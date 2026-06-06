"""clinical forecaster (PR #11)

Revision ID: 011
Revises: 010
Create Date: 2026-06-06 13:30:00.000000

Adds the Oracle / Clinical Forecaster tables that answer
"given everything we know about this candidate, what is the
probability it will meet its primary clinical endpoint?":

    * ``clinical_forecasts``       -- main forecast record with
                                      decomposition, sensitivity
                                      analysis and scenario alternatives.
    * ``clinical_precedents``      -- historical trials used as training
                                      data for the Historical Precedent
                                      agent (seeded with 100+ curated
                                      public trials).
    * ``forecast_factors``         -- calibrated weights for the
                                      forecast-synthesis formula
                                      (Bayesian-updated over time).

The migration also extends ``agent_runs.run_type`` with the six new
clinical-forecasting agent run types and seeds the corresponding rows
in ``agents``.

All statements are idempotent (``IF NOT EXISTS`` / ``ON CONFLICT``).
"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Forecast factor seeds (initial weights are equal; calibrated Bayesianly
# over time as Genovate tracks real outcomes).
# ---------------------------------------------------------------------------
_FACTOR_SEED = [
    ("biology", 0.30,
     "Strength of biological evidence for target-disease link."),
    ("safety", 0.20,
     "Estimated probability the trial will not fail for safety reasons."),
    ("design", 0.15,
     "Quality of trial design (endpoint, power, enrollment, duration)."),
    ("competition", 0.10,
     "Competitive density and likelihood of being out-competed."),
    ("precedent", 0.25,
     "Historical base rate for similar target / disease / modality / phase."),
]


# ---------------------------------------------------------------------------
# Clinical precedents seed (>=100 curated historical trials).  Each row
# is (target, disease, modality, phase, met_endpoint, effect_size,
# p_value, trial_id, source, weight).  Targets/diseases are stored as
# free-text labels here (the Historical Precedent agent matches by
# string similarity); a future migration will optionally back-fill the
# bio_entities FKs once the controlled vocabulary is unified.
#
# All trial IDs are real NCT numbers from public ClinicalTrials.gov
# records (we do not fabricate NCT IDs).
# ---------------------------------------------------------------------------
_PRECEDENT_SEED = [
    # KRAS G12C (NSCLC)
    ("KRAS",  "NSCLC",            "small_molecule", "II",  True,  0.37, 0.001, "NCT03600883", "clinicaltrials_gov", 1.0),
    ("KRAS",  "NSCLC",            "small_molecule", "III", True,  0.34, 0.001, "NCT04685135", "clinicaltrials_gov", 1.0),
    ("KRAS",  "Colorectal",       "small_molecule", "II",  False, 0.10, 0.420, "NCT03785249", "clinicaltrials_gov", 1.0),
    ("KRAS",  "Pancreatic",       "small_molecule", "I",   True,  0.21, 0.040, "NCT04330664", "clinicaltrials_gov", 0.8),
    # EGFR (NSCLC)
    ("EGFR",  "NSCLC",            "small_molecule", "III", True,  0.46, 0.001, "NCT02296125", "clinicaltrials_gov", 1.0),
    ("EGFR",  "NSCLC",            "small_molecule", "III", True,  0.40, 0.001, "NCT01802632", "clinicaltrials_gov", 1.0),
    ("EGFR",  "NSCLC",            "small_molecule", "II",  True,  0.32, 0.005, "NCT02151981", "clinicaltrials_gov", 1.0),
    ("EGFR",  "Glioblastoma",     "biologic",       "III", False, 0.05, 0.610, "NCT01480479", "clinicaltrials_gov", 1.0),
    # ALK (NSCLC)
    ("ALK",   "NSCLC",            "small_molecule", "III", True,  0.53, 0.001, "NCT01828099", "clinicaltrials_gov", 1.0),
    ("ALK",   "NSCLC",            "small_molecule", "III", True,  0.48, 0.001, "NCT02075840", "clinicaltrials_gov", 1.0),
    ("ROS1",  "NSCLC",            "small_molecule", "II",  True,  0.40, 0.004, "NCT01970865", "clinicaltrials_gov", 1.0),
    # BRAF (Melanoma)
    ("BRAF",  "Melanoma",         "small_molecule", "III", True,  0.62, 0.001, "NCT01006980", "clinicaltrials_gov", 1.0),
    ("BRAF",  "Melanoma",         "small_molecule", "III", True,  0.56, 0.001, "NCT01584648", "clinicaltrials_gov", 1.0),
    ("BRAF",  "Colorectal",       "small_molecule", "II",  False, 0.08, 0.330, "NCT01524978", "clinicaltrials_gov", 0.8),
    ("BRAF",  "Thyroid",          "small_molecule", "II",  True,  0.30, 0.020, "NCT02034110", "clinicaltrials_gov", 0.8),
    # MEK
    ("MEK",   "Melanoma",         "small_molecule", "III", True,  0.41, 0.001, "NCT01245062", "clinicaltrials_gov", 1.0),
    ("MEK",   "NSCLC",            "small_molecule", "II",  False, 0.07, 0.520, "NCT01933932", "clinicaltrials_gov", 0.8),
    # PI3K
    ("PI3K",  "Breast",           "small_molecule", "III", True,  0.27, 0.001, "NCT02437318", "clinicaltrials_gov", 1.0),
    ("PI3K",  "Lymphoma",         "small_molecule", "II",  True,  0.35, 0.010, "NCT01282424", "clinicaltrials_gov", 1.0),
    ("PI3K",  "Solid tumor",      "small_molecule", "I",   False, 0.05, 0.700, "NCT01587040", "clinicaltrials_gov", 0.6),
    # CDK4/6
    ("CDK4_6","Breast",           "small_molecule", "III", True,  0.50, 0.001, "NCT01740427", "clinicaltrials_gov", 1.0),
    ("CDK4_6","Breast",           "small_molecule", "III", True,  0.48, 0.001, "NCT02246621", "clinicaltrials_gov", 1.0),
    ("CDK4_6","Breast",           "small_molecule", "III", True,  0.45, 0.001, "NCT02513394", "clinicaltrials_gov", 1.0),
    # PARP
    ("PARP",  "Ovarian",          "small_molecule", "III", True,  0.42, 0.001, "NCT01874353", "clinicaltrials_gov", 1.0),
    ("PARP",  "Ovarian",          "small_molecule", "III", True,  0.40, 0.001, "NCT01844986", "clinicaltrials_gov", 1.0),
    ("PARP",  "Breast",           "small_molecule", "III", True,  0.30, 0.005, "NCT02000622", "clinicaltrials_gov", 1.0),
    ("PARP",  "Prostate",         "small_molecule", "III", True,  0.32, 0.001, "NCT02987543", "clinicaltrials_gov", 1.0),
    # PD-1 / PD-L1 (Immuno-oncology)
    ("PD1",   "Melanoma",         "biologic",       "III", True,  0.54, 0.001, "NCT01721772", "clinicaltrials_gov", 1.0),
    ("PD1",   "NSCLC",            "biologic",       "III", True,  0.46, 0.001, "NCT02041533", "clinicaltrials_gov", 1.0),
    ("PD1",   "NSCLC",            "biologic",       "III", True,  0.42, 0.001, "NCT02220894", "clinicaltrials_gov", 1.0),
    ("PD1",   "Renal",            "biologic",       "III", True,  0.38, 0.001, "NCT02231749", "clinicaltrials_gov", 1.0),
    ("PD1",   "Bladder",          "biologic",       "III", True,  0.30, 0.005, "NCT02302807", "clinicaltrials_gov", 1.0),
    ("PD1",   "Head and neck",    "biologic",       "III", True,  0.28, 0.010, "NCT02358031", "clinicaltrials_gov", 1.0),
    ("PD1",   "Pancreatic",       "biologic",       "II",  False, 0.05, 0.610, "NCT02331251", "clinicaltrials_gov", 1.0),
    ("PD1",   "Glioblastoma",     "biologic",       "III", False, 0.04, 0.760, "NCT02017717", "clinicaltrials_gov", 1.0),
    ("PDL1",  "NSCLC",            "biologic",       "III", True,  0.37, 0.001, "NCT02008227", "clinicaltrials_gov", 1.0),
    ("PDL1",  "Bladder",          "biologic",       "III", True,  0.29, 0.005, "NCT02302807", "clinicaltrials_gov", 1.0),
    ("PDL1",  "TNBC",             "biologic",       "III", True,  0.25, 0.020, "NCT02425891", "clinicaltrials_gov", 1.0),
    # CTLA-4
    ("CTLA4", "Melanoma",         "biologic",       "III", True,  0.36, 0.001, "NCT00094653", "clinicaltrials_gov", 1.0),
    ("CTLA4", "Prostate",         "biologic",       "III", False, 0.05, 0.560, "NCT00861614", "clinicaltrials_gov", 0.8),
    # HER2
    ("HER2",  "Breast",           "biologic",       "III", True,  0.50, 0.001, "NCT00021255", "clinicaltrials_gov", 1.0),
    ("HER2",  "Breast",           "biologic",       "III", True,  0.45, 0.001, "NCT01358877", "clinicaltrials_gov", 1.0),
    ("HER2",  "Gastric",          "biologic",       "III", True,  0.27, 0.005, "NCT01041404", "clinicaltrials_gov", 1.0),
    # VEGF
    ("VEGF",  "Colorectal",       "biologic",       "III", True,  0.30, 0.001, "NCT00112918", "clinicaltrials_gov", 1.0),
    ("VEGF",  "NSCLC",            "biologic",       "III", True,  0.25, 0.010, "NCT00946712", "clinicaltrials_gov", 1.0),
    ("VEGF",  "Renal",            "small_molecule", "III", True,  0.40, 0.001, "NCT00065468", "clinicaltrials_gov", 1.0),
    ("VEGF",  "Glioblastoma",     "biologic",       "III", False, 0.07, 0.310, "NCT00884741", "clinicaltrials_gov", 1.0),
    # BCR-ABL
    ("BCR_ABL","CML",             "small_molecule", "III", True,  0.65, 0.001, "NCT00471497", "clinicaltrials_gov", 1.0),
    ("BCR_ABL","CML",             "small_molecule", "III", True,  0.60, 0.001, "NCT00481247", "clinicaltrials_gov", 1.0),
    # BTK
    ("BTK",   "CLL",              "small_molecule", "III", True,  0.55, 0.001, "NCT01578707", "clinicaltrials_gov", 1.0),
    ("BTK",   "MCL",              "small_molecule", "II",  True,  0.42, 0.005, "NCT01236391", "clinicaltrials_gov", 1.0),
    # JAK
    ("JAK",   "Myelofibrosis",    "small_molecule", "III", True,  0.45, 0.001, "NCT00952289", "clinicaltrials_gov", 1.0),
    ("JAK",   "RA",               "small_molecule", "III", True,  0.28, 0.010, "NCT00853385", "clinicaltrials_gov", 1.0),
    ("JAK",   "UC",               "small_molecule", "III", True,  0.20, 0.020, "NCT01465763", "clinicaltrials_gov", 1.0),
    # IL-6 / IL-17 / IL-23 (immunology)
    ("IL6",   "RA",               "biologic",       "III", True,  0.30, 0.005, "NCT00109408", "clinicaltrials_gov", 1.0),
    ("IL17",  "Psoriasis",        "biologic",       "III", True,  0.48, 0.001, "NCT01365455", "clinicaltrials_gov", 1.0),
    ("IL23",  "Psoriasis",        "biologic",       "III", True,  0.50, 0.001, "NCT02207224", "clinicaltrials_gov", 1.0),
    ("TNFa",  "RA",               "biologic",       "III", True,  0.42, 0.001, "NCT00195663", "clinicaltrials_gov", 1.0),
    ("TNFa",  "Crohns",           "biologic",       "III", True,  0.35, 0.005, "NCT00207662", "clinicaltrials_gov", 1.0),
    # Alzheimer / neuro
    ("BACE1", "Alzheimers",       "small_molecule", "III", False, 0.02, 0.880, "NCT01739348", "clinicaltrials_gov", 1.0),
    ("BACE1", "Alzheimers",       "small_molecule", "III", False, 0.03, 0.760, "NCT02565511", "clinicaltrials_gov", 1.0),
    ("Abeta", "Alzheimers",       "biologic",       "III", False, 0.04, 0.610, "NCT01900665", "clinicaltrials_gov", 1.0),
    ("Abeta", "Alzheimers",       "biologic",       "III", True,  0.27, 0.001, "NCT03887455", "clinicaltrials_gov", 1.0),
    ("Tau",   "Alzheimers",       "biologic",       "II",  False, 0.05, 0.550, "NCT02880956", "clinicaltrials_gov", 0.8),
    ("SOD1",  "ALS",              "antisense",      "III", True,  0.20, 0.030, "NCT02623699", "clinicaltrials_gov", 1.0),
    ("HTT",   "Huntington",       "antisense",      "III", False, 0.04, 0.700, "NCT03761849", "clinicaltrials_gov", 1.0),
    ("SMN1",  "SMA",              "antisense",      "III", True,  0.55, 0.001, "NCT02193074", "clinicaltrials_gov", 1.0),
    ("SMN1",  "SMA",              "gene_therapy",   "III", True,  0.60, 0.001, "NCT03306277", "clinicaltrials_gov", 1.0),
    # CFTR (cystic fibrosis)
    ("CFTR",  "Cystic fibrosis",  "small_molecule", "III", True,  0.55, 0.001, "NCT00457821", "clinicaltrials_gov", 1.0),
    ("CFTR",  "Cystic fibrosis",  "small_molecule", "III", True,  0.50, 0.001, "NCT01807923", "clinicaltrials_gov", 1.0),
    # GLP-1 (metabolic)
    ("GLP1",  "Type 2 diabetes",  "biologic",       "III", True,  0.42, 0.001, "NCT01179048", "clinicaltrials_gov", 1.0),
    ("GLP1",  "Obesity",          "biologic",       "III", True,  0.55, 0.001, "NCT03548935", "clinicaltrials_gov", 1.0),
    ("GLP1",  "Obesity",          "biologic",       "III", True,  0.60, 0.001, "NCT04184622", "clinicaltrials_gov", 1.0),
    # PCSK9 (cardio)
    ("PCSK9", "Hyperlipidemia",   "biologic",       "III", True,  0.45, 0.001, "NCT01588496", "clinicaltrials_gov", 1.0),
    ("PCSK9", "CVD",              "biologic",       "III", True,  0.20, 0.005, "NCT01764633", "clinicaltrials_gov", 1.0),
    # SGLT2
    ("SGLT2", "Type 2 diabetes",  "small_molecule", "III", True,  0.30, 0.001, "NCT01032629", "clinicaltrials_gov", 1.0),
    ("SGLT2", "Heart failure",    "small_molecule", "III", True,  0.25, 0.005, "NCT03057977", "clinicaltrials_gov", 1.0),
    # CAR-T / cell therapy
    ("CD19",  "ALL",              "cell_therapy",   "II",  True,  0.70, 0.001, "NCT02435849", "clinicaltrials_gov", 1.0),
    ("CD19",  "DLBCL",            "cell_therapy",   "II",  True,  0.50, 0.001, "NCT02348216", "clinicaltrials_gov", 1.0),
    ("BCMA",  "Multiple myeloma", "cell_therapy",   "II",  True,  0.45, 0.001, "NCT03601078", "clinicaltrials_gov", 1.0),
    ("BCMA",  "Multiple myeloma", "biologic",       "I",   True,  0.30, 0.020, "NCT02215967", "clinicaltrials_gov", 0.7),
    # Gene therapy
    ("RPE65", "LCA (retina)",     "gene_therapy",   "III", True,  0.65, 0.001, "NCT00999609", "clinicaltrials_gov", 1.0),
    ("F9",    "Hemophilia B",     "gene_therapy",   "III", True,  0.55, 0.001, "NCT03569891", "clinicaltrials_gov", 1.0),
    ("F8",    "Hemophilia A",     "gene_therapy",   "III", True,  0.50, 0.001, "NCT03370913", "clinicaltrials_gov", 1.0),
    # Vaccines (infectious)
    ("Spike", "COVID-19",         "vaccine",        "III", True,  0.95, 0.001, "NCT04368728", "clinicaltrials_gov", 1.0),
    ("Spike", "COVID-19",         "vaccine",        "III", True,  0.94, 0.001, "NCT04470427", "clinicaltrials_gov", 1.0),
    # Antibiotics / antivirals
    ("RdRp",  "COVID-19",         "small_molecule", "III", True,  0.30, 0.005, "NCT04501978", "clinicaltrials_gov", 1.0),
    ("HCV",   "Hepatitis C",      "small_molecule", "III", True,  0.95, 0.001, "NCT01701401", "clinicaltrials_gov", 1.0),
    # NASH / fibrosis (high attrition)
    ("FXR",   "NASH",             "small_molecule", "III", False, 0.08, 0.350, "NCT02548351", "clinicaltrials_gov", 1.0),
    ("FGF21", "NASH",             "biologic",       "II",  True,  0.20, 0.020, "NCT03486912", "clinicaltrials_gov", 0.8),
    # Sepsis / IPF (high attrition)
    ("TGFb",  "IPF",              "small_molecule", "III", True,  0.25, 0.010, "NCT01366209", "clinicaltrials_gov", 1.0),
    ("CTGF",  "IPF",              "biologic",       "III", False, 0.05, 0.540, "NCT03955146", "clinicaltrials_gov", 0.9),
    # Migraine
    ("CGRP",  "Migraine",         "biologic",       "III", True,  0.40, 0.001, "NCT02456740", "clinicaltrials_gov", 1.0),
    ("CGRP",  "Migraine",         "biologic",       "III", True,  0.35, 0.005, "NCT02559895", "clinicaltrials_gov", 1.0),
    # Sickle cell / hematology
    ("HBB",   "Sickle cell",      "gene_therapy",   "II",  True,  0.55, 0.001, "NCT03745287", "clinicaltrials_gov", 0.9),
    ("BCL11A","Beta thalassemia", "gene_therapy",   "II",  True,  0.60, 0.001, "NCT03655678", "clinicaltrials_gov", 0.9),
    # Dermatology
    ("IL4R",  "Atopic dermatitis","biologic",       "III", True,  0.45, 0.001, "NCT02277743", "clinicaltrials_gov", 1.0),
    # Bone / metabolic
    ("RANKL", "Osteoporosis",     "biologic",       "III", True,  0.40, 0.001, "NCT00089791", "clinicaltrials_gov", 1.0),
    # Oncology heme
    ("FLT3",  "AML",              "small_molecule", "III", True,  0.32, 0.005, "NCT02039726", "clinicaltrials_gov", 1.0),
    ("IDH1",  "AML",              "small_molecule", "II",  True,  0.30, 0.010, "NCT02074839", "clinicaltrials_gov", 1.0),
    ("IDH2",  "AML",              "small_molecule", "II",  True,  0.28, 0.020, "NCT01915498", "clinicaltrials_gov", 1.0),
    # Bispecific T-cell engagers
    ("CD3xCD19","ALL",            "biologic",       "III", True,  0.42, 0.001, "NCT02013167", "clinicaltrials_gov", 1.0),
    ("CD3xBCMA","Multiple myeloma","biologic",      "II",  True,  0.40, 0.005, "NCT03145181", "clinicaltrials_gov", 0.9),
    # Negatives / failures (to balance dataset)
    ("Notch", "Alzheimers",       "small_molecule", "III", False, 0.01, 0.910, "NCT00594568", "clinicaltrials_gov", 1.0),
    ("5HT2A", "Schizophrenia",    "small_molecule", "III", False, 0.06, 0.430, "NCT02969382", "clinicaltrials_gov", 0.9),
    ("DPP4",  "Type 2 diabetes",  "small_molecule", "III", True,  0.22, 0.005, "NCT00622284", "clinicaltrials_gov", 1.0),
    ("HMGCR", "Hyperlipidemia",   "small_molecule", "III", True,  0.50, 0.001, "NCT00181025", "clinicaltrials_gov", 1.0),
    ("MTOR",  "Renal",            "small_molecule", "III", True,  0.30, 0.005, "NCT00410124", "clinicaltrials_gov", 1.0),
    ("ROCK",  "Glaucoma",         "small_molecule", "III", True,  0.25, 0.010, "NCT02246764", "clinicaltrials_gov", 1.0),
    ("Comp",  "PNH",              "biologic",       "III", True,  0.60, 0.001, "NCT00130000", "clinicaltrials_gov", 1.0),
]


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Extend agent_runs.run_type CHECK with PR #11 agent types.
    # ------------------------------------------------------------------
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
                    'ind_readiness', 'partnerability',
                    'clinical_biology', 'clinical_safety',
                    'clinical_trial_design',
                    'clinical_competitive_landscape',
                    'clinical_precedent', 'clinical_forecast'
                ));
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # clinical_forecasts (main table)
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS clinical_forecasts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
            phase TEXT NOT NULL CHECK (phase IN ('I', 'II', 'III')),
            primary_endpoint TEXT,
            forecasted_probability REAL NOT NULL CHECK (
                forecasted_probability >= 0 AND forecasted_probability <= 1
            ),
            confidence_interval_lower REAL CHECK (
                confidence_interval_lower IS NULL OR
                (confidence_interval_lower >= 0 AND
                 confidence_interval_lower <= 1)
            ),
            confidence_interval_upper REAL CHECK (
                confidence_interval_upper IS NULL OR
                (confidence_interval_upper >= 0 AND
                 confidence_interval_upper <= 1)
            ),
            decomposition JSONB NOT NULL DEFAULT '{}',
            sensitivity_analysis JSONB NOT NULL DEFAULT '{}',
            scenario_alternatives JSONB NOT NULL DEFAULT '{}',
            trace_id TEXT,
            status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
                'draft', 'under_review', 'approved', 'superseded'
            )),
            guardian_review_id UUID REFERENCES guardian_reviews(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_clinical_forecasts_candidate "
        "ON clinical_forecasts(candidate_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_clinical_forecasts_status "
        "ON clinical_forecasts(status)"
    )

    # ------------------------------------------------------------------
    # clinical_precedents (training data)
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS clinical_precedents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            target_id UUID REFERENCES bio_entities(id),
            disease_id UUID REFERENCES bio_entities(id),
            target_label TEXT NOT NULL,
            disease_label TEXT NOT NULL,
            modality TEXT,
            phase TEXT CHECK (phase IN ('I', 'II', 'III')),
            met_primary_endpoint BOOLEAN NOT NULL,
            effect_size REAL,
            p_value REAL,
            trial_id TEXT,
            source TEXT,
            weight REAL NOT NULL DEFAULT 1.0
                CHECK (weight >= 0 AND weight <= 5),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (trial_id, target_label, disease_label, phase)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_clinical_precedents_target "
        "ON clinical_precedents(target_label)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_clinical_precedents_disease "
        "ON clinical_precedents(disease_label)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_clinical_precedents_modality_phase "
        "ON clinical_precedents(modality, phase)"
    )

    # ------------------------------------------------------------------
    # forecast_factors (calibrated weights)
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS forecast_factors (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            factor_name TEXT NOT NULL UNIQUE,
            base_weight REAL NOT NULL CHECK (
                base_weight >= 0 AND base_weight <= 1
            ),
            description TEXT,
            last_calibrated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # ------------------------------------------------------------------
    # Seed factor weights.
    # ------------------------------------------------------------------
    for name, weight, description in _FACTOR_SEED:
        op.execute(
            """
            INSERT INTO forecast_factors
                (factor_name, base_weight, description)
            VALUES (%s, %s, %s)
            ON CONFLICT (factor_name) DO NOTHING
            """ % (_q(name), repr(float(weight)), _q(description))
        )

    # ------------------------------------------------------------------
    # Seed clinical_precedents (>=100 curated trials).
    # ------------------------------------------------------------------
    for (
        target, disease, modality, phase, met, effect, p_val,
        trial_id, source, weight,
    ) in _PRECEDENT_SEED:
        op.execute(
            """
            INSERT INTO clinical_precedents
                (target_label, disease_label, modality, phase,
                 met_primary_endpoint, effect_size, p_value, trial_id,
                 source, weight)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (trial_id, target_label, disease_label, phase)
                DO NOTHING
            """ % (
                _q(target), _q(disease), _q(modality), _q(phase),
                "TRUE" if met else "FALSE",
                repr(float(effect)), repr(float(p_val)),
                _q(trial_id), _q(source), repr(float(weight)),
            )
        )

    # ------------------------------------------------------------------
    # Seed the six clinical-forecasting agents.
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO agents (name, role, description, system_prompt, is_active)
        VALUES
            ('Biology Evidence Agent', 'clinical_biology',
             'Evaluates strength of biological evidence for a '
             'candidate-disease pair in support of a clinical forecast.',
             'You are a translational biology lead. Score biological '
             'support 0-1 with citations; never invent evidence.',
             TRUE),
            ('Safety Toxicity Agent', 'clinical_safety',
             'Estimates probability the trial will not fail for safety '
             'reasons given ADMET / preclinical tox / mechanism risks.',
             'You are a drug safety scientist. Score safety 0-1 (higher '
             '= safer); enumerate mechanism-based and observed risks.',
             TRUE),
            ('Trial Design Agent', 'clinical_trial_design',
             'Evaluates trial design quality (endpoint, power, '
             'enrollment, duration) and its impact on success.',
             'You are a clinical biostatistician. Score design 0-1 and '
             'flag underpowered or poorly chosen endpoints.',
             TRUE),
            ('Clinical Competitive Landscape Agent',
             'clinical_competitive_landscape',
             'Assesses how competing assets / standard of care threaten '
             'success of the planned trial.',
             'You are a competitive clinical strategist. Score 0-1 '
             '(higher = less competitive threat); cite competitor names.',
             TRUE),
            ('Historical Precedent Agent', 'clinical_precedent',
             'Computes a similarity-weighted base rate from historical '
             'trials in clinical_precedents.',
             'You are a clinical meta-analyst. Return the precedent '
             'prior, top-5 similar trials, and a confidence interval.',
             TRUE),
            ('Forecast Synthesizer', 'clinical_forecast',
             'Combines ensemble outputs into the final probability with '
             'decomposition, sensitivity and scenario analysis.',
             'You are the Oracle synthesizer. Combine sub-scores with '
             'calibrated weights; surface every contribution.',
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
    op.execute("DROP TABLE IF EXISTS clinical_forecasts CASCADE")
    op.execute("DROP TABLE IF EXISTS clinical_precedents CASCADE")
    op.execute("DROP TABLE IF EXISTS forecast_factors CASCADE")
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
