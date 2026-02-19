// Demo data for visualization pages (survival, geospatial, research)

// ============================================================================
// Survival Analysis Demo Data
// ============================================================================

export interface DemoSurvivalPoint {
  time: number;
  survival_probability: number;
  at_risk: number;
  events: number;
  censored: number;
  ci_lower: number | null;
  ci_upper: number | null;
}

export interface DemoSurvivalCurve {
  cohort_id: string;
  cohort_name: string;
  points: DemoSurvivalPoint[];
  median_survival: number | null;
  events_total: number;
  censored_total: number;
  patients_total: number;
}

export interface DemoSurvivalData {
  curves: DemoSurvivalCurve[];
  log_rank_p_value: number | null;
  hazard_ratio: number | null;
  hazard_ratio_ci: number[] | null;
  time_unit: string;
}

export const DEMO_SURVIVAL_DATA: DemoSurvivalData = {
  curves: [
    {
      cohort_id: "treatment",
      cohort_name: "Treatment Group",
      patients_total: 245,
      events_total: 67,
      censored_total: 178,
      median_survival: 48,
      points: [
        { time: 0, survival_probability: 1.0, at_risk: 245, events: 0, censored: 0, ci_lower: 1.0, ci_upper: 1.0 },
        { time: 3, survival_probability: 0.97, at_risk: 238, events: 4, censored: 3, ci_lower: 0.95, ci_upper: 0.99 },
        { time: 6, survival_probability: 0.94, at_risk: 228, events: 7, censored: 3, ci_lower: 0.91, ci_upper: 0.97 },
        { time: 9, survival_probability: 0.91, at_risk: 218, events: 5, censored: 5, ci_lower: 0.87, ci_upper: 0.95 },
        { time: 12, survival_probability: 0.87, at_risk: 205, events: 8, censored: 5, ci_lower: 0.83, ci_upper: 0.91 },
        { time: 15, survival_probability: 0.84, at_risk: 194, events: 6, censored: 5, ci_lower: 0.79, ci_upper: 0.89 },
        { time: 18, survival_probability: 0.81, at_risk: 183, events: 5, censored: 6, ci_lower: 0.76, ci_upper: 0.86 },
        { time: 21, survival_probability: 0.78, at_risk: 172, events: 4, censored: 7, ci_lower: 0.73, ci_upper: 0.83 },
        { time: 24, survival_probability: 0.75, at_risk: 160, events: 5, censored: 7, ci_lower: 0.69, ci_upper: 0.81 },
        { time: 30, survival_probability: 0.71, at_risk: 142, events: 6, censored: 12, ci_lower: 0.65, ci_upper: 0.77 },
        { time: 36, survival_probability: 0.67, at_risk: 125, events: 5, censored: 12, ci_lower: 0.60, ci_upper: 0.74 },
        { time: 42, survival_probability: 0.63, at_risk: 108, events: 4, censored: 13, ci_lower: 0.56, ci_upper: 0.70 },
        { time: 48, survival_probability: 0.59, at_risk: 90, events: 4, censored: 14, ci_lower: 0.51, ci_upper: 0.67 },
        { time: 54, survival_probability: 0.56, at_risk: 72, events: 3, censored: 15, ci_lower: 0.47, ci_upper: 0.65 },
        { time: 60, survival_probability: 0.53, at_risk: 54, events: 2, censored: 16, ci_lower: 0.43, ci_upper: 0.63 },
      ],
    },
    {
      cohort_id: "control",
      cohort_name: "Control Group",
      patients_total: 238,
      events_total: 94,
      censored_total: 144,
      median_survival: 36,
      points: [
        { time: 0, survival_probability: 1.0, at_risk: 238, events: 0, censored: 0, ci_lower: 1.0, ci_upper: 1.0 },
        { time: 3, survival_probability: 0.95, at_risk: 226, events: 8, censored: 4, ci_lower: 0.92, ci_upper: 0.98 },
        { time: 6, survival_probability: 0.89, at_risk: 210, events: 10, censored: 6, ci_lower: 0.85, ci_upper: 0.93 },
        { time: 9, survival_probability: 0.83, at_risk: 194, events: 9, censored: 7, ci_lower: 0.78, ci_upper: 0.88 },
        { time: 12, survival_probability: 0.77, at_risk: 177, events: 10, censored: 7, ci_lower: 0.72, ci_upper: 0.82 },
        { time: 15, survival_probability: 0.72, at_risk: 163, events: 7, censored: 7, ci_lower: 0.66, ci_upper: 0.78 },
        { time: 18, survival_probability: 0.67, at_risk: 148, events: 8, censored: 7, ci_lower: 0.61, ci_upper: 0.73 },
        { time: 21, survival_probability: 0.62, at_risk: 132, events: 8, censored: 8, ci_lower: 0.55, ci_upper: 0.69 },
        { time: 24, survival_probability: 0.57, at_risk: 117, events: 7, censored: 8, ci_lower: 0.50, ci_upper: 0.64 },
        { time: 30, survival_probability: 0.50, at_risk: 96, events: 9, censored: 12, ci_lower: 0.43, ci_upper: 0.57 },
        { time: 36, survival_probability: 0.44, at_risk: 78, events: 6, censored: 12, ci_lower: 0.37, ci_upper: 0.51 },
        { time: 42, survival_probability: 0.39, at_risk: 61, events: 5, censored: 12, ci_lower: 0.31, ci_upper: 0.47 },
        { time: 48, survival_probability: 0.35, at_risk: 46, events: 3, censored: 12, ci_lower: 0.27, ci_upper: 0.43 },
        { time: 54, survival_probability: 0.31, at_risk: 33, events: 2, censored: 11, ci_lower: 0.22, ci_upper: 0.40 },
        { time: 60, survival_probability: 0.28, at_risk: 22, events: 2, censored: 9, ci_lower: 0.18, ci_upper: 0.38 },
      ],
    },
  ],
  log_rank_p_value: 0.0023,
  hazard_ratio: 0.68,
  hazard_ratio_ci: [0.52, 0.89],
  time_unit: "months",
};

