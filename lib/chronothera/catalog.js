const formulationGoals = ["Extended-release", "Depot-injection", "Targeted-delivery", "Chronotherapeutic"];
const routesOfAdministration = ["oral", "SC", "IM", "IV", "local", "ocular"];
const regulatoryBodies = ["FDA", "EMA", "PMDA", "TGA", "Health Canada"];
const apis = [
  { name: "Insulin Glargine", modality: "biologic", defaultDoseMg: 10 },
  { name: "Metformin", modality: "small molecule", defaultDoseMg: 500 },
  { name: "Dapagliflozin", modality: "small molecule", defaultDoseMg: 10 },
  { name: "KRAS Peptide Antigen", modality: "peptide vaccine", defaultDoseMg: 1 },
  { name: "TNBC Peptide Antigen", modality: "peptide vaccine", defaultDoseMg: 1 },
  { name: "DryAMD Peptide Candidate", modality: "peptide therapy", defaultDoseMg: 2 },
  { name: "MPOX Immunogen Candidate", modality: "vaccine", defaultDoseMg: 1 },
  { name: "AC-1 Peptide Antigen", modality: "peptide vaccine", defaultDoseMg: 1 },
  { name: "AA-1 Peptide Candidate", modality: "peptide therapy", defaultDoseMg: 2 },
  { name: "Emerging Threat Immunogen", modality: "rapid response platform", defaultDoseMg: 1 }
];
const excipients = [
  { name: "PLGA", defaultPercentage: 35, class: "polymer", releaseUse: "depot/sustained" },
  { name: "PEG", defaultPercentage: 5, class: "polyether", releaseUse: "half-life/formulation" },
  { name: "Chitosan", defaultPercentage: 5, class: "biopolymer", releaseUse: "mucoadhesive/delivery" },
  { name: "Eudragit", defaultPercentage: 12, class: "polymer", releaseUse: "oral modified release" },
  { name: "HPMC", defaultPercentage: 8, class: "cellulose derivative", releaseUse: "matrix/controlled release" }
];
const assetPresets = [
  { id: "peg-insulin-glargine-citrate", label: "PEGylated Insulin Glargine-Citrate", category: "Category A", modality: "biologic/formulation-enhanced", defaultApis: ["Insulin Glargine"], suggestedRoutes: ["SC"], formulationGoals: ["Extended-release", "Depot-injection"], chronotheraFocus: ["half-life extension", "weekly dosing", "stability", "patient-centricity"] },
  { id: "metformin-dapagliflozin-dr", label: "Metformin + Dapagliflozin Delayed-Release Oral Combo", category: "Category A", modality: "oral combination", defaultApis: ["Metformin", "Dapagliflozin"], suggestedRoutes: ["oral"], formulationGoals: ["Extended-release", "Chronotherapeutic"], chronotheraFocus: ["delayed release", "GI tolerability", "adherence", "co-formulation"] },
  { id: "theravac-dryamd-1", label: "TheraVac-DryAMD-1", category: "Category B", modality: "peptide therapy", defaultApis: ["DryAMD Peptide Candidate"], suggestedRoutes: ["local", "ocular"], formulationGoals: ["Targeted-delivery"], chronotheraFocus: ["ocular delivery", "oxidative stress", "local safety", "stability"] },
  { id: "theravac-ac-1", label: "TheraVac-AC-1", category: "Category B", modality: "peptide vaccine", defaultApis: ["AC-1 Peptide Antigen"], suggestedRoutes: ["SC", "IM"], formulationGoals: ["Targeted-delivery", "Extended-release"], chronotheraFocus: ["immune presentation", "stability", "adjuvant compatibility"] },
  { id: "theravac-ac-2", label: "TheraVac-AC-2 KRAS Peptide Vaccine", category: "Category B", modality: "peptide vaccine", defaultApis: ["KRAS Peptide Antigen"], suggestedRoutes: ["SC", "IM"], formulationGoals: ["Targeted-delivery"], chronotheraFocus: ["immune presentation", "stability", "adjuvant compatibility"] },
  { id: "theravac-tnbc-1", label: "TheraVac-TNBC-1", category: "Category C", modality: "peptide vaccine", defaultApis: ["TNBC Peptide Antigen"], suggestedRoutes: ["SC", "IM"], formulationGoals: ["Targeted-delivery"], chronotheraFocus: ["immune presentation", "tumor antigen delivery", "stability"] },
  { id: "theravac-aa-1", label: "TheraVac-AA-1", category: "Category C", modality: "peptide therapy", defaultApis: ["AA-1 Peptide Candidate"], suggestedRoutes: ["SC", "IM"], formulationGoals: ["Extended-release"], chronotheraFocus: ["exposure smoothing", "stability", "patient-centricity"] },
  { id: "mpox-pilot-program", label: "MPOX Pilot Program", category: "Forge Rapid Response Program", modality: "vaccine/therapy-oriented program", defaultApis: ["MPOX Immunogen Candidate"], suggestedRoutes: ["SC", "IM"], formulationGoals: ["Targeted-delivery"], chronotheraFocus: ["rapid preclinical package", "intervention strategy", "clinical forecast support"] },
  { id: "future-emerging-threat", label: "Future Emerging Threat Program", category: "Forge Rapid Response Program", modality: "rapid response platform", defaultApis: ["Emerging Threat Immunogen"], suggestedRoutes: ["SC", "IM"], formulationGoals: ["Targeted-delivery", "Extended-release"], chronotheraFocus: ["rapid formulation screen", "platform readiness", "preclinical package"] }
];
module.exports = { formulationGoals, routesOfAdministration, regulatoryBodies, apis, excipients, assetPresets };
