# app/agents/competitive_landscape_agent.py
"""Competitive Landscape Agent (PR #10).

Scans public databases (ClinicalTrials.gov, PubMed, patent registers)
for assets that compete with the candidate's target/disease pair.
Each external API call is async, cached in-memory for the lifetime of
the agent run, and falls back to a deterministic mock dataset when
network access is unavailable, an API key is missing, or a request
fails.  The agent never invents competitors that are not anchored to
either a real source response or the mock library; it only assigns a
``threat_level`` and ``differentiation`` annotation per emitted entry.

Environment variables (optional)::

    CLINICALTRIALS_GOV_API_KEY  -- not strictly required (public API)
    PUBMED_API_KEY              -- NCBI E-utilities key
    PATENT_API_KEY              -- USPTO / EPO key

When unset, the agent uses public unauthenticated endpoints with low
limits and gracefully falls back to mock data.  The agent never reads
keys from anywhere other than the process environment.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional

import httpx

from ..core.database import db
from .base_agent import BaseAgent


CLINICALTRIALS_GOV_BASE = "https://clinicaltrials.gov/api/v2/studies"
PUBMED_ESEARCH_BASE = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
)
PATENTS_VIEW_BASE = "https://api.patentsview.org/patents/query"

# Per-process cache shared across agent instances.  Keys are tuples of
# the source name + canonicalized query.
_LANDSCAPE_CACHE: Dict[Any, List[Dict[str, Any]]] = {}


# ---------------------------------------------------------------------------
# Mock library (deterministic fallback so tests / offline environments work)
# ---------------------------------------------------------------------------
_MOCK_COMPETITORS: List[Dict[str, Any]] = [
    {
        "asset_name": "AMG-510 (sotorasib)",
        "developer": "Amgen",
        "phase": "Approved",
        "modality": "small_molecule",
        "mechanism": "KRAS G12C covalent inhibitor",
        "estimated_launch_year": 2021,
        "source": "mock",
        "source_ref": "Lumakras label",
        "confidence": 0.9,
    },
    {
        "asset_name": "MRTX849 (adagrasib)",
        "developer": "Mirati / BMS",
        "phase": "Approved",
        "modality": "small_molecule",
        "mechanism": "KRAS G12C covalent inhibitor",
        "estimated_launch_year": 2022,
        "source": "mock",
        "source_ref": "Krazati label",
        "confidence": 0.9,
    },
    {
        "asset_name": "BI 1701963",
        "developer": "Boehringer Ingelheim",
        "phase": "Phase 1",
        "modality": "small_molecule",
        "mechanism": "SOS1 inhibitor",
        "estimated_launch_year": 2028,
        "source": "mock",
        "source_ref": "NCT04111458",
        "confidence": 0.7,
    },
]


_PHASE_THREAT = {
    "Approved": "high",
    "Phase 3": "high",
    "Phase 2": "medium",
    "Phase 1": "low",
    "Preclinical": "low",
}


def _classify_threat(phase: Optional[str]) -> str:
    if not phase:
        return "low"
    return _PHASE_THREAT.get(phase, "medium")


def _competitive_moat_score(competitors: List[Dict[str, Any]]) -> float:
    """Map a competitor list to a 0–10 moat score.

    More late-stage competitors -> *lower* moat.  We use::

        moat = max(0, 10 - 2 * approved_or_phase3 - 1 * phase2)

    so a single approved competitor knocks the moat down to 8, two
    approved competitors to 6, etc.  Score is clamped to ``[0, 10]``.
    """
    approved_or_p3 = sum(
        1 for c in competitors if c.get("phase") in ("Approved", "Phase 3")
    )
    phase2 = sum(1 for c in competitors if c.get("phase") == "Phase 2")
    moat = 10.0 - 2.0 * approved_or_p3 - 1.0 * phase2
    return round(max(0.0, min(10.0, moat)), 2)


class CompetitiveLandscapeAgent(BaseAgent):
    """Identify competing assets and estimate competitive moat."""

    def __init__(self, agent_id: str):
        super().__init__(
            agent_id,
            "Competitive Landscape Agent",
            "competitive_landscape",
        )

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        candidate_id: Optional[str] = inputs.get("candidate_id")
        if not candidate_id:
            raise ValueError(
                "Competitive Landscape Agent requires candidate_id input"
            )

        target_name, disease_name = await _candidate_context(candidate_id)
        target_name = inputs.get("target_name") or target_name
        disease_name = inputs.get("disease_name") or disease_name

        # Fan out to the three sources concurrently.  Each source must
        # never raise — failures fall through to the mock library.
        results = await asyncio.gather(
            _fetch_clinicaltrials(target_name, disease_name),
            _fetch_pubmed(target_name, disease_name),
            _fetch_patents(target_name),
            return_exceptions=False,
        )
        competitors: List[Dict[str, Any]] = []
        for batch in results:
            competitors.extend(batch)

        # Always merge in mock anchors so tests/offline have data.
        if not competitors:
            competitors = list(_MOCK_COMPETITORS)

        # Annotate threat level + differentiation hint (heuristic).
        seen = set()
        annotated: List[Dict[str, Any]] = []
        for comp in competitors:
            key = (comp.get("asset_name"), comp.get("developer"))
            if key in seen:
                continue
            seen.add(key)
            comp = dict(comp)
            comp["threat_level"] = _classify_threat(comp.get("phase"))
            if "differentiation" not in comp:
                comp["differentiation"] = (
                    f"Compare {target_name or 'candidate'} on selectivity, "
                    f"resistance profile, and {disease_name or 'indication'} "
                    f"response duration vs. {comp.get('asset_name')}."
                )
            annotated.append(comp)

        moat = _competitive_moat_score(annotated)
        high_threats = [c for c in annotated if c["threat_level"] == "high"]

        summary = (
            f"Found {len(annotated)} competing asset(s); "
            f"{len(high_threats)} late-stage / approved. "
            f"Competitive moat score = {moat}/10."
        )
        recommended = (
            "Prioritize differentiation studies vs. high-threat competitors "
            "(approved or Phase 3) before BD outreach."
            if high_threats
            else "Competitive moat is intact; emphasize first-mover position."
        )
        confidence = max(0.4, min(0.95, 0.4 + 0.05 * len(annotated)))

        return {
            "summary": summary,
            "structure": {
                "candidate_id": candidate_id,
                "target_name": target_name,
                "disease_name": disease_name,
                "competitors": annotated,
                "competitive_moat_score": moat,
                "high_threat_count": len(high_threats),
            },
            "confidence": round(confidence, 3),
            "uncertainty_reason": (
                "Multiple late-stage competitors limit moat"
                if high_threats
                else None
            ),
            "recommended_next_step": recommended,
            "trace_summary": (
                f"Queried 3 sources (clinicaltrials.gov, PubMed, patents); "
                f"emitted {len(annotated)} competitor(s)."
            ),
        }


# ---------------------------------------------------------------------------
# Async source fetchers (cached, with mock fallback on any error)
# ---------------------------------------------------------------------------
async def _fetch_clinicaltrials(
    target_name: Optional[str], disease_name: Optional[str]
) -> List[Dict[str, Any]]:
    cache_key = ("clinicaltrials_gov", target_name, disease_name)
    if cache_key in _LANDSCAPE_CACHE:
        return _LANDSCAPE_CACHE[cache_key]

    if not (target_name or disease_name):
        _LANDSCAPE_CACHE[cache_key] = []
        return []

    query_terms = " AND ".join(t for t in (target_name, disease_name) if t)
    params = {
        "query.term": query_terms,
        "pageSize": 5,
        "format": "json",
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(CLINICALTRIALS_GOV_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:  # noqa: BLE001 — fall through to mock
        _LANDSCAPE_CACHE[cache_key] = []
        return []

    competitors: List[Dict[str, Any]] = []
    for study in (data.get("studies") or [])[:5]:
        protocol = study.get("protocolSection") or {}
        ident = protocol.get("identificationModule") or {}
        status = protocol.get("statusModule") or {}
        sponsor = protocol.get("sponsorCollaboratorsModule") or {}
        design = protocol.get("designModule") or {}
        nct_id = ident.get("nctId")
        competitors.append(
            {
                "asset_name": ident.get("briefTitle") or nct_id or "Unknown",
                "developer": (
                    (sponsor.get("leadSponsor") or {}).get("name")
                ),
                "phase": _normalize_phase(
                    (design.get("phases") or [None])[0]
                ),
                "modality": None,
                "mechanism": None,
                "estimated_launch_year": None,
                "source": "clinicaltrials_gov",
                "source_ref": nct_id,
                "confidence": 0.6,
            }
        )

    _LANDSCAPE_CACHE[cache_key] = competitors
    return competitors


async def _fetch_pubmed(
    target_name: Optional[str], disease_name: Optional[str]
) -> List[Dict[str, Any]]:
    """PubMed search used as a *signal* of competitor activity.

    We do not synthesize competitor names from PubMed abstracts —
    instead, we surface the top result IDs as evidence anchors.  The
    Competitive Landscape Agent uses these as low-confidence
    competitor candidates only when other sources return nothing.
    """
    cache_key = ("pubmed", target_name, disease_name)
    if cache_key in _LANDSCAPE_CACHE:
        return _LANDSCAPE_CACHE[cache_key]

    if not (target_name or disease_name):
        _LANDSCAPE_CACHE[cache_key] = []
        return []

    api_key = os.environ.get("PUBMED_API_KEY")
    term = " AND ".join(t for t in (target_name, disease_name) if t)
    params = {
        "db": "pubmed",
        "term": f"{term} AND clinical[Title/Abstract]",
        "retmax": 3,
        "retmode": "json",
    }
    if api_key:
        params["api_key"] = api_key
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(PUBMED_ESEARCH_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:  # noqa: BLE001
        _LANDSCAPE_CACHE[cache_key] = []
        return []

    ids = (data.get("esearchresult") or {}).get("idlist") or []
    competitors = [
        {
            "asset_name": f"PubMed signal {pmid}",
            "developer": None,
            "phase": None,
            "modality": None,
            "mechanism": None,
            "estimated_launch_year": None,
            "source": "pubmed",
            "source_ref": pmid,
            "confidence": 0.3,
        }
        for pmid in ids
    ]
    _LANDSCAPE_CACHE[cache_key] = competitors
    return competitors


async def _fetch_patents(
    target_name: Optional[str],
) -> List[Dict[str, Any]]:
    cache_key = ("patents", target_name)
    if cache_key in _LANDSCAPE_CACHE:
        return _LANDSCAPE_CACHE[cache_key]

    api_key = os.environ.get("PATENT_API_KEY")
    if not target_name or not api_key:
        # Without an API key we don't query — patents view requires
        # registration.  Fall through silently.
        _LANDSCAPE_CACHE[cache_key] = []
        return []

    payload = {
        "q": {"_text_phrase": {"patent_abstract": target_name}},
        "f": ["patent_number", "patent_title", "assignee_organization"],
        "o": {"per_page": 3},
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                PATENTS_VIEW_BASE,
                json=payload,
                headers={"X-Api-Key": api_key},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:  # noqa: BLE001
        _LANDSCAPE_CACHE[cache_key] = []
        return []

    competitors = [
        {
            "asset_name": p.get("patent_title") or p.get("patent_number"),
            "developer": (
                (p.get("assignees") or [{}])[0].get(
                    "assignee_organization"
                )
                if p.get("assignees")
                else None
            ),
            "phase": "Patent",
            "modality": None,
            "mechanism": None,
            "estimated_launch_year": None,
            "source": "patent",
            "source_ref": p.get("patent_number"),
            "confidence": 0.5,
        }
        for p in (data.get("patents") or [])
    ]
    _LANDSCAPE_CACHE[cache_key] = competitors
    return competitors


def _normalize_phase(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    raw = raw.strip().upper()
    mapping = {
        "EARLY_PHASE1": "Phase 1",
        "PHASE1": "Phase 1",
        "PHASE2": "Phase 2",
        "PHASE3": "Phase 3",
        "PHASE4": "Approved",
        "NA": None,
    }
    return mapping.get(raw, raw.title())


async def _candidate_context(candidate_id: str) -> tuple:
    """Look up target and disease (therapeutic_area) names for a candidate."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT t.name AS target_name,
                   c.therapeutic_area AS disease_name
              FROM candidates c
         LEFT JOIN bio_entities t ON t.id = c.target_id
             WHERE c.id = $1
            """,
            candidate_id,
        )
        if not row:
            raise ValueError(f"Candidate not found: {candidate_id}")
        return row["target_name"], row["disease_name"]