// ============================================================================
// Geospatial Demo Data
// ============================================================================

export interface DemoGeospatialRegion {
  region_id: string;
  region_name: string;
  state_code: string | null;
  latitude: number;
  longitude: number;
  metric_value: number;
  metric_label: string;
  population: number;
  patient_count: number;
  confidence_interval: number[] | null;
  trend: string | null;
}

export interface DemoGeospatialData {
  regions: DemoGeospatialRegion[];
  metric_name: string;
  metric_unit: string;
  min_value: number;
  max_value: number;
  national_average: number;
  time_period: string;
}

const stateData: [string, string, string, number, number, number, number, number, string][] = [
  // [id, name, code, lat, lon, prevalence, population, patients, trend]
  ["al", "Alabama", "AL", 32.8, -86.8, 13.6, 5024279, 68330, "increasing"],
  ["ak", "Alaska", "AK", 63.3, -152.0, 8.4, 733391, 6160, "stable"],
  ["az", "Arizona", "AZ", 34.0, -111.1, 12.1, 7151502, 86540, "increasing"],
  ["ar", "Arkansas", "AR", 35.2, -91.8, 13.3, 3011524, 40053, "increasing"],
  ["ca", "California", "CA", 36.8, -119.4, 10.5, 39538223, 415150, "stable"],
  ["co", "Colorado", "CO", 39.1, -105.4, 7.4, 5773714, 42725, "decreasing"],
  ["ct", "Connecticut", "CT", 41.6, -72.7, 9.3, 3605944, 33535, "stable"],
  ["de", "Delaware", "DE", 38.9, -75.5, 11.2, 989948, 11087, "stable"],
  ["fl", "Florida", "FL", 27.6, -81.5, 12.7, 21538187, 273534, "increasing"],
  ["ga", "Georgia", "GA", 32.2, -83.4, 12.5, 10711908, 133899, "increasing"],
  ["hi", "Hawaii", "HI", 19.9, -155.6, 10.8, 1455271, 15716, "stable"],
  ["id", "Idaho", "ID", 44.1, -114.7, 8.9, 1839106, 16367, "stable"],
  ["il", "Illinois", "IL", 40.3, -89.0, 10.9, 12812508, 139656, "stable"],
  ["in", "Indiana", "IN", 40.3, -86.1, 12.6, 6732219, 84825, "increasing"],
  ["ia", "Iowa", "IA", 41.9, -93.1, 9.7, 3190369, 30946, "stable"],
  ["ks", "Kansas", "KS", 39.0, -98.5, 10.8, 2937880, 31729, "stable"],
  ["ky", "Kentucky", "KY", 37.8, -84.3, 14.2, 4505836, 63982, "increasing"],
  ["la", "Louisiana", "LA", 31.2, -92.3, 13.8, 4657757, 64277, "increasing"],
  ["me", "Maine", "ME", 45.3, -69.4, 10.1, 1362359, 13759, "stable"],
  ["md", "Maryland", "MD", 39.0, -76.6, 10.6, 6177224, 65478, "stable"],
  ["ma", "Massachusetts", "MA", 42.4, -71.4, 9.0, 7029917, 63269, "decreasing"],
  ["mi", "Michigan", "MI", 44.3, -84.5, 11.5, 10077331, 115889, "stable"],
  ["mn", "Minnesota", "MN", 46.7, -94.7, 8.3, 5706494, 47363, "decreasing"],
  ["ms", "Mississippi", "MS", 32.7, -89.7, 14.7, 2961279, 43530, "increasing"],
  ["mo", "Missouri", "MO", 38.5, -91.8, 11.7, 6154913, 72012, "stable"],
  ["mt", "Montana", "MT", 46.8, -110.4, 8.6, 1084225, 9324, "stable"],
  ["ne", "Nebraska", "NE", 41.1, -98.3, 9.4, 1961504, 18438, "stable"],
  ["nv", "Nevada", "NV", 38.8, -116.4, 10.7, 3104614, 33219, "stable"],
  ["nh", "New Hampshire", "NH", 43.5, -71.6, 8.8, 1377529, 12121, "decreasing"],
  ["nj", "New Jersey", "NJ", 40.3, -74.5, 10.2, 9288994, 94747, "stable"],
  ["nm", "New Mexico", "NM", 34.5, -105.9, 12.8, 2117522, 27104, "stable"],
  ["ny", "New York", "NY", 43.3, -74.2, 10.5, 20201249, 212113, "stable"],
  ["nc", "North Carolina", "NC", 35.8, -79.0, 11.8, 10439388, 123184, "increasing"],
  ["nd", "North Dakota", "ND", 47.5, -101.0, 9.1, 779094, 7089, "stable"],
  ["oh", "Ohio", "OH", 40.4, -82.9, 11.7, 11799448, 138073, "stable"],
  ["ok", "Oklahoma", "OK", 35.0, -97.1, 13.1, 3959353, 51867, "increasing"],
  ["or", "Oregon", "OR", 44.0, -120.5, 9.6, 4237256, 40677, "stable"],
  ["pa", "Pennsylvania", "PA", 41.2, -77.2, 10.8, 13002700, 140429, "stable"],
  ["ri", "Rhode Island", "RI", 41.6, -71.5, 9.5, 1097379, 10425, "stable"],
  ["sc", "South Carolina", "SC", 34.0, -81.0, 12.9, 5118425, 66027, "increasing"],
  ["sd", "South Dakota", "SD", 43.9, -99.4, 9.3, 886667, 8246, "stable"],
  ["tn", "Tennessee", "TN", 35.5, -86.6, 13.4, 6910840, 92605, "increasing"],
  ["tx", "Texas", "TX", 31.9, -99.9, 12.1, 29145505, 352660, "increasing"],
  ["ut", "Utah", "UT", 39.3, -111.1, 7.8, 3271616, 25518, "decreasing"],
  ["vt", "Vermont", "VT", 44.0, -72.7, 8.5, 643077, 5466, "decreasing"],
  ["va", "Virginia", "VA", 37.4, -78.7, 10.3, 8631393, 88903, "stable"],
  ["wa", "Washington", "WA", 47.8, -120.7, 9.2, 7614893, 70057, "stable"],
  ["wv", "West Virginia", "WV", 38.6, -80.6, 15.7, 1793716, 28161, "increasing"],
  ["wi", "Wisconsin", "WI", 43.8, -88.8, 9.6, 5893718, 56579, "stable"],
  ["wy", "Wyoming", "WY", 43.1, -107.6, 8.7, 576851, 5018, "stable"],
];

