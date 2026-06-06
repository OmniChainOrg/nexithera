"""partnerability + IND readiness (PR #10)

Revision ID: 010
Revises: 009
Create Date: 2026-06-06 13:00:00.000000

Adds the strategic-decision tables that let Genovate answer two
questions about every candidate:

    * **Is this asset partnerable?**  -> competitive landscape, IP
      position, differentiation, BD fit.
    * **Is this asset IND-ready?**    -> regulatory checklist (CMC,
      non-clinical tox, clinical, regulatory, GMP).

Tables added::

    * ``competitive_assets``        — competing assets in the same
                                      target/disease space.
    * ``ip_positions``              — patent records / FTO snapshots.
    * ``ind_readiness_items``       — global checklist of regulatory
                                      gate items (seeded with 20+ rows).
    * ``candidate_ind_readiness``   — per-candidate status for each
                                      checklist item.
    * ``partnerability_scores``     — composite partnerability score
                                      with sub-scores and ranked
                                      potential partners.

The migration also extends ``agent_runs.run_type`` with the four new
agent types so PR #10 traces persist via ``BaseAgent.run()``.

All statements are idempotent (``IF NOT EXISTS`` / ``DO $$``) and safe
to re-run.
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Pre-populated IND checklist (>=20 items across CMC, non-clinical,
# clinical, regulatory, GMP) -- mirrors the table in the PR #10 spec.
# ---------------------------------------------------------------------------
_IND_CHECKLIST_SEED = [
    ("CMC", "Cell line / source characterization",
     "Identity, purity, and stability of the production cell line or "
     "source material.", True),
    ("CMC", "Master cell bank / working cell bank",
     "MCB and WCB established, characterized, and released per ICH Q5A/Q5D.",
     True),
    ("CMC", "Manufacturing process definition",
     "Defined upstream/downstream process with in-process controls.", True),
    ("CMC", "Analytical methods validated",
     "Identity, purity, potency, and safety methods validated per ICH Q2.",
     True),
    ("CMC", "Reference standard established",
     "Primary reference standard qualified.", True),
    ("CMC", "Formulation finalized",
     "Drug product formulation locked for IND-enabling tox and Phase I.",
     True),
    ("CMC", "Stability data (3 months accelerated)",
     "Drug substance and drug product stability per ICH Q1A.", True),
    ("nonclinical_tox", "Primary pharmacology (PoC)",
     "In vivo proof-of-concept demonstrating MoA-relevant activity.", True),
    ("nonclinical_tox", "Secondary pharmacology (safety panel)",
     "Off-target binding / functional panel (e.g. Eurofins SafetyScreen).",
     True),
    ("nonclinical_tox", "In vitro toxicology (hERG, genotox)",
     "hERG, Ames, micronucleus per ICH S7B / S2.", True),
    ("nonclinical_tox", "28-day repeat dose toxicity (2 species)",
     "GLP repeat-dose toxicology in rodent + non-rodent per ICH M3.", True),
    ("nonclinical_tox", "Safety pharmacology (CNS, respiratory, CV)",
     "Core battery per ICH S7A.", True),
    ("nonclinical_tox", "Biodistribution (for gene/cell therapies)",
     "qPCR biodistribution if applicable to modality.", False),
    ("clinical_protocol", "Draft protocol (Phase I)",
     "First-in-human protocol with dose escalation plan.", True),
    ("clinical_protocol", "Investigator brochure",
     "IB compiled per ICH E6 with non-clinical + CMC summaries.", True),
    ("clinical_protocol", "Informed consent template",
     "ICF template aligned with the protocol risk profile.", True),
    ("regulatory", "Pre-IND meeting with FDA (if US)",
     "Type B pre-IND meeting requested and held.", False),
    ("regulatory", "IND application package assembled",
     "Modules 1-5 of the IND assembled and QC'd.", True),
    ("gmp", "GMP batch produced",
     "At least one cGMP-compliant clinical-supply batch produced.", True),
    ("gmp", "Certificate of analysis",
     "CoA issued for clinical supply batch.", True),
    ("gmp", "GMP facility qualification",
     "Manufacturing facility qualified / audited for cGMP.", True),
]


def upgrade() -> None:
    # Extend agent_runs.run_type CHECK with PR #10 agent types.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                 WHERE conname = 'agent_runs_run_type_check'
            ) THEN
                ALTER TABLE agent_runs
                    DROP CONSTRAINT agent_runs_run_type_check;
            END IF;
            ALTER TABLE agent_runs
                ADD CONSTRAINT agent_runs_run_type_check
                CHECK (run_type IN (
                    'target_assessment', 'evidence_synthesis',
                    'simulation_critique', 'literature_extraction',
                    'safety_check', 'formulation_analysis',
                    'gap_analysis', 'active_learning',
                    'competitive_landscape', 'ip_position',
                    'ind_readiness', 'partnerability'
                ));
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # competitive_assets
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS competitive_assets (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
            target_id UUID REFERENCES bio_entities(id) ON DELETE SET NULL,
            disease_id UUID REFERENCES bio_entities(id) ON DELETE SET NULL,
            asset_name TEXT NOT NULL,
            developer TEXT,
            phase TEXT,
            modality TEXT,
            mechanism TEXT,
            estimated_launch_year INTEGER,
            differentiation TEXT,
            threat_level TEXT CHECK (threat_level IN ('low', 'medium', 'high')),
            source TEXT CHECK (source IN (
                'clinicaltrials_gov', 'pubmed', 'patent',
                'press_release', 'mock'
            )),
            source_ref TEXT,
            confidence REAL CHECK (confidence IS NULL OR
                                   (confidence >= 0 AND confidence <= 1)),
            agent_run_id UUID REFERENCES agent_runs(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_competitive_assets_candidate "
        "ON competitive_assets(candidate_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_competitive_assets_target "
        "ON competitive_assets(target_id)"
    )

    # ------------------------------------------------------------------
    # ip_positions
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ip_positions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
            patent_number TEXT,
            patent_family TEXT,
            assignee TEXT,
            expiry_year INTEGER,
            jurisdiction TEXT,
            claims TEXT,
            is_blocking BOOLEAN NOT NULL DEFAULT FALSE,
            freedom_to_operate_estimate REAL CHECK (
                freedom_to_operate_estimate IS NULL OR
                (freedom_to_operate_estimate >= 0 AND
                 freedom_to_operate_estimate <= 1)
            ),
            agent_run_id UUID REFERENCES agent_runs(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ip_positions_candidate "
        "ON ip_positions(candidate_id)"
    )

    # ------------------------------------------------------------------
    # ind_readiness_items (template)
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ind_readiness_items (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            category TEXT NOT NULL CHECK (category IN (
                'CMC', 'nonclinical_tox', 'clinical_protocol',
                'regulatory', 'gmp'
            )),
            item TEXT NOT NULL UNIQUE,
            description TEXT,
            is_required BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # ------------------------------------------------------------------
    # candidate_ind_readiness (per-candidate responses)
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS candidate_ind_readiness (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            candidate_id UUID NOT NULL
                REFERENCES candidates(id) ON DELETE CASCADE,
            checklist_item_id UUID NOT NULL
                REFERENCES ind_readiness_items(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'not_started' CHECK (status IN (
                'not_started', 'in_progress', 'complete',
                'waived', 'failed'
            )),
            evidence_uri TEXT,
            notes TEXT,
            updated_by UUID REFERENCES users(id),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (candidate_id, checklist_item_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_candidate_ind_readiness_candidate "
        "ON candidate_ind_readiness(candidate_id)"
    )

    # ------------------------------------------------------------------
    # partnerability_scores
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS partnerability_scores (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            candidate_id UUID NOT NULL
                REFERENCES candidates(id) ON DELETE CASCADE,
            overall_score REAL NOT NULL CHECK (
                overall_score >= 0 AND overall_score <= 10
            ),
            competitive_moat_score REAL CHECK (
                competitive_moat_score IS NULL OR
                (competitive_moat_score >= 0 AND competitive_moat_score <= 10)
            ),
            ip_strength_score REAL CHECK (
                ip_strength_score IS NULL OR
                (ip_strength_score >= 0 AND ip_strength_score <= 10)
            ),
            unmet_need_score REAL CHECK (
                unmet_need_score IS NULL OR
                (unmet_need_score >= 0 AND unmet_need_score <= 10)
            ),
            ind_readiness_score REAL CHECK (
                ind_readiness_score IS NULL OR
                (ind_readiness_score >= 0 AND ind_readiness_score <= 10)
            ),
            bd_interest_estimate REAL CHECK (
                bd_interest_estimate IS NULL OR
                (bd_interest_estimate >= 0 AND bd_interest_estimate <= 1)
            ),
            potential_partners JSONB NOT NULL DEFAULT '[]',
            rationale TEXT,
            agent_run_id UUID REFERENCES agent_runs(id),
            assessed_by UUID REFERENCES users(id),
            assessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_partnerability_scores_candidate "
        "ON partnerability_scores(candidate_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_partnerability_scores_assessed_at "
        "ON partnerability_scores(assessed_at DESC)"
    )

    # ------------------------------------------------------------------
    # Seed the IND checklist template (>=20 items).
    # ------------------------------------------------------------------
    for category, item, description, is_required in _IND_CHECKLIST_SEED:
        op.execute(
            """
            INSERT INTO ind_readiness_items
                (category, item, description, is_required)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (item) DO NOTHING
            """ % (
                _q(category), _q(item), _q(description),
                "TRUE" if is_required else "FALSE",
            )
        )

    # ------------------------------------------------------------------
    # Seed the four PR #10 agents.
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO agents (name, role, description, system_prompt, is_active)
        VALUES
            ('Competitive Landscape Agent', 'competitive_landscape',
             'Identifies competing assets in the same target/disease space '
             'using ClinicalTrials.gov, PubMed, and patent databases.',
             'You are a competitive intelligence analyst. Identify '
             'competing assets, their phase, modality, mechanism, and '
             'differentiation vs. the candidate. Cite every competitor.',
             TRUE),
            ('IP Position Agent', 'ip_position',
             'Estimates freedom-to-operate, identifies blocking patents '
             'and white-space windows.',
             'You are a patent analyst. Identify blocking patents, '
             'estimate FTO (0-1), and surface white-space opportunities.',
             TRUE),
            ('IND Readiness Agent', 'ind_readiness',
             'Compares a candidate against the IND checklist; identifies '
             'critical gaps; estimates timeline to IND completion.',
             'You are a regulatory affairs lead. Assess IND readiness '
             'item-by-item; never invent completed items.',
             TRUE),
            ('Partnerability Agent', 'partnerability',
             'Synthesizes competitive, IP, unmet-need, and IND-readiness '
             'sub-scores into a composite partnerability score (0-10).',
             'You are a BD strategist. Compute a weighted partnerability '
             'score and rank potential partners by strategic fit.',
             TRUE)
        ON CONFLICT (name) DO NOTHING
        """
    )


def _q(value: str) -> str:
    """Escape a literal for inline SQL substitution (Postgres-safe)."""
    if value is None:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS partnerability_scores CASCADE")
    op.execute("DROP TABLE IF EXISTS candidate_ind_readiness CASCADE")
    op.execute("DROP TABLE IF EXISTS ind_readiness_items CASCADE")
    op.execute("DROP TABLE IF EXISTS ip_positions CASCADE")
    op.execute("DROP TABLE IF EXISTS competitive_assets CASCADE")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                 WHERE conname = 'agent_runs_run_type_check'
            ) THEN
                ALTER TABLE agent_runs
                    DROP CONSTRAINT agent_runs_run_type_check;
            END IF;
            ALTER TABLE agent_runs
                ADD CONSTRAINT agent_runs_run_type_check
                CHECK (run_type IN (
                    'target_assessment', 'evidence_synthesis',
                    'simulation_critique', 'literature_extraction',
                    'safety_check', 'formulation_analysis',
                    'gap_analysis', 'active_learning'
                ));
        END $$;
        """
    )