export const DEMO_GEOSPATIAL_DATA: DemoGeospatialData = {
  regions: stateData.map(([id, name, code, lat, lon, prevalence, pop, patients, trend]) => ({
    region_id: id,
    region_name: name,
    state_code: code,
    latitude: lat,
    longitude: lon,
    metric_value: prevalence,
    metric_label: `${prevalence}%`,
    population: pop,
    patient_count: patients,
    confidence_interval: [prevalence - 0.8, prevalence + 0.8],
    trend,
  })),
  metric_name: "Diabetes Prevalence",
  metric_unit: "%",
  min_value: 7.4,
  max_value: 15.7,
  national_average: 11.3,
  time_period: "2024",
};

// ============================================================================
// Forest Plot Demo Data
// ============================================================================

export interface DemoForestPlotStudy {
  study_id: string;
  study_name: string;
  year: number;
  effect_size: number;
  ci_lower: number;
  ci_upper: number;
  weight: number;
  sample_size: number;
  events_treatment: number | null;
  events_control: number | null;
  n_treatment: number | null;
  n_control: number | null;
}

export interface DemoForestPlotData {
  studies: DemoForestPlotStudy[];
  pooled_effect: number;
  pooled_ci_lower: number;
  pooled_ci_upper: number;
  heterogeneity_i2: number;
  heterogeneity_q: number;
  heterogeneity_p: number;
  effect_measure: string;
  null_value: number;
}

export const DEMO_FOREST_PLOT_DATA: DemoForestPlotData = {
  studies: [
    { study_id: "s1", study_name: "ACCORD (2010)", year: 2010, effect_size: 0.90, ci_lower: 0.78, ci_upper: 1.04, weight: 18.2, sample_size: 10251, events_treatment: 352, events_control: 371, n_treatment: 5128, n_control: 5123 },
    { study_id: "s2", study_name: "ADVANCE (2008)", year: 2008, effect_size: 0.94, ci_lower: 0.84, ci_upper: 1.06, weight: 16.4, sample_size: 11140, events_treatment: 557, events_control: 590, n_treatment: 5571, n_control: 5569 },
    { study_id: "s3", study_name: "UKPDS (1998)", year: 1998, effect_size: 0.84, ci_lower: 0.71, ci_upper: 1.00, weight: 12.3, sample_size: 3867, events_treatment: 169, events_control: 201, n_treatment: 2729, n_control: 1138 },
    { study_id: "s4", study_name: "VADT (2009)", year: 2009, effect_size: 0.88, ci_lower: 0.74, ci_upper: 1.05, weight: 10.8, sample_size: 1791, events_treatment: 102, events_control: 115, n_treatment: 892, n_control: 899 },
    { study_id: "s5", study_name: "EMPA-REG (2015)", year: 2015, effect_size: 0.86, ci_lower: 0.74, ci_upper: 0.99, weight: 14.1, sample_size: 7020, events_treatment: 490, events_control: 282, n_treatment: 4687, n_control: 2333 },
    { study_id: "s6", study_name: "LEADER (2016)", year: 2016, effect_size: 0.87, ci_lower: 0.78, ci_upper: 0.97, weight: 15.7, sample_size: 9340, events_treatment: 608, events_control: 694, n_treatment: 4668, n_control: 4672 },
    { study_id: "s7", study_name: "SUSTAIN-6 (2016)", year: 2016, effect_size: 0.74, ci_lower: 0.58, ci_upper: 0.95, weight: 6.8, sample_size: 3297, events_treatment: 108, events_control: 146, n_treatment: 1648, n_control: 1649 },
    { study_id: "s8", study_name: "CANVAS (2017)", year: 2017, effect_size: 0.86, ci_lower: 0.75, ci_upper: 0.97, weight: 5.7, sample_size: 10142, events_treatment: 585, events_control: 426, n_treatment: 5795, n_control: 4347 },
  ],
  pooled_effect: 0.87,
  pooled_ci_lower: 0.82,
  pooled_ci_upper: 0.93,
  heterogeneity_i2: 18.4,
  heterogeneity_q: 8.58,
  heterogeneity_p: 0.284,
  effect_measure: "OR",
  null_value: 1.0,
};

// ============================================================================
// Volcano Plot Demo Data
// ============================================================================

export interface DemoVolcanoPoint {
  id: string;
  name: string;
  log_fold_change: number;
  neg_log_p_value: number;
  p_value: number;
  significant: boolean;
  direction: string;
  category: string | null;
}

export interface DemoVolcanoData {
  points: DemoVolcanoPoint[];
  fc_threshold: number;
  p_threshold: number;
  total_features: number;
  significant_up: number;
  significant_down: number;
  comparison: string;
}

function generateVolcanoPoints(): DemoVolcanoPoint[] {
  // Deterministic pseudo-random based on seed
  let seed = 42;
  function rand() { seed = (seed * 16807 + 0) % 2147483647; return seed / 2147483647; }

  const biomarkers = [
    "HbA1c", "TNF-alpha", "IL-6", "CRP", "Adiponectin", "Leptin", "Resistin",
    "GLP-1", "Insulin", "Glucagon", "VEGF", "PDGF", "IGF-1", "FGF-21",
    "Fetuin-A", "RBP4", "MCP-1", "ICAM-1", "VCAM-1", "E-selectin",
    "PAI-1", "Fibrinogen", "vWF", "Thrombomodulin", "sRAGE",
    "NT-proBNP", "Troponin-I", "Galectin-3", "sST2", "GDF-15",
    "Cystatin-C", "NGAL", "KIM-1", "TIMP-2", "IGFBP7",
    "miR-21", "miR-155", "miR-126", "miR-223", "miR-146a",
    "HMGB1", "Calprotectin", "LBP", "sCD163", "Neopterin",
    "FABP4", "PAPP-A", "Osteopontin", "Periostin", "YKL-40",
    "Angptl4", "PCSK9", "Lp(a)", "sdLDL", "oxLDL",
    "8-OHdG", "MDA", "SOD", "GPx", "Catalase",
  ];

  return biomarkers.map((name, i) => {
    const lfc = (rand() - 0.5) * 5;
    const pval = Math.pow(10, -(rand() * 4.5 + 0.2));
    const negLogP = -Math.log10(pval);
    const sig = Math.abs(lfc) > 1.0 && pval < 0.05;
    return {
      id: `feat_${i}`,
      name,
      log_fold_change: Math.round(lfc * 100) / 100,
      neg_log_p_value: Math.round(negLogP * 100) / 100,
      p_value: pval,
      significant: sig,
      direction: lfc > 0 ? "up" : "down",
      category: i < 20 ? "Inflammatory" : i < 35 ? "Cardiovascular" : i < 45 ? "Epigenetic" : "Metabolic",
    };
  });
}

const volcanoPoints = generateVolcanoPoints();

export const DEMO_VOLCANO_DATA: DemoVolcanoData = {
  points: volcanoPoints,
  fc_threshold: 1.0,
  p_threshold: 0.05,
  total_features: volcanoPoints.length,
  significant_up: volcanoPoints.filter(p => p.significant && p.direction === "up").length,
  significant_down: volcanoPoints.filter(p => p.significant && p.direction === "down").length,
  comparison: "Treatment vs. Control (Biomarker Panel)",
};

// ============================================================================
// Study Timeline Demo Data
// ============================================================================

export interface DemoTimelineMilestone {
  name: string;
  date: string;
}

export interface DemoTimelineEvent {
  id: string;
  name: string;
  start_date: string;
  end_date: string | null;
  category: string;
  status: string;
  progress: number;
  milestones: DemoTimelineMilestone[];
  dependencies: string[];
}

export interface DemoTimelineData {
  events: DemoTimelineEvent[];
  study_name: string;
  study_start: string;
  study_end: string | null;
  categories: string[];
}

export const DEMO_TIMELINE_DATA: DemoTimelineData = {
  study_name: "PRECISION-DM Phase III Clinical Trial",
  study_start: "2023-01-15",
  study_end: "2026-06-30",
  categories: ["Planning", "Regulatory", "Enrollment", "Treatment", "Follow-up", "Analysis"],
  events: [
    {
      id: "e1", name: "Protocol Development", start_date: "2023-01-15", end_date: "2023-06-30",
      category: "Planning", status: "completed", progress: 100,
      milestones: [{ name: "Protocol Finalized", date: "2023-05-15" }, { name: "SAP Approved", date: "2023-06-20" }],
      dependencies: [],
    },
    {
      id: "e2", name: "Regulatory Submission", start_date: "2023-04-01", end_date: "2023-09-15",
      category: "Regulatory", status: "completed", progress: 100,
      milestones: [{ name: "IND Filed", date: "2023-04-15" }, { name: "IRB Approval", date: "2023-08-01" }, { name: "FDA Clearance", date: "2023-09-10" }],
      dependencies: ["e1"],
    },
    {
      id: "e3", name: "Site Activation", start_date: "2023-07-01", end_date: "2023-12-31",
      category: "Planning", status: "completed", progress: 100,
      milestones: [{ name: "First Site Activated", date: "2023-08-15" }, { name: "All 24 Sites Active", date: "2023-12-01" }],
      dependencies: ["e2"],
    },
    {
      id: "e4", name: "Patient Enrollment", start_date: "2023-09-01", end_date: "2024-12-31",
      category: "Enrollment", status: "completed", progress: 100,
      milestones: [{ name: "First Patient In", date: "2023-09-20" }, { name: "50% Enrolled", date: "2024-06-15" }, { name: "Last Patient In", date: "2024-11-28" }],
      dependencies: ["e3"],
    },
    {
      id: "e5", name: "Treatment Phase", start_date: "2023-10-01", end_date: "2025-06-30",
      category: "Treatment", status: "in_progress", progress: 78,
      milestones: [{ name: "Interim Analysis", date: "2024-12-01" }, { name: "DSMB Review", date: "2025-03-15" }],
      dependencies: ["e4"],
    },
    {
      id: "e6", name: "Follow-up Period", start_date: "2025-01-01", end_date: "2025-12-31",
      category: "Follow-up", status: "in_progress", progress: 35,
      milestones: [{ name: "6-Month Follow-up Complete", date: "2025-06-30" }],
      dependencies: ["e5"],
    },
    {
      id: "e7", name: "Data Lock & Analysis", start_date: "2025-10-01", end_date: "2026-03-31",
      category: "Analysis", status: "planned", progress: 0,
      milestones: [{ name: "Database Lock", date: "2026-01-15" }, { name: "Primary Analysis Complete", date: "2026-03-01" }],
      dependencies: ["e6"],
    },
    {
      id: "e8", name: "Publication & Submission", start_date: "2026-02-01", end_date: "2026-06-30",
      category: "Analysis", status: "planned", progress: 0,
      milestones: [{ name: "Manuscript Submitted", date: "2026-04-15" }, { name: "NDA Submission", date: "2026-06-15" }],
      dependencies: ["e7"],
    },
  ],
};
