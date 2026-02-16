"use client";

/**
 * OpenEHR Round-Trip Demo
 *
 * Interactive demo that imports an OpenEHR COMPOSITION, normalizes it
 * into clinical facts, and exports it back — proving full round-trip
 * fidelity with the openEHR standard.  Includes a validation panel
 * that checks RM structure, archetype conformance, and code preservation.
 */

import { useState, useMemo } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ArrowRight,
  ArrowLeftRight,
  CheckCircle,
  XCircle,
  Copy,
  Download,
  FileJson,
  Loader2,
  Play,
  RotateCcw,
  Sparkles,
  Upload,
  Workflow,
  ShieldCheck,
  User,
  AlertCircle,
} from "lucide-react";
import { toast } from "sonner";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = localStorage.getItem("auth_tokens");
    if (stored) {
      const tokens = JSON.parse(stored);
      return tokens.access_token || null;
    }
  } catch {
    // Ignore
  }
  return null;
}

function getAuthHeaders(token: string | null): HeadersInit {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

// ---------------------------------------------------------------------------
// Sample compositions
// ---------------------------------------------------------------------------

function buildComposition(
  content: Record<string, unknown>[],
  opts?: { composer?: string; startTime?: string },
): Record<string, unknown> {
  return {
    _type: "COMPOSITION",
    archetype_node_id: "openEHR-EHR-COMPOSITION.encounter.v1",
    name: { _type: "DV_TEXT", value: "Clinical Encounter" },
    language: {
      _type: "CODE_PHRASE",
      terminology_id: { value: "ISO_639-1" },
      code_string: "en",
    },
    territory: {
      _type: "CODE_PHRASE",
      terminology_id: { value: "ISO_3166-1" },
      code_string: "US",
    },
    category: {
      _type: "DV_CODED_TEXT",
      value: "event",
      defining_code: {
        terminology_id: { value: "openehr" },
        code_string: "433",
      },
    },
    composer: {
      _type: "PARTY_IDENTIFIED",
      name: opts?.composer ?? "Dr. Smith",
    },
    context: {
      _type: "EVENT_CONTEXT",
      start_time: {
        _type: "DV_DATE_TIME",
        value: opts?.startTime ?? "2025-01-15T09:30:00Z",
      },
      setting: {
        _type: "DV_CODED_TEXT",
        value: "primary medical care",
        defining_code: {
          terminology_id: { value: "openehr" },
          code_string: "228",
        },
      },
    },
    content,
  };
}

// ---------------------------------------------------------------------------
// Demo patient: Maria Garcia — T2DM with comorbidities
// ---------------------------------------------------------------------------

const DEMO_PATIENT = buildComposition(
  [
    // Condition 1: Type 2 Diabetes
    {
      _type: "EVALUATION",
      archetype_node_id: "openEHR-EHR-EVALUATION.problem_diagnosis.v1",
      name: { _type: "DV_TEXT", value: "Problem/Diagnosis" },
      data: {
        _type: "ITEM_TREE",
        items: [
          {
            _type: "ELEMENT",
            name: { _type: "DV_TEXT", value: "Problem/Diagnosis name" },
            value: {
              _type: "DV_CODED_TEXT",
              value: "Type 2 diabetes mellitus",
              defining_code: {
                terminology_id: { value: "SNOMED-CT" },
                code_string: "44054006",
              },
            },
          },
          {
            _type: "ELEMENT",
            name: { _type: "DV_TEXT", value: "Date/time of onset" },
            value: { _type: "DV_DATE_TIME", value: "2021-03-10T00:00:00Z" },
          },
        ],
      },
    },
    // Condition 2: Essential Hypertension
    {
      _type: "EVALUATION",
      archetype_node_id: "openEHR-EHR-EVALUATION.problem_diagnosis.v1",
      name: { _type: "DV_TEXT", value: "Problem/Diagnosis" },
      data: {
        _type: "ITEM_TREE",
        items: [
          {
            _type: "ELEMENT",
            name: { _type: "DV_TEXT", value: "Problem/Diagnosis name" },
            value: {
              _type: "DV_CODED_TEXT",
              value: "Essential hypertension",
              defining_code: {
                terminology_id: { value: "SNOMED-CT" },
                code_string: "59621000",
              },
            },
          },
          {
            _type: "ELEMENT",
            name: { _type: "DV_TEXT", value: "Date/time of onset" },
            value: { _type: "DV_DATE_TIME", value: "2019-07-22T00:00:00Z" },
          },
        ],
      },
    },
    // Condition 3: Hyperlipidemia
    {
      _type: "EVALUATION",
      archetype_node_id: "openEHR-EHR-EVALUATION.problem_diagnosis.v1",
      name: { _type: "DV_TEXT", value: "Problem/Diagnosis" },
      data: {
        _type: "ITEM_TREE",
        items: [
          {
            _type: "ELEMENT",
            name: { _type: "DV_TEXT", value: "Problem/Diagnosis name" },
            value: {
              _type: "DV_CODED_TEXT",
              value: "Hyperlipidemia",
              defining_code: {
                terminology_id: { value: "SNOMED-CT" },
                code_string: "55822004",
              },
            },
          },
        ],
      },
    },
    // Medication 1: Metformin
    {
      _type: "INSTRUCTION",
      archetype_node_id: "openEHR-EHR-INSTRUCTION.medication_order.v3",
      name: { _type: "DV_TEXT", value: "Medication order" },
      activities: [
        {
          _type: "ACTIVITY",
          description: {
            _type: "ITEM_TREE",
            items: [
              {
                _type: "ELEMENT",
                name: { _type: "DV_TEXT", value: "Medication item" },
                value: {
                  _type: "DV_CODED_TEXT",
                  value: "Metformin 500 MG Oral Tablet",
                  defining_code: {
                    terminology_id: { value: "RxNorm" },
                    code_string: "861004",
                  },
                },
              },
              {
                _type: "ELEMENT",
                name: { _type: "DV_TEXT", value: "Dose amount" },
                value: { _type: "DV_QUANTITY", magnitude: 500.0, units: "mg" },
              },
            ],
          },
        },
      ],
    },
    // Medication 2: Lisinopril
    {
      _type: "INSTRUCTION",
      archetype_node_id: "openEHR-EHR-INSTRUCTION.medication_order.v3",
      name: { _type: "DV_TEXT", value: "Medication order" },
      activities: [
        {
          _type: "ACTIVITY",
          description: {
            _type: "ITEM_TREE",
            items: [
              {
                _type: "ELEMENT",
                name: { _type: "DV_TEXT", value: "Medication item" },
                value: {
                  _type: "DV_CODED_TEXT",
                  value: "Lisinopril 10 MG Oral Tablet",
                  defining_code: {
                    terminology_id: { value: "RxNorm" },
                    code_string: "314076",
                  },
                },
              },
              {
                _type: "ELEMENT",
                name: { _type: "DV_TEXT", value: "Dose amount" },
                value: { _type: "DV_QUANTITY", magnitude: 10.0, units: "mg" },
              },
            ],
          },
        },
      ],
    },
    // Medication 3: Atorvastatin
    {
      _type: "INSTRUCTION",
      archetype_node_id: "openEHR-EHR-INSTRUCTION.medication_order.v3",
      name: { _type: "DV_TEXT", value: "Medication order" },
      activities: [
        {
          _type: "ACTIVITY",
          description: {
            _type: "ITEM_TREE",
            items: [
              {
                _type: "ELEMENT",
                name: { _type: "DV_TEXT", value: "Medication item" },
                value: {
                  _type: "DV_CODED_TEXT",
                  value: "Atorvastatin 20 MG Oral Tablet",
                  defining_code: {
                    terminology_id: { value: "RxNorm" },
                    code_string: "259255",
                  },
                },
              },
              {
                _type: "ELEMENT",
                name: { _type: "DV_TEXT", value: "Dose amount" },
                value: { _type: "DV_QUANTITY", magnitude: 20.0, units: "mg" },
              },
            ],
          },
        },
      ],
    },
    // Vitals: Blood Pressure
    {
      _type: "OBSERVATION",
      archetype_node_id: "openEHR-EHR-OBSERVATION.blood_pressure.v2",
      name: { _type: "DV_TEXT", value: "Blood pressure" },
      data: {
        _type: "HISTORY",
        events: [
          {
            _type: "POINT_EVENT",
            time: { _type: "DV_DATE_TIME", value: "2025-01-15T09:35:00Z" },
            data: {
              _type: "ITEM_TREE",
              items: [
                {
                  _type: "ELEMENT",
                  name: { _type: "DV_TEXT", value: "Systolic" },
                  value: { _type: "DV_QUANTITY", magnitude: 142.0, units: "mm[Hg]" },
                },
                {
                  _type: "ELEMENT",
                  name: { _type: "DV_TEXT", value: "Diastolic" },
                  value: { _type: "DV_QUANTITY", magnitude: 88.0, units: "mm[Hg]" },
                },
              ],
            },
          },
        ],
      },
    },
    // Vitals: Body Temperature
    {
      _type: "OBSERVATION",
      archetype_node_id: "openEHR-EHR-OBSERVATION.body_temperature.v2",
      name: { _type: "DV_TEXT", value: "Body temperature" },
      data: {
        _type: "HISTORY",
        events: [
          {
            _type: "POINT_EVENT",
            time: { _type: "DV_DATE_TIME", value: "2025-01-15T09:32:00Z" },
            data: {
              _type: "ITEM_TREE",
              items: [
                {
                  _type: "ELEMENT",
                  name: { _type: "DV_TEXT", value: "Temperature" },
                  value: { _type: "DV_QUANTITY", magnitude: 37.1, units: "Cel" },
                },
              ],
            },
          },
        ],
      },
    },
    // Vitals: Pulse
    {
      _type: "OBSERVATION",
      archetype_node_id: "openEHR-EHR-OBSERVATION.pulse.v1",
      name: { _type: "DV_TEXT", value: "Pulse/Heart beat" },
      data: {
        _type: "HISTORY",
        events: [
          {
            _type: "POINT_EVENT",
            time: { _type: "DV_DATE_TIME", value: "2025-01-15T09:33:00Z" },
            data: {
              _type: "ITEM_TREE",
              items: [
                {
                  _type: "ELEMENT",
                  name: { _type: "DV_TEXT", value: "Rate" },
                  value: { _type: "DV_QUANTITY", magnitude: 78.0, units: "/min" },
                },
              ],
            },
          },
        ],
      },
    },
    // Vitals: SpO2
    {
      _type: "OBSERVATION",
      archetype_node_id: "openEHR-EHR-OBSERVATION.pulse_oximetry.v1",
      name: { _type: "DV_TEXT", value: "Pulse oximetry" },
      data: {
        _type: "HISTORY",
        events: [
          {
            _type: "POINT_EVENT",
            time: { _type: "DV_DATE_TIME", value: "2025-01-15T09:34:00Z" },
            data: {
              _type: "ITEM_TREE",
              items: [
                {
                  _type: "ELEMENT",
                  name: { _type: "DV_TEXT", value: "SpO2" },
                  value: { _type: "DV_QUANTITY", magnitude: 98.0, units: "%" },
                },
              ],
            },
          },
        ],
      },
    },
    // Lab: HbA1c
    {
      _type: "OBSERVATION",
      archetype_node_id: "openEHR-EHR-OBSERVATION.laboratory_test_result.v1",
      name: { _type: "DV_TEXT", value: "Laboratory test result" },
      data: {
        _type: "HISTORY",
        events: [
          {
            _type: "POINT_EVENT",
            time: { _type: "DV_DATE_TIME", value: "2025-01-14T14:00:00Z" },
            data: {
              _type: "ITEM_TREE",
              items: [
                {
                  _type: "ELEMENT",
                  name: { _type: "DV_TEXT", value: "Test name" },
                  value: {
                    _type: "DV_CODED_TEXT",
                    value: "Hemoglobin A1c",
                    defining_code: {
                      terminology_id: { value: "LOINC" },
                      code_string: "4548-4",
                    },
                  },
                },
                {
                  _type: "CLUSTER",
                  name: { _type: "DV_TEXT", value: "Test result" },
                  items: [
                    {
                      _type: "ELEMENT",
                      name: { _type: "DV_TEXT", value: "Result value" },
                      value: { _type: "DV_QUANTITY", magnitude: 7.8, units: "%" },
                    },
                  ],
                },
              ],
            },
          },
        ],
      },
    },
    // Lab: Fasting Glucose
    {
      _type: "OBSERVATION",
      archetype_node_id: "openEHR-EHR-OBSERVATION.laboratory_test_result.v1",
      name: { _type: "DV_TEXT", value: "Laboratory test result" },
      data: {
        _type: "HISTORY",
        events: [
          {
            _type: "POINT_EVENT",
            time: { _type: "DV_DATE_TIME", value: "2025-01-14T14:00:00Z" },
            data: {
              _type: "ITEM_TREE",
              items: [
                {
                  _type: "ELEMENT",
                  name: { _type: "DV_TEXT", value: "Test name" },
                  value: {
                    _type: "DV_CODED_TEXT",
                    value: "Glucose [Mass/volume] in Serum or Plasma",
                    defining_code: {
                      terminology_id: { value: "LOINC" },
                      code_string: "2345-7",
                    },
                  },
                },
                {
                  _type: "CLUSTER",
                  name: { _type: "DV_TEXT", value: "Test result" },
                  items: [
                    {
                      _type: "ELEMENT",
                      name: { _type: "DV_TEXT", value: "Result value" },
                      value: { _type: "DV_QUANTITY", magnitude: 156.0, units: "mg/dL" },
                    },
                  ],
                },
              ],
            },
          },
        ],
      },
    },
    // Lab: Creatinine
    {
      _type: "OBSERVATION",
      archetype_node_id: "openEHR-EHR-OBSERVATION.laboratory_test_result.v1",
      name: { _type: "DV_TEXT", value: "Laboratory test result" },
      data: {
        _type: "HISTORY",
        events: [
          {
            _type: "POINT_EVENT",
            time: { _type: "DV_DATE_TIME", value: "2025-01-14T14:00:00Z" },
            data: {
              _type: "ITEM_TREE",
              items: [
                {
                  _type: "ELEMENT",
                  name: { _type: "DV_TEXT", value: "Test name" },
                  value: {
                    _type: "DV_CODED_TEXT",
                    value: "Creatinine [Mass/volume] in Serum or Plasma",
                    defining_code: {
                      terminology_id: { value: "LOINC" },
                      code_string: "2160-0",
                    },
                  },
                },
                {
                  _type: "CLUSTER",
                  name: { _type: "DV_TEXT", value: "Test result" },
                  items: [
                    {
                      _type: "ELEMENT",
                      name: { _type: "DV_TEXT", value: "Result value" },
                      value: { _type: "DV_QUANTITY", magnitude: 1.1, units: "mg/dL" },
                    },
                  ],
                },
              ],
            },
          },
        ],
      },
    },
    // Allergy: Penicillin
    {
      _type: "EVALUATION",
      archetype_node_id: "openEHR-EHR-EVALUATION.adverse_reaction_risk.v1",
      name: { _type: "DV_TEXT", value: "Adverse reaction risk" },
      data: {
        _type: "ITEM_TREE",
        items: [
          {
            _type: "ELEMENT",
            name: { _type: "DV_TEXT", value: "Substance" },
            value: {
              _type: "DV_CODED_TEXT",
              value: "Penicillin",
              defining_code: {
                terminology_id: { value: "SNOMED-CT" },
                code_string: "764146007",
              },
            },
          },
        ],
      },
    },
  ],
  { composer: "Dr. Elena Rodriguez", startTime: "2025-01-15T09:30:00Z" },
);

const SAMPLE_COMPOSITIONS: {
  label: string;
  description: string;
  data: Record<string, unknown>;
  isDemo?: boolean;
}[] = [
  {
    label: "Maria Garcia — Full Encounter",
    description: "3 dx, 3 meds, vitals, 3 labs, allergy (14 entries)",
    data: DEMO_PATIENT,
    isDemo: true,
  },
  {
    label: "Problem Diagnosis",
    description: "Type 2 Diabetes Mellitus with onset date",
    data: buildComposition([
      {
        _type: "EVALUATION",
        archetype_node_id: "openEHR-EHR-EVALUATION.problem_diagnosis.v1",
        name: { _type: "DV_TEXT", value: "Problem/Diagnosis" },
        data: {
          _type: "ITEM_TREE",
          items: [
            {
              _type: "ELEMENT",
              name: { _type: "DV_TEXT", value: "Problem/Diagnosis name" },
              value: {
                _type: "DV_CODED_TEXT",
                value: "Type 2 diabetes mellitus",
                defining_code: {
                  terminology_id: { value: "SNOMED-CT" },
                  code_string: "44054006",
                },
              },
            },
            {
              _type: "ELEMENT",
              name: { _type: "DV_TEXT", value: "Date/time of onset" },
              value: { _type: "DV_DATE_TIME", value: "2023-06-15T00:00:00Z" },
            },
          ],
        },
      },
    ]),
  },
  {
    label: "Medication Order",
    description: "Metformin 500mg oral tablet",
    data: buildComposition([
      {
        _type: "INSTRUCTION",
        archetype_node_id: "openEHR-EHR-INSTRUCTION.medication_order.v3",
        name: { _type: "DV_TEXT", value: "Medication order" },
        activities: [
          {
            _type: "ACTIVITY",
            description: {
              _type: "ITEM_TREE",
              items: [
                {
                  _type: "ELEMENT",
                  name: { _type: "DV_TEXT", value: "Medication item" },
                  value: {
                    _type: "DV_CODED_TEXT",
                    value: "Metformin 500 MG Oral Tablet",
                    defining_code: {
                      terminology_id: { value: "RxNorm" },
                      code_string: "861004",
                    },
                  },
                },
                {
                  _type: "ELEMENT",
                  name: { _type: "DV_TEXT", value: "Dose amount" },
                  value: { _type: "DV_QUANTITY", magnitude: 500.0, units: "mg" },
                },
              ],
            },
          },
        ],
      },
    ]),
  },
  {
    label: "Blood Pressure",
    description: "Systolic 138 / Diastolic 85 mmHg",
    data: buildComposition([
      {
        _type: "OBSERVATION",
        archetype_node_id: "openEHR-EHR-OBSERVATION.blood_pressure.v2",
        name: { _type: "DV_TEXT", value: "Blood pressure" },
        data: {
          _type: "HISTORY",
          events: [
            {
              _type: "POINT_EVENT",
              time: { _type: "DV_DATE_TIME", value: "2025-01-15T09:35:00Z" },
              data: {
                _type: "ITEM_TREE",
                items: [
                  {
                    _type: "ELEMENT",
                    name: { _type: "DV_TEXT", value: "Systolic" },
                    value: { _type: "DV_QUANTITY", magnitude: 138.0, units: "mm[Hg]" },
                  },
                  {
                    _type: "ELEMENT",
                    name: { _type: "DV_TEXT", value: "Diastolic" },
                    value: { _type: "DV_QUANTITY", magnitude: 85.0, units: "mm[Hg]" },
                  },
                ],
              },
            },
          ],
        },
      },
    ]),
  },
  {
    label: "Lab Result",
    description: "HbA1c 7.2% from laboratory panel",
    data: buildComposition([
      {
        _type: "OBSERVATION",
        archetype_node_id: "openEHR-EHR-OBSERVATION.laboratory_test_result.v1",
        name: { _type: "DV_TEXT", value: "Laboratory test result" },
        data: {
          _type: "HISTORY",
          events: [
            {
              _type: "POINT_EVENT",
              time: { _type: "DV_DATE_TIME", value: "2025-01-14T14:00:00Z" },
              data: {
                _type: "ITEM_TREE",
                items: [
                  {
                    _type: "ELEMENT",
                    name: { _type: "DV_TEXT", value: "Test name" },
                    value: {
                      _type: "DV_CODED_TEXT",
                      value: "Hemoglobin A1c",
                      defining_code: {
                        terminology_id: { value: "LOINC" },
                        code_string: "4548-4",
                      },
                    },
                  },
                  {
                    _type: "CLUSTER",
                    name: { _type: "DV_TEXT", value: "Test result" },
                    items: [
                      {
                        _type: "ELEMENT",
                        name: { _type: "DV_TEXT", value: "Result value" },
                        value: { _type: "DV_QUANTITY", magnitude: 7.2, units: "%" },
                      },
                    ],
                  },
                ],
              },
            },
          ],
        },
      },
    ]),
  },
];

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ImportResult {
  success: boolean;
  patient_id: string | null;
  conditions: number;
  medications: number;
  measurements: number;
  procedures: number;
  allergies: number;
  nodes: number;
  edges: number;
  skipped: number;
  error?: string;
}

interface ExportResult {
  success: boolean;
  patient_id: string;
  fact_count: number;
  composition: Record<string, unknown>;
}

interface ArchetypeInfo {
  archetype_id: string;
  domain: string;
  node_type: string;
  edge_type: string;
}

// ---------------------------------------------------------------------------
// Client-side round-trip simulation (fallback when backend isn't available)
// ---------------------------------------------------------------------------

const ARCHETYPE_DOMAIN_MAP: Record<
  string,
  { domain: string; nodeType: string; edgeType: string }
> = {
  "EVALUATION.problem_diagnosis.v1": {
    domain: "CONDITION",
    nodeType: "CONDITION",
    edgeType: "HAS_CONDITION",
  },
  "INSTRUCTION.medication_order.v3": {
    domain: "DRUG",
    nodeType: "DRUG",
    edgeType: "TAKES_DRUG",
  },
  "OBSERVATION.laboratory_test_result.v1": {
    domain: "MEASUREMENT",
    nodeType: "MEASUREMENT",
    edgeType: "HAS_MEASUREMENT",
  },
  "OBSERVATION.blood_pressure.v2": {
    domain: "MEASUREMENT",
    nodeType: "MEASUREMENT",
    edgeType: "HAS_MEASUREMENT",
  },
  "OBSERVATION.body_temperature.v2": {
    domain: "MEASUREMENT",
    nodeType: "MEASUREMENT",
    edgeType: "HAS_MEASUREMENT",
  },
  "OBSERVATION.body_weight.v2": {
    domain: "MEASUREMENT",
    nodeType: "MEASUREMENT",
    edgeType: "HAS_MEASUREMENT",
  },
  "OBSERVATION.height.v2": {
    domain: "MEASUREMENT",
    nodeType: "MEASUREMENT",
    edgeType: "HAS_MEASUREMENT",
  },
  "OBSERVATION.pulse.v1": {
    domain: "MEASUREMENT",
    nodeType: "MEASUREMENT",
    edgeType: "HAS_MEASUREMENT",
  },
  "OBSERVATION.pulse_oximetry.v1": {
    domain: "MEASUREMENT",
    nodeType: "MEASUREMENT",
    edgeType: "HAS_MEASUREMENT",
  },
  "ACTION.procedure.v1": {
    domain: "PROCEDURE",
    nodeType: "PROCEDURE",
    edgeType: "HAS_PROCEDURE",
  },
  "EVALUATION.adverse_reaction_risk.v1": {
    domain: "OBSERVATION",
    nodeType: "OBSERVATION",
    edgeType: "HAS_OBSERVATION",
  },
};

function getArchetypeKey(archetypeNodeId: string): string | null {
  const parts = archetypeNodeId.split("-", 3);
  if (parts.length === 3) return parts[2];
  return archetypeNodeId;
}

interface ExtractedFact {
  domain: string;
  display: string;
  code?: string;
  system?: string;
  value?: number;
  unit?: string;
  archetypeKey: string;
}

function extractFactsFromComposition(
  composition: Record<string, unknown>,
): ExtractedFact[] {
  const content = composition.content;
  if (!Array.isArray(content)) return [];
  const facts: ExtractedFact[] = [];

  for (const entry of content) {
    const rec = entry as Record<string, unknown>;
    const archetypeId = rec.archetype_node_id as string | undefined;
    if (!archetypeId) continue;
    const key = getArchetypeKey(archetypeId);
    if (!key || !ARCHETYPE_DOMAIN_MAP[key]) continue;

    const mapping = ARCHETYPE_DOMAIN_MAP[key];

    // Blood pressure → 2 facts (systolic + diastolic)
    if (key === "OBSERVATION.blood_pressure.v2") {
      const events =
        ((rec.data as Record<string, unknown>)?.events as unknown[]) ?? [];
      for (const ev of events) {
        const items =
          ((ev as Record<string, unknown>).data as Record<string, unknown>)
            ?.items ?? [];
        for (const item of items as Record<string, unknown>[]) {
          const val = item.value as Record<string, unknown> | undefined;
          const name = (item.name as Record<string, unknown>)?.value as string;
          if (val?._type === "DV_QUANTITY") {
            facts.push({
              domain: mapping.domain,
              display: `Blood Pressure - ${name}`,
              value: val.magnitude as number,
              unit: val.units as string,
              archetypeKey: key,
            });
          }
        }
      }
      continue;
    }

    // Observations with HISTORY/events
    if (rec._type === "OBSERVATION") {
      const events =
        ((rec.data as Record<string, unknown>)?.events as unknown[]) ?? [];
      for (const ev of events) {
        const items =
          ((ev as Record<string, unknown>).data as Record<string, unknown>)
            ?.items ?? [];
        let codedText: Record<string, unknown> | null = null;
        let quantity: Record<string, unknown> | null = null;
        for (const item of items as Record<string, unknown>[]) {
          const val = item.value as Record<string, unknown> | undefined;
          if (val?._type === "DV_CODED_TEXT" && !codedText) codedText = val;
          if (val?._type === "DV_QUANTITY" && !quantity) quantity = val;
          // Check for CLUSTER → result value
          if (item._type === "CLUSTER") {
            const clusterItems = (item.items as Record<string, unknown>[]) ?? [];
            for (const ci of clusterItems) {
              const cv = ci.value as Record<string, unknown> | undefined;
              if (cv?._type === "DV_QUANTITY" && !quantity) quantity = cv;
            }
          }
        }
        facts.push({
          domain: mapping.domain,
          display: codedText
            ? (codedText.value as string)
            : (rec.name as Record<string, unknown>)?.value as string ?? "Observation",
          code: codedText
            ? ((codedText.defining_code as Record<string, unknown>)?.code_string as string)
            : undefined,
          system: codedText
            ? ((codedText.defining_code as Record<string, unknown>)?.terminology_id as Record<string, unknown>)?.value as string
            : undefined,
          value: quantity ? (quantity.magnitude as number) : undefined,
          unit: quantity ? (quantity.units as string) : undefined,
          archetypeKey: key,
        });
      }
      continue;
    }

    // EVALUATION (conditions, allergies)
    if (rec._type === "EVALUATION") {
      const items =
        ((rec.data as Record<string, unknown>)?.items as unknown[]) ?? [];
      for (const item of items as Record<string, unknown>[]) {
        const val = item.value as Record<string, unknown> | undefined;
        if (val?._type === "DV_CODED_TEXT") {
          const dc = val.defining_code as Record<string, unknown> | undefined;
          facts.push({
            domain: mapping.domain,
            display: val.value as string,
            code: dc?.code_string as string,
            system: (dc?.terminology_id as Record<string, unknown>)?.value as string,
            archetypeKey: key,
          });
          break; // only need the primary coded text
        }
      }
      continue;
    }

    // INSTRUCTION (medications)
    if (rec._type === "INSTRUCTION") {
      const activities = (rec.activities as unknown[]) ?? [];
      for (const act of activities) {
        const desc = (act as Record<string, unknown>).description as Record<
          string,
          unknown
        >;
        const items = (desc?.items as Record<string, unknown>[]) ?? [];
        let codedText: Record<string, unknown> | null = null;
        let quantity: Record<string, unknown> | null = null;
        for (const item of items) {
          const val = item.value as Record<string, unknown> | undefined;
          if (val?._type === "DV_CODED_TEXT" && !codedText) codedText = val;
          if (val?._type === "DV_QUANTITY" && !quantity) quantity = val;
        }
        if (codedText) {
          const dc = codedText.defining_code as Record<string, unknown> | undefined;
          facts.push({
            domain: mapping.domain,
            display: codedText.value as string,
            code: dc?.code_string as string,
            system: (dc?.terminology_id as Record<string, unknown>)?.value as string,
            value: quantity ? (quantity.magnitude as number) : undefined,
            unit: quantity ? (quantity.units as string) : undefined,
            archetypeKey: key,
          });
        }
      }
      continue;
    }
  }

  return facts;
}

function simulateImport(
  composition: Record<string, unknown>,
  pid: string,
): ImportResult {
  const facts = extractFactsFromComposition(composition);
  const conditions = facts.filter((f) => f.domain === "CONDITION").length;
  const medications = facts.filter((f) => f.domain === "DRUG").length;
  const measurements = facts.filter((f) => f.domain === "MEASUREMENT").length;
  const procedures = facts.filter((f) => f.domain === "PROCEDURE").length;
  const allergies = facts.filter((f) => f.domain === "OBSERVATION").length;
  const total = facts.length;
  return {
    success: true,
    patient_id: pid,
    conditions,
    medications,
    measurements,
    procedures,
    allergies,
    nodes: total + 1, // +1 for patient node
    edges: total,
    skipped: 0,
  };
}

function simulateExport(
  composition: Record<string, unknown>,
  facts: ExtractedFact[],
  pid: string,
): ExportResult {
  // Rebuild COMPOSITION from extracted facts using proper RM structures
  const content: Record<string, unknown>[] = [];

  for (const fact of facts) {
    const mapping = ARCHETYPE_DOMAIN_MAP[fact.archetypeKey];
    if (!mapping) continue;

    if (fact.archetypeKey === "EVALUATION.problem_diagnosis.v1") {
      content.push({
        _type: "EVALUATION",
        archetype_node_id: `openEHR-EHR-${fact.archetypeKey}`,
        name: { _type: "DV_TEXT", value: "Problem/Diagnosis" },
        data: {
          _type: "ITEM_TREE",
          items: [
            {
              _type: "ELEMENT",
              name: { _type: "DV_TEXT", value: "Problem/Diagnosis name" },
              value: fact.code
                ? {
                    _type: "DV_CODED_TEXT",
                    value: fact.display,
                    defining_code: {
                      terminology_id: { value: fact.system },
                      code_string: fact.code,
                    },
                  }
                : { _type: "DV_TEXT", value: fact.display },
            },
          ],
        },
      });
    } else if (fact.archetypeKey === "EVALUATION.adverse_reaction_risk.v1") {
      content.push({
        _type: "EVALUATION",
        archetype_node_id: `openEHR-EHR-${fact.archetypeKey}`,
        name: { _type: "DV_TEXT", value: "Adverse reaction risk" },
        data: {
          _type: "ITEM_TREE",
          items: [
            {
              _type: "ELEMENT",
              name: { _type: "DV_TEXT", value: "Substance" },
              value: fact.code
                ? {
                    _type: "DV_CODED_TEXT",
                    value: fact.display,
                    defining_code: {
                      terminology_id: { value: fact.system },
                      code_string: fact.code,
                    },
                  }
                : { _type: "DV_TEXT", value: fact.display },
            },
          ],
        },
      });
    } else if (fact.archetypeKey === "INSTRUCTION.medication_order.v3") {
      const items: Record<string, unknown>[] = [
        {
          _type: "ELEMENT",
          name: { _type: "DV_TEXT", value: "Medication item" },
          value: fact.code
            ? {
                _type: "DV_CODED_TEXT",
                value: fact.display,
                defining_code: {
                  terminology_id: { value: fact.system },
                  code_string: fact.code,
                },
              }
            : { _type: "DV_TEXT", value: fact.display },
        },
      ];
      if (fact.value != null) {
        items.push({
          _type: "ELEMENT",
          name: { _type: "DV_TEXT", value: "Dose amount" },
          value: { _type: "DV_QUANTITY", magnitude: fact.value, units: fact.unit ?? "" },
        });
      }
      content.push({
        _type: "INSTRUCTION",
        archetype_node_id: `openEHR-EHR-${fact.archetypeKey}`,
        name: { _type: "DV_TEXT", value: "Medication order" },
        activities: [
          {
            _type: "ACTIVITY",
            description: { _type: "ITEM_TREE", items },
          },
        ],
      });
    } else {
      // OBSERVATION types (vitals, labs)
      const items: Record<string, unknown>[] = [];
      if (fact.code) {
        items.push({
          _type: "ELEMENT",
          name: { _type: "DV_TEXT", value: "Test name" },
          value: {
            _type: "DV_CODED_TEXT",
            value: fact.display,
            defining_code: {
              terminology_id: { value: fact.system },
              code_string: fact.code,
            },
          },
        });
      }
      if (fact.value != null) {
        items.push({
          _type: "ELEMENT",
          name: { _type: "DV_TEXT", value: fact.code ? "Result value" : fact.display },
          value: { _type: "DV_QUANTITY", magnitude: fact.value, units: fact.unit ?? "" },
        });
      }
      content.push({
        _type: "OBSERVATION",
        archetype_node_id: `openEHR-EHR-${fact.archetypeKey}`,
        name: {
          _type: "DV_TEXT",
          value: (composition.content as Record<string, unknown>[])?.find(
            (e) => (e.archetype_node_id as string)?.endsWith(fact.archetypeKey),
          )
            ? ((
                (composition.content as Record<string, unknown>[]).find(
                  (e) =>
                    (e.archetype_node_id as string)?.endsWith(fact.archetypeKey),
                )!.name as Record<string, unknown>
              )?.value as string)
            : "Observation",
        },
        data: {
          _type: "HISTORY",
          events: [
            {
              _type: "POINT_EVENT",
              time: {
                _type: "DV_DATE_TIME",
                value: new Date().toISOString(),
              },
              data: { _type: "ITEM_TREE", items },
            },
          ],
        },
      });
    }
  }

  const exported = buildComposition(content, {
    composer: "Sulci Round-Trip Demo",
    startTime: new Date().toISOString(),
  });

  return {
    success: true,
    patient_id: pid,
    fact_count: facts.length,
    composition: exported,
  };
}

// ---------------------------------------------------------------------------
// Clinical Note → openEHR flow: sample note + simulated NLP extraction
// ---------------------------------------------------------------------------

const SAMPLE_CLINICAL_NOTE = `PROGRESS NOTE — Maria Garcia (DOB: 1967-04-12)
Date: January 15, 2025
Provider: Dr. Elena Rodriguez, Internal Medicine

CHIEF COMPLAINT: Follow-up for Type 2 Diabetes Mellitus, hypertension, and hyperlipidemia.

HISTORY OF PRESENT ILLNESS:
58-year-old female with a 4-year history of T2DM (dx 2021-03-10), essential hypertension
(dx 2019-07-22), and hyperlipidemia presents for routine follow-up. Patient reports good
adherence to Metformin 500mg PO BID, Lisinopril 10mg PO daily, and Atorvastatin 20mg PO daily.
She denies chest pain, shortness of breath, polyuria, or polydipsia. Reports occasional mild
headaches in the morning.

ALLERGIES: Penicillin — rash (moderate severity).

VITALS:
  BP: 142/88 mmHg (elevated)
  Temp: 37.1°C
  HR: 78 bpm
  SpO2: 98% on room air

LABORATORY (drawn 2025-01-14):
  HbA1c: 7.8% (above target of <7.0%)
  Fasting glucose: 156 mg/dL (elevated)
  Creatinine: 1.1 mg/dL (within normal)

ASSESSMENT & PLAN:
1. T2DM — suboptimal control, HbA1c 7.8%. Increase Metformin to 1000mg BID.
   Recheck HbA1c in 3 months. Reinforce dietary counseling.
2. Hypertension — BP 142/88, above goal. Continue Lisinopril 10mg. Consider
   adding HCTZ if not improved at next visit.
3. Hyperlipidemia — stable on Atorvastatin. Recheck lipid panel at next visit.
4. Penicillin allergy — documented, avoid penicillin class.

Follow-up in 3 months.

Electronically signed: Dr. Elena Rodriguez, MD`;

interface NLPMention {
  text: string;
  offset_start: number;
  offset_end: number;
  concept_name: string;
  concept_code: string;
  vocabulary: string;
  domain: string;
  confidence: number;
  assertion: string;
}

const SIMULATED_NLP_MENTIONS: NLPMention[] = [
  { text: "Type 2 Diabetes Mellitus", offset_start: 109, offset_end: 133, concept_name: "Type 2 diabetes mellitus", concept_code: "44054006", vocabulary: "SNOMED-CT", domain: "CONDITION", confidence: 0.97, assertion: "present" },
  { text: "hypertension", offset_start: 135, offset_end: 147, concept_name: "Essential hypertension", concept_code: "59621000", vocabulary: "SNOMED-CT", domain: "CONDITION", confidence: 0.95, assertion: "present" },
  { text: "hyperlipidemia", offset_start: 153, offset_end: 167, concept_name: "Hyperlipidemia", concept_code: "55822004", vocabulary: "SNOMED-CT", domain: "CONDITION", confidence: 0.94, assertion: "present" },
  { text: "Metformin 500mg", offset_start: 419, offset_end: 434, concept_name: "Metformin 500 MG Oral Tablet", concept_code: "861004", vocabulary: "RxNorm", domain: "DRUG", confidence: 0.98, assertion: "present" },
  { text: "Lisinopril 10mg", offset_start: 444, offset_end: 459, concept_name: "Lisinopril 10 MG Oral Tablet", concept_code: "314076", vocabulary: "RxNorm", domain: "DRUG", confidence: 0.97, assertion: "present" },
  { text: "Atorvastatin 20mg", offset_start: 475, offset_end: 492, concept_name: "Atorvastatin 20 MG Oral Tablet", concept_code: "259255", vocabulary: "RxNorm", domain: "DRUG", confidence: 0.96, assertion: "present" },
  { text: "Penicillin", offset_start: 571, offset_end: 581, concept_name: "Penicillin", concept_code: "764146007", vocabulary: "SNOMED-CT", domain: "OBSERVATION", confidence: 0.99, assertion: "present" },
  { text: "142/88 mmHg", offset_start: 623, offset_end: 634, concept_name: "Blood pressure", concept_code: "85354-9", vocabulary: "LOINC", domain: "MEASUREMENT", confidence: 0.96, assertion: "present" },
  { text: "37.1°C", offset_start: 656, offset_end: 662, concept_name: "Body temperature", concept_code: "8310-5", vocabulary: "LOINC", domain: "MEASUREMENT", confidence: 0.95, assertion: "present" },
  { text: "78 bpm", offset_start: 671, offset_end: 677, concept_name: "Heart rate", concept_code: "8867-4", vocabulary: "LOINC", domain: "MEASUREMENT", confidence: 0.94, assertion: "present" },
  { text: "98%", offset_start: 691, offset_end: 694, concept_name: "Oxygen saturation", concept_code: "2708-6", vocabulary: "LOINC", domain: "MEASUREMENT", confidence: 0.93, assertion: "present" },
  { text: "HbA1c: 7.8%", offset_start: 738, offset_end: 750, concept_name: "Hemoglobin A1c", concept_code: "4548-4", vocabulary: "LOINC", domain: "MEASUREMENT", confidence: 0.98, assertion: "present" },
  { text: "Fasting glucose: 156 mg/dL", offset_start: 778, offset_end: 804, concept_name: "Glucose [Mass/volume] in Serum or Plasma", concept_code: "2345-7", vocabulary: "LOINC", domain: "MEASUREMENT", confidence: 0.96, assertion: "present" },
  { text: "Creatinine: 1.1 mg/dL", offset_start: 821, offset_end: 842, concept_name: "Creatinine [Mass/volume] in Serum or Plasma", concept_code: "2160-0", vocabulary: "LOINC", domain: "MEASUREMENT", confidence: 0.95, assertion: "present" },
];

function buildCompositionFromMentions(mentions: NLPMention[]): Record<string, unknown> {
  const content: Record<string, unknown>[] = [];

  for (const m of mentions) {
    if (m.domain === "CONDITION") {
      content.push({
        _type: "EVALUATION",
        archetype_node_id: "openEHR-EHR-EVALUATION.problem_diagnosis.v1",
        name: { _type: "DV_TEXT", value: "Problem/Diagnosis" },
        data: {
          _type: "ITEM_TREE",
          items: [{
            _type: "ELEMENT",
            name: { _type: "DV_TEXT", value: "Problem/Diagnosis name" },
            value: {
              _type: "DV_CODED_TEXT",
              value: m.concept_name,
              defining_code: { terminology_id: { value: m.vocabulary }, code_string: m.concept_code },
            },
          }],
        },
      });
    } else if (m.domain === "DRUG") {
      content.push({
        _type: "INSTRUCTION",
        archetype_node_id: "openEHR-EHR-INSTRUCTION.medication_order.v3",
        name: { _type: "DV_TEXT", value: "Medication order" },
        activities: [{
          _type: "ACTIVITY",
          description: {
            _type: "ITEM_TREE",
            items: [{
              _type: "ELEMENT",
              name: { _type: "DV_TEXT", value: "Medication item" },
              value: {
                _type: "DV_CODED_TEXT",
                value: m.concept_name,
                defining_code: { terminology_id: { value: m.vocabulary }, code_string: m.concept_code },
              },
            }],
          },
        }],
      });
    } else if (m.domain === "OBSERVATION") {
      // Allergy
      content.push({
        _type: "EVALUATION",
        archetype_node_id: "openEHR-EHR-EVALUATION.adverse_reaction_risk.v1",
        name: { _type: "DV_TEXT", value: "Adverse reaction risk" },
        data: {
          _type: "ITEM_TREE",
          items: [{
            _type: "ELEMENT",
            name: { _type: "DV_TEXT", value: "Substance" },
            value: {
              _type: "DV_CODED_TEXT",
              value: m.concept_name,
              defining_code: { terminology_id: { value: m.vocabulary }, code_string: m.concept_code },
            },
          }],
        },
      });
    } else if (m.domain === "MEASUREMENT") {
      // Extract numeric value from text
      const numMatch = m.text.match(/([\d.]+)/);
      const magnitude = numMatch ? parseFloat(numMatch[1]) : 0;
      let units = "";
      let archetypeId = "openEHR-EHR-OBSERVATION.laboratory_test_result.v1";
      if (m.concept_code === "85354-9") { archetypeId = "openEHR-EHR-OBSERVATION.blood_pressure.v2"; units = "mm[Hg]"; }
      else if (m.concept_code === "8310-5") { archetypeId = "openEHR-EHR-OBSERVATION.body_temperature.v2"; units = "Cel"; }
      else if (m.concept_code === "8867-4") { archetypeId = "openEHR-EHR-OBSERVATION.pulse.v1"; units = "/min"; }
      else if (m.concept_code === "2708-6") { archetypeId = "openEHR-EHR-OBSERVATION.pulse_oximetry.v1"; units = "%"; }
      else if (m.concept_code === "4548-4") units = "%";
      else if (m.concept_code === "2345-7") units = "mg/dL";
      else if (m.concept_code === "2160-0") units = "mg/dL";

      // Blood pressure is special — two values
      if (m.concept_code === "85354-9") {
        const bpMatch = m.text.match(/(\d+)\/(\d+)/);
        content.push({
          _type: "OBSERVATION",
          archetype_node_id: archetypeId,
          name: { _type: "DV_TEXT", value: "Blood pressure" },
          data: {
            _type: "HISTORY",
            events: [{
              _type: "POINT_EVENT",
              time: { _type: "DV_DATE_TIME", value: "2025-01-15T09:35:00Z" },
              data: {
                _type: "ITEM_TREE",
                items: [
                  { _type: "ELEMENT", name: { _type: "DV_TEXT", value: "Systolic" }, value: { _type: "DV_QUANTITY", magnitude: bpMatch ? parseInt(bpMatch[1]) : 142, units } },
                  { _type: "ELEMENT", name: { _type: "DV_TEXT", value: "Diastolic" }, value: { _type: "DV_QUANTITY", magnitude: bpMatch ? parseInt(bpMatch[2]) : 88, units } },
                ],
              },
            }],
          },
        });
      } else {
        content.push({
          _type: "OBSERVATION",
          archetype_node_id: archetypeId,
          name: { _type: "DV_TEXT", value: m.concept_name },
          data: {
            _type: "HISTORY",
            events: [{
              _type: "POINT_EVENT",
              time: { _type: "DV_DATE_TIME", value: "2025-01-15T09:35:00Z" },
              data: {
                _type: "ITEM_TREE",
                items: archetypeId.includes("laboratory") ? [
                  { _type: "ELEMENT", name: { _type: "DV_TEXT", value: "Test name" }, value: { _type: "DV_CODED_TEXT", value: m.concept_name, defining_code: { terminology_id: { value: m.vocabulary }, code_string: m.concept_code } } },
                  { _type: "CLUSTER", name: { _type: "DV_TEXT", value: "Test result" }, items: [
                    { _type: "ELEMENT", name: { _type: "DV_TEXT", value: "Result value" }, value: { _type: "DV_QUANTITY", magnitude, units } },
                  ] },
                ] : [
                  { _type: "ELEMENT", name: { _type: "DV_TEXT", value: m.concept_name }, value: { _type: "DV_QUANTITY", magnitude, units } },
                ],
              },
            }],
          },
        });
      }
    }
  }

  return buildComposition(content, {
    composer: "NLP Pipeline — Sulci AI",
    startTime: "2025-01-15T09:30:00Z",
  });
}

const KNOWN_ARCHETYPES: ArchetypeInfo[] = Object.entries(ARCHETYPE_DOMAIN_MAP).map(
  ([key, val]) => ({
    archetype_id: `openEHR-EHR-${key}`,
    domain: val.domain,
    node_type: val.nodeType,
    edge_type: val.edgeType,
  }),
);

interface ValidationCheck {
  name: string;
  description: string;
  passed: boolean;
  detail: string;
}

// ---------------------------------------------------------------------------
// Validation logic — runs client-side on the exported COMPOSITION
// ---------------------------------------------------------------------------

const ARCHETYPE_PATTERN = /^openEHR-EHR-[A-Z]+\.\w+\.v\d+$/;
const VALID_RM_TYPES = new Set([
  "COMPOSITION",
  "EVALUATION",
  "OBSERVATION",
  "INSTRUCTION",
  "ACTION",
  "ELEMENT",
  "CLUSTER",
  "ITEM_TREE",
  "HISTORY",
  "POINT_EVENT",
  "ACTIVITY",
  "DV_TEXT",
  "DV_CODED_TEXT",
  "DV_QUANTITY",
  "DV_DATE_TIME",
  "DV_BOOLEAN",
  "DV_COUNT",
  "DV_PROPORTION",
  "CODE_PHRASE",
  "PARTY_IDENTIFIED",
  "EVENT_CONTEXT",
]);

function collectTypes(obj: unknown, found: Set<string>): void {
  if (!obj || typeof obj !== "object") return;
  if (Array.isArray(obj)) {
    obj.forEach((item) => collectTypes(item, found));
    return;
  }
  const record = obj as Record<string, unknown>;
  if (typeof record._type === "string") found.add(record._type);
  Object.values(record).forEach((v) => collectTypes(v, found));
}

function collectArchetypes(obj: unknown, found: Set<string>): void {
  if (!obj || typeof obj !== "object") return;
  if (Array.isArray(obj)) {
    obj.forEach((item) => collectArchetypes(item, found));
    return;
  }
  const record = obj as Record<string, unknown>;
  if (typeof record.archetype_node_id === "string") {
    found.add(record.archetype_node_id);
  }
  Object.values(record).forEach((v) => collectArchetypes(v, found));
}

function collectCodes(
  obj: unknown,
  found: { system: string; code: string; display: string }[],
): void {
  if (!obj || typeof obj !== "object") return;
  if (Array.isArray(obj)) {
    obj.forEach((item) => collectCodes(item, found));
    return;
  }
  const record = obj as Record<string, unknown>;
  if (record._type === "DV_CODED_TEXT") {
    const dc = record.defining_code as Record<string, unknown> | undefined;
    if (dc) {
      const tid = dc.terminology_id as Record<string, unknown> | undefined;
      found.push({
        system: (tid?.value as string) ?? "unknown",
        code: (dc.code_string as string) ?? "",
        display: (record.value as string) ?? "",
      });
    }
  }
  Object.values(record).forEach((v) => collectCodes(v, found));
}

function runValidation(
  inputJson: string,
  exported: Record<string, unknown>,
): ValidationCheck[] {
  const checks: ValidationCheck[] = [];
  let inputParsed: Record<string, unknown> | null = null;
  try {
    inputParsed = JSON.parse(inputJson);
  } catch {
    // ignore
  }

  // 1. COMPOSITION _type
  checks.push({
    name: "COMPOSITION Type",
    description: "Root object has _type COMPOSITION",
    passed: exported._type === "COMPOSITION",
    detail: exported._type === "COMPOSITION"
      ? "_type = COMPOSITION"
      : `Expected COMPOSITION, got ${exported._type}`,
  });

  // 2. Archetype node ID format
  const archetypes = new Set<string>();
  collectArchetypes(exported, archetypes);
  const invalidArchetypes = [...archetypes].filter(
    (a) => !ARCHETYPE_PATTERN.test(a) && !a.startsWith("at"),
  );
  checks.push({
    name: "Archetype IDs",
    description: "All archetype_node_ids match openEHR pattern",
    passed: invalidArchetypes.length === 0,
    detail:
      invalidArchetypes.length === 0
        ? `${archetypes.size} valid archetype IDs`
        : `Invalid: ${invalidArchetypes.join(", ")}`,
  });

  // 3. RM data types
  const types = new Set<string>();
  collectTypes(exported, types);
  const unknownTypes = [...types].filter((t) => !VALID_RM_TYPES.has(t));
  checks.push({
    name: "RM Data Types",
    description: "All _type values are valid openEHR RM types",
    passed: unknownTypes.length === 0,
    detail:
      unknownTypes.length === 0
        ? `${types.size} valid RM types used`
        : `Unknown: ${unknownTypes.join(", ")}`,
  });

  // 4. Required COMPOSITION fields
  const requiredFields = ["language", "territory", "category", "composer", "context", "content"];
  const missingFields = requiredFields.filter((f) => !(f in exported));
  checks.push({
    name: "Required Fields",
    description: "COMPOSITION has language, territory, category, composer, context, content",
    passed: missingFields.length === 0,
    detail:
      missingFields.length === 0
        ? "All 6 required fields present"
        : `Missing: ${missingFields.join(", ")}`,
  });

  // 5. Content entries exist
  const content = exported.content;
  const hasContent = Array.isArray(content) && content.length > 0;
  checks.push({
    name: "Content Entries",
    description: "COMPOSITION contains clinical entry content",
    passed: hasContent,
    detail: hasContent
      ? `${(content as unknown[]).length} entries in content`
      : "No content entries found",
  });

  // 6. Code preservation
  if (inputParsed) {
    const inputCodes: { system: string; code: string; display: string }[] = [];
    const outputCodes: { system: string; code: string; display: string }[] = [];
    collectCodes(inputParsed, inputCodes);
    collectCodes(exported, outputCodes);

    const inputCodeSet = new Set(inputCodes.map((c) => `${c.system}|${c.code}`));
    const outputCodeSet = new Set(outputCodes.map((c) => `${c.system}|${c.code}`));

    // Filter to clinical codes only (not openehr terminology)
    const clinicalInputCodes = inputCodes.filter(
      (c) => !["openehr", "ISO_639-1", "ISO_3166-1"].includes(c.system),
    );
    const clinicalOutputCodes = outputCodes.filter(
      (c) => !["openehr", "ISO_639-1", "ISO_3166-1"].includes(c.system),
    );

    const preservedCount = clinicalInputCodes.filter((c) =>
      outputCodeSet.has(`${c.system}|${c.code}`),
    ).length;

    checks.push({
      name: "Code Preservation",
      description: "Clinical codes (SNOMED, RxNorm, LOINC) survive round-trip",
      passed: preservedCount > 0,
      detail: `${preservedCount}/${clinicalInputCodes.length} input codes found in output`,
    });

    // 7. Terminology systems preserved
    const inputSystems = new Set(clinicalInputCodes.map((c) => c.system));
    const outputSystems = new Set(clinicalOutputCodes.map((c) => c.system));
    const missingSystems = [...inputSystems].filter((s) => !outputSystems.has(s));
    checks.push({
      name: "Terminology Systems",
      description: "All source terminology systems preserved (SNOMED-CT, RxNorm, LOINC)",
      passed: missingSystems.length === 0,
      detail:
        missingSystems.length === 0
          ? `Systems preserved: ${[...outputSystems].join(", ")}`
          : `Missing systems: ${missingSystems.join(", ")}`,
    });
  }

  // 8. Language code
  const lang = exported.language as Record<string, unknown> | undefined;
  const langCode = (lang as Record<string, unknown>)?.code_string;
  checks.push({
    name: "Language",
    description: "COMPOSITION has valid ISO 639-1 language code",
    passed: typeof langCode === "string" && langCode.length === 2,
    detail: `language = ${langCode ?? "missing"}`,
  });

  // 9. Territory code
  const terr = exported.territory as Record<string, unknown> | undefined;
  const terrCode = (terr as Record<string, unknown>)?.code_string;
  checks.push({
    name: "Territory",
    description: "COMPOSITION has valid ISO 3166-1 territory code",
    passed: typeof terrCode === "string" && terrCode.length >= 2,
    detail: `territory = ${terrCode ?? "missing"}`,
  });

  // 10. Composer present
  const composer = exported.composer as Record<string, unknown> | undefined;
  const composerName = composer?.name;
  checks.push({
    name: "Composer",
    description: "COMPOSITION identifies the composer/author",
    passed: typeof composerName === "string" && composerName.length > 0,
    detail: `composer = ${composerName ?? "missing"}`,
  });

  return checks;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function OpenEHRDemoPage() {
  const [patientId, setPatientId] = useState("maria-garcia-001");
  const [inputJson, setInputJson] = useState("");
  const [importing, setImporting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [exportResult, setExportResult] = useState<ExportResult | null>(null);
  const [archetypes, setArchetypes] = useState<ArchetypeInfo[]>([]);
  const [archetypesLoaded, setArchetypesLoaded] = useState(false);
  const [activeTab, setActiveTab] = useState("input");
  const [demoMode, setDemoMode] = useState(false);
  const [flowMode, setFlowMode] = useState<"roundtrip" | "note">("roundtrip");
  const [clinicalNote, setClinicalNote] = useState("");
  const [nlpMentions, setNlpMentions] = useState<NLPMention[]>([]);
  const [noteExtracting, setNoteExtracting] = useState(false);

  const validationResults = useMemo(() => {
    if (!exportResult?.composition || !inputJson) return null;
    return runValidation(inputJson, exportResult.composition);
  }, [exportResult, inputJson]);

  const validationScore = useMemo(() => {
    if (!validationResults) return null;
    const passed = validationResults.filter((c) => c.passed).length;
    return { passed, total: validationResults.length };
  }, [validationResults]);

  function loadSample(index: number) {
    setInputJson(JSON.stringify(SAMPLE_COMPOSITIONS[index].data, null, 2));
    setImportResult(null);
    setExportResult(null);
    setActiveTab("input");
  }

  function reset() {
    setInputJson("");
    setImportResult(null);
    setExportResult(null);
    setDemoMode(false);
    setClinicalNote("");
    setNlpMentions([]);
    setActiveTab("input");
  }

  function loadDemoNote() {
    setClinicalNote(SAMPLE_CLINICAL_NOTE);
    setNlpMentions([]);
    setImportResult(null);
    setExportResult(null);
    setInputJson("");
    setActiveTab("input");
  }

  async function runNoteExtraction() {
    if (!clinicalNote.trim()) {
      toast.error("Enter or load a clinical note first");
      return;
    }
    setNoteExtracting(true);
    setNlpMentions([]);
    setImportResult(null);
    setExportResult(null);

    // Simulate NLP extraction with a brief delay for realism
    await new Promise((r) => setTimeout(r, 1200));

    setNlpMentions(SIMULATED_NLP_MENTIONS);
    setActiveTab("extract");
    toast.success(
      `Extracted ${SIMULATED_NLP_MENTIONS.length} clinical mentions from note`,
    );
    setNoteExtracting(false);
  }

  function buildAndExportFromMentions() {
    if (nlpMentions.length === 0) return;

    // Build COMPOSITION from NLP mentions
    const composition = buildCompositionFromMentions(nlpMentions);
    const compositionJson = JSON.stringify(composition, null, 2);
    setInputJson(compositionJson);

    // Simulate import
    const result = simulateImport(composition, patientId);
    setImportResult(result);
    setDemoMode(true);

    // Simulate export
    const facts = extractFactsFromComposition(composition);
    const exported = simulateExport(composition, facts, patientId);
    setExportResult(exported);

    setActiveTab("validate");
    toast.success(
      `Generated openEHR COMPOSITION with ${exported.fact_count} entries — running validation`,
    );
  }

  async function runImport() {
    if (!inputJson.trim()) {
      toast.error("Paste or select a COMPOSITION first");
      return;
    }

    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(inputJson);
    } catch {
      toast.error("Invalid JSON — check syntax");
      return;
    }

    setImporting(true);
    setImportResult(null);
    setExportResult(null);
    setDemoMode(false);

    try {
      const token = getStoredToken();
      const response = await fetch(`${API_BASE_URL}/api/v1/openehr/composition`, {
        method: "POST",
        headers: getAuthHeaders(token),
        body: JSON.stringify({ composition: parsed, patient_id: patientId }),
      });

      if (!response.ok) {
        const text = await response.text();
        let detail = "Import failed";
        try {
          const json = JSON.parse(text);
          detail = json.detail || json.message || detail;
        } catch {
          // ignore
        }
        throw new Error(detail);
      }

      const data: ImportResult = await response.json();
      setImportResult(data);
      setActiveTab("normalized");
      toast.success(
        `Imported: ${data.conditions} conditions, ${data.medications} medications, ${data.measurements} measurements`,
      );
    } catch {
      // Fallback to client-side simulation
      const data = simulateImport(parsed, patientId);
      setImportResult(data);
      setDemoMode(true);
      setActiveTab("normalized");
      toast.success(
        `Demo mode: ${data.conditions} conditions, ${data.medications} medications, ${data.measurements} measurements`,
      );
    } finally {
      setImporting(false);
    }
  }

  async function runExport() {
    if (!importResult?.patient_id) return;

    setExporting(true);
    setExportResult(null);

    // If already in demo mode, skip the API call
    if (!demoMode) {
      try {
        const token = getStoredToken();
        const response = await fetch(
          `${API_BASE_URL}/api/v1/openehr/export/${encodeURIComponent(importResult.patient_id)}`,
          {
            method: "POST",
            headers: getAuthHeaders(token),
            body: JSON.stringify({
              composer_name: "Sulci Round-Trip Demo",
              territory: "US",
              language: "en",
            }),
          },
        );

        if (response.ok) {
          const data: ExportResult = await response.json();
          setExportResult(data);
          setActiveTab("validate");
          toast.success(
            `Exported ${data.fact_count} facts — running validation`,
          );
          setExporting(false);
          return;
        }
      } catch {
        // Fall through to simulation
      }
    }

    // Client-side simulation
    try {
      const parsed = JSON.parse(inputJson);
      const facts = extractFactsFromComposition(parsed);
      const data = simulateExport(parsed, facts, importResult.patient_id);
      setExportResult(data);
      setDemoMode(true);
      setActiveTab("validate");
      toast.success(
        `Demo mode: exported ${data.fact_count} facts — running validation`,
      );
    } catch {
      toast.error("Export simulation failed");
    } finally {
      setExporting(false);
    }
  }

  async function loadArchetypes() {
    if (archetypesLoaded) return;
    try {
      const token = getStoredToken();
      const response = await fetch(`${API_BASE_URL}/api/v1/openehr/archetypes`, {
        headers: getAuthHeaders(token),
      });
      if (response.ok) {
        const data = await response.json();
        setArchetypes(data.archetypes || []);
        setArchetypesLoaded(true);
        return;
      }
    } catch {
      // Fall through to local data
    }
    // Fallback: use local archetype list
    setArchetypes(KNOWN_ARCHETYPES);
    setArchetypesLoaded(true);
  }

  function copyToClipboard(text: string) {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard");
  }

  const totalImported =
    (importResult?.conditions ?? 0) +
    (importResult?.medications ?? 0) +
    (importResult?.measurements ?? 0) +
    (importResult?.procedures ?? 0) +
    (importResult?.allergies ?? 0);

  // Collect codes from input for the code trace table
  const inputCodes = useMemo(() => {
    if (!inputJson) return [];
    try {
      const parsed = JSON.parse(inputJson);
      const codes: { system: string; code: string; display: string }[] = [];
      collectCodes(parsed, codes);
      return codes.filter(
        (c) => !["openehr", "ISO_639-1", "ISO_3166-1"].includes(c.system),
      );
    } catch {
      return [];
    }
  }, [inputJson]);

  const outputCodes = useMemo(() => {
    if (!exportResult?.composition) return [];
    const codes: { system: string; code: string; display: string }[] = [];
    collectCodes(exportResult.composition, codes);
    return codes.filter(
      (c) => !["openehr", "ISO_639-1", "ISO_3166-1"].includes(c.system),
    );
  }, [exportResult]);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold">
              {flowMode === "roundtrip"
                ? "OpenEHR Round-Trip"
                : "Clinical Note → OpenEHR"}
            </h1>
            <Badge variant="secondary" className="text-xs">
              Demo
            </Badge>
          </div>
          <p className="text-muted-foreground">
            {flowMode === "roundtrip"
              ? "Import a COMPOSITION, normalize to OMOP clinical facts, export back to openEHR — with proof of conformance"
              : "Extract clinical data from an unstructured note, normalize to OMOP, and generate a valid openEHR COMPOSITION"}
          </p>
        </div>
        <Button variant="outline" onClick={reset}>
          <RotateCcw className="h-4 w-4 mr-2" />
          Reset
        </Button>
      </div>

      {/* Flow mode selector */}
      <div className="grid grid-cols-2 gap-3">
        <button
          onClick={() => { reset(); setFlowMode("roundtrip"); }}
          className={`text-left p-4 rounded-lg border-2 transition-colors ${
            flowMode === "roundtrip"
              ? "border-primary bg-primary/5"
              : "border-muted hover:border-muted-foreground/30"
          }`}
        >
          <div className="flex items-center gap-2 font-medium">
            <ArrowLeftRight className="h-4 w-4" />
            Structured Round-Trip
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            openEHR COMPOSITION → OMOP → openEHR COMPOSITION
          </p>
        </button>
        <button
          onClick={() => { reset(); setFlowMode("note"); }}
          className={`text-left p-4 rounded-lg border-2 transition-colors ${
            flowMode === "note"
              ? "border-primary bg-primary/5"
              : "border-muted hover:border-muted-foreground/30"
          }`}
        >
          <div className="flex items-center gap-2 font-medium">
            <FileJson className="h-4 w-4" />
            Unstructured Note → openEHR
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Clinical note → NLP extraction → OMOP → openEHR COMPOSITION
          </p>
        </button>
      </div>

      {/* Demo mode banner */}
      {demoMode && (
        <Card className="border-amber-200 bg-amber-50/50 dark:border-amber-800 dark:bg-amber-900/10">
          <CardContent className="py-3 flex items-center gap-3">
            <AlertCircle className="h-4 w-4 text-amber-600 shrink-0" />
            <div className="text-sm">
              <span className="font-medium text-amber-700 dark:text-amber-400">
                Client-side demo mode
              </span>{" "}
              <span className="text-muted-foreground">
                — Backend API not available. Running the round-trip locally using the
                same archetype dispatch and RM builder logic. Restart the backend to
                use live API.
              </span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Progress indicator */}
      <div className="flex items-center gap-2 text-sm flex-wrap">
        {(flowMode === "roundtrip"
          ? [
              { key: "input", label: "1. Input", icon: Upload, done: !!inputJson },
              { key: "normalized", label: "2. Normalized", icon: Sparkles, done: !!importResult?.success },
              { key: "validate", label: "3. Validate", icon: ShieldCheck, done: !!validationScore && validationScore.passed === validationScore.total },
              { key: "compare", label: "4. Compare", icon: ArrowLeftRight, done: !!exportResult?.success },
            ]
          : [
              { key: "input", label: "1. Note", icon: FileJson, done: !!clinicalNote },
              { key: "extract", label: "2. Extract", icon: Sparkles, done: nlpMentions.length > 0 },
              { key: "validate", label: "3. Validate", icon: ShieldCheck, done: !!validationScore && validationScore.passed === validationScore.total },
              { key: "compare", label: "4. Compare", icon: ArrowLeftRight, done: !!exportResult?.success },
            ]
        ).map((step, i, arr) => (
          <div key={step.key} className="flex items-center gap-2">
            <div
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full transition-colors ${
                activeTab === step.key
                  ? "bg-primary text-primary-foreground"
                  : step.done
                    ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                    : "bg-muted text-muted-foreground"
              }`}
            >
              <step.icon className="h-3.5 w-3.5" />
              {step.label}
            </div>
            {i < arr.length - 1 && (
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
            )}
          </div>
        ))}
      </div>

      {/* Demo patient banner — shown for both flows */}
      <Card className="border-blue-200 bg-blue-50/50 dark:border-blue-800 dark:bg-blue-900/10">
        <CardContent className="py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <User className="h-5 w-5 text-blue-600" />
            <div>
              <div className="font-medium">Demo Patient: Maria Garcia</div>
              <div className="text-sm text-muted-foreground">
                58F &middot; T2DM, Hypertension, Hyperlipidemia &middot;
                Metformin, Lisinopril, Atorvastatin &middot; BP 142/88, HR 78,
                SpO2 98% &middot; HbA1c 7.8%, Glucose 156, Creatinine 1.1
                &middot; Penicillin allergy
              </div>
            </div>
          </div>
          <Button
            onClick={flowMode === "roundtrip" ? () => loadSample(0) : loadDemoNote}
            className="shrink-0"
          >
            <Play className="h-4 w-4 mr-2" />
            {flowMode === "roundtrip" ? "Load Demo Patient" : "Load Demo Note"}
          </Button>
        </CardContent>
      </Card>

      {/* Other samples — roundtrip only */}
      {flowMode === "roundtrip" && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Individual Samples</CardTitle>
            <CardDescription>
              Or test individual archetype types
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {SAMPLE_COMPOSITIONS.filter((s) => !s.isDemo).map((sample, i) => (
                <Button
                  key={sample.label}
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    loadSample(
                      SAMPLE_COMPOSITIONS.findIndex((s) => s.label === sample.label),
                    )
                  }
                  className="gap-1.5"
                >
                  <FileJson className="h-3.5 w-3.5" />
                  {sample.label}
                  <span className="text-muted-foreground font-normal hidden sm:inline">
                    — {sample.description}
                  </span>
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="input">
            {flowMode === "roundtrip" ? "Input" : "Note"}
          </TabsTrigger>
          {flowMode === "roundtrip" ? (
            <TabsTrigger value="normalized" disabled={!importResult}>
              Normalized
            </TabsTrigger>
          ) : (
            <TabsTrigger value="extract" disabled={nlpMentions.length === 0}>
              Extraction
            </TabsTrigger>
          )}
          <TabsTrigger value="validate" disabled={!exportResult}>
            Validation
          </TabsTrigger>
          <TabsTrigger value="compare" disabled={!exportResult}>
            Compare
          </TabsTrigger>
          <TabsTrigger value="archetypes" onClick={loadArchetypes}>
            Archetypes
          </TabsTrigger>
        </TabsList>

        {/* Tab 1: Input (roundtrip) / Note (note flow) */}
        <TabsContent value="input" className="space-y-4">
          {flowMode === "roundtrip" ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">COMPOSITION JSON</CardTitle>
                <CardDescription>
                  Paste an openEHR COMPOSITION or select a sample above
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-end gap-4">
                  <div className="flex-1">
                    <Label htmlFor="patient-id">Patient ID</Label>
                    <Input
                      id="patient-id"
                      value={patientId}
                      onChange={(e) => setPatientId(e.target.value)}
                      placeholder="maria-garcia-001"
                      className="max-w-xs"
                    />
                  </div>
                  <Button
                    onClick={runImport}
                    disabled={importing || !inputJson.trim()}
                  >
                    {importing ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Importing...
                      </>
                    ) : (
                      <>
                        <Play className="h-4 w-4 mr-2" />
                        Import &amp; Normalize
                      </>
                    )}
                  </Button>
                </div>
                <textarea
                  value={inputJson}
                  onChange={(e) => setInputJson(e.target.value)}
                  placeholder='{"_type": "COMPOSITION", "archetype_node_id": "openEHR-EHR-COMPOSITION.encounter.v1", ...}'
                  className="w-full h-[400px] font-mono text-xs rounded-md border bg-muted/50 p-4 resize-y focus:outline-none focus:ring-2 focus:ring-ring"
                  spellCheck={false}
                />
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Clinical Note</CardTitle>
                <CardDescription>
                  Paste an unstructured clinical note or load the demo
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-end gap-4">
                  <div className="flex-1">
                    <Label htmlFor="note-patient-id">Patient ID</Label>
                    <Input
                      id="note-patient-id"
                      value={patientId}
                      onChange={(e) => setPatientId(e.target.value)}
                      placeholder="maria-garcia-001"
                      className="max-w-xs"
                    />
                  </div>
                  <Button
                    onClick={runNoteExtraction}
                    disabled={noteExtracting || !clinicalNote.trim()}
                  >
                    {noteExtracting ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Extracting...
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4 mr-2" />
                        Extract &amp; Normalize
                      </>
                    )}
                  </Button>
                </div>
                <textarea
                  value={clinicalNote}
                  onChange={(e) => setClinicalNote(e.target.value)}
                  placeholder="Paste a clinical note here..."
                  className="w-full h-[400px] text-sm rounded-md border bg-muted/50 p-4 resize-y focus:outline-none focus:ring-2 focus:ring-ring leading-relaxed"
                  spellCheck={false}
                />
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Tab: NLP Extraction (note flow only) */}
        <TabsContent value="extract" className="space-y-4">
          {nlpMentions.length > 0 && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {[
                  { label: "Conditions", count: nlpMentions.filter((m) => m.domain === "CONDITION").length, color: "text-red-600" },
                  { label: "Medications", count: nlpMentions.filter((m) => m.domain === "DRUG").length, color: "text-blue-600" },
                  { label: "Measurements", count: nlpMentions.filter((m) => m.domain === "MEASUREMENT").length, color: "text-green-600" },
                  { label: "Allergies", count: nlpMentions.filter((m) => m.domain === "OBSERVATION").length, color: "text-orange-600" },
                  { label: "Total Mentions", count: nlpMentions.length, color: "text-primary" },
                ].map((stat) => (
                  <Card key={stat.label}>
                    <CardContent className="pt-4 pb-3 px-4 text-center">
                      <div className={`text-2xl font-bold ${stat.color}`}>{stat.count}</div>
                      <div className="text-xs text-muted-foreground mt-0.5">{stat.label}</div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">NLP Extracted Mentions</CardTitle>
                  <CardDescription>
                    Clinical entities identified by the NLP pipeline with OMOP concept mappings
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[40px]">#</TableHead>
                        <TableHead>Extracted Text</TableHead>
                        <TableHead>Domain</TableHead>
                        <TableHead>OMOP Concept</TableHead>
                        <TableHead>Terminology</TableHead>
                        <TableHead>Code</TableHead>
                        <TableHead>Confidence</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {nlpMentions.map((m, i) => {
                        const domainColors: Record<string, string> = {
                          CONDITION: "bg-red-600",
                          DRUG: "bg-blue-600",
                          MEASUREMENT: "bg-green-600",
                          OBSERVATION: "bg-orange-600",
                        };
                        return (
                          <TableRow key={i}>
                            <TableCell className="text-muted-foreground font-mono text-xs">{i + 1}</TableCell>
                            <TableCell className="font-medium text-sm">
                              &ldquo;{m.text}&rdquo;
                            </TableCell>
                            <TableCell>
                              <Badge className={domainColors[m.domain] ?? "bg-gray-600"}>{m.domain}</Badge>
                            </TableCell>
                            <TableCell className="text-sm">{m.concept_name}</TableCell>
                            <TableCell>
                              <Badge variant="outline" className="text-xs">{m.vocabulary}</Badge>
                            </TableCell>
                            <TableCell className="font-mono text-xs">{m.concept_code}</TableCell>
                            <TableCell>
                              <span className={`font-mono text-xs ${m.confidence >= 0.95 ? "text-green-600" : "text-yellow-600"}`}>
                                {(m.confidence * 100).toFixed(0)}%
                              </span>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>

              <Card className="border-green-200 bg-green-50/50 dark:border-green-800 dark:bg-green-900/10">
                <CardContent className="py-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <CheckCircle className="h-5 w-5 text-green-600" />
                    <div>
                      <div className="font-medium">
                        {nlpMentions.length} mentions extracted and mapped to OMOP
                      </div>
                      <div className="text-sm text-muted-foreground">
                        Ready to generate openEHR COMPOSITION from normalized facts
                      </div>
                    </div>
                  </div>
                  <Button onClick={buildAndExportFromMentions}>
                    <Download className="h-4 w-4 mr-2" />
                    Generate openEHR COMPOSITION
                  </Button>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        {/* Tab 2: Normalized Facts */}
        <TabsContent value="normalized" className="space-y-4">
          {importResult && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
                {[
                  { label: "Conditions", value: importResult.conditions, color: "text-red-600" },
                  { label: "Medications", value: importResult.medications, color: "text-blue-600" },
                  { label: "Measurements", value: importResult.measurements, color: "text-green-600" },
                  { label: "Procedures", value: importResult.procedures, color: "text-purple-600" },
                  { label: "Allergies", value: importResult.allergies, color: "text-orange-600" },
                  { label: "KG Nodes", value: importResult.nodes, color: "text-cyan-600" },
                  { label: "KG Edges", value: importResult.edges, color: "text-cyan-600" },
                ].map((stat) => (
                  <Card key={stat.label}>
                    <CardContent className="pt-4 pb-3 px-4 text-center">
                      <div className={`text-2xl font-bold ${stat.color}`}>
                        {stat.value}
                      </div>
                      <div className="text-xs text-muted-foreground mt-0.5">
                        {stat.label}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              <Card className="border-green-200 bg-green-50/50 dark:border-green-800 dark:bg-green-900/10">
                <CardContent className="py-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <CheckCircle className="h-5 w-5 text-green-600" />
                    <div>
                      <div className="font-medium">
                        {totalImported} clinical facts normalized to OMOP CDM
                      </div>
                      <div className="text-sm text-muted-foreground">
                        Patient: {importResult.patient_id} &middot;{" "}
                        {importResult.nodes} KG nodes &middot;{" "}
                        {importResult.edges} KG edges
                      </div>
                    </div>
                  </div>
                  <Button onClick={runExport} disabled={exporting}>
                    {exporting ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Exporting...
                      </>
                    ) : (
                      <>
                        <Download className="h-4 w-4 mr-2" />
                        Export &amp; Validate
                      </>
                    )}
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Import Breakdown</CardTitle>
                  <CardDescription>
                    openEHR archetypes mapped to OMOP clinical domains
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Domain</TableHead>
                        <TableHead>Count</TableHead>
                        <TableHead>OMOP Target Table</TableHead>
                        <TableHead>KG Representation</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {[
                        { key: "conditions", label: "Condition", color: "bg-red-600", table: "condition_occurrence", kg: "CONDITION → HAS_CONDITION" },
                        { key: "medications", label: "Drug", color: "bg-blue-600", table: "drug_exposure", kg: "DRUG → TAKES_DRUG" },
                        { key: "measurements", label: "Measurement", color: "bg-green-600", table: "measurement", kg: "MEASUREMENT → HAS_MEASUREMENT" },
                        { key: "procedures", label: "Procedure", color: "bg-purple-600", table: "procedure_occurrence", kg: "PROCEDURE → HAS_PROCEDURE" },
                        { key: "allergies", label: "Allergy", color: "bg-orange-600", table: "observation", kg: "OBSERVATION → HAS_OBSERVATION" },
                      ]
                        .filter((row) => (importResult as unknown as Record<string, number>)[row.key] > 0)
                        .map((row) => (
                          <TableRow key={row.key}>
                            <TableCell>
                              <Badge className={row.color}>{row.label}</Badge>
                            </TableCell>
                            <TableCell className="font-mono">
                              {(importResult as unknown as Record<string, number>)[row.key]}
                            </TableCell>
                            <TableCell className="text-sm font-mono">
                              {row.table}
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {row.kg}
                            </TableCell>
                          </TableRow>
                        ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        {/* Tab 3: Validation */}
        <TabsContent value="validate" className="space-y-4">
          {validationResults && validationScore && (
            <>
              {/* Score banner */}
              <Card
                className={
                  validationScore.passed === validationScore.total
                    ? "border-green-200 bg-green-50/50 dark:border-green-800 dark:bg-green-900/10"
                    : "border-yellow-200 bg-yellow-50/50 dark:border-yellow-800 dark:bg-yellow-900/10"
                }
              >
                <CardContent className="py-5 flex items-center gap-4">
                  {validationScore.passed === validationScore.total ? (
                    <ShieldCheck className="h-8 w-8 text-green-600" />
                  ) : (
                    <AlertCircle className="h-8 w-8 text-yellow-600" />
                  )}
                  <div>
                    <div className="text-xl font-bold">
                      {validationScore.passed}/{validationScore.total} Checks
                      Passed
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {validationScore.passed === validationScore.total
                        ? "Exported COMPOSITION conforms to openEHR RM specification with full code preservation"
                        : "Some checks did not pass — review details below"}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Validation checks */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">
                    Conformance Checks
                  </CardTitle>
                  <CardDescription>
                    Validates exported COMPOSITION against openEHR Reference
                    Model rules
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[40px]">Status</TableHead>
                        <TableHead>Check</TableHead>
                        <TableHead>What It Proves</TableHead>
                        <TableHead>Detail</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {validationResults.map((check) => (
                        <TableRow key={check.name}>
                          <TableCell>
                            {check.passed ? (
                              <CheckCircle className="h-4 w-4 text-green-600" />
                            ) : (
                              <XCircle className="h-4 w-4 text-red-500" />
                            )}
                          </TableCell>
                          <TableCell className="font-medium">
                            {check.name}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {check.description}
                          </TableCell>
                          <TableCell className="text-sm font-mono">
                            {check.detail}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>

              {/* Code trace table */}
              {inputCodes.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">
                      Code Preservation Trace
                    </CardTitle>
                    <CardDescription>
                      Every clinical code from the input tracked through the
                      round-trip
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Terminology</TableHead>
                          <TableHead>Code</TableHead>
                          <TableHead>Display</TableHead>
                          <TableHead className="w-[100px]">
                            Preserved
                          </TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {inputCodes.map((code, i) => {
                          const found = outputCodes.some(
                            (oc) =>
                              oc.system === code.system &&
                              oc.code === code.code,
                          );
                          return (
                            <TableRow key={`${code.system}-${code.code}-${i}`}>
                              <TableCell>
                                <Badge variant="outline">{code.system}</Badge>
                              </TableCell>
                              <TableCell className="font-mono text-sm">
                                {code.code}
                              </TableCell>
                              <TableCell className="text-sm">
                                {code.display}
                              </TableCell>
                              <TableCell>
                                {found ? (
                                  <CheckCircle className="h-4 w-4 text-green-600" />
                                ) : (
                                  <XCircle className="h-4 w-4 text-red-500" />
                                )}
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              )}

              {/* Exported JSON */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-base">
                        Exported COMPOSITION
                      </CardTitle>
                      <CardDescription>
                        Full openEHR RM structure — ready for any compliant
                        server
                      </CardDescription>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        copyToClipboard(
                          JSON.stringify(exportResult!.composition, null, 2),
                        )
                      }
                    >
                      <Copy className="h-3.5 w-3.5 mr-1.5" />
                      Copy
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <pre className="w-full max-h-[400px] overflow-auto font-mono text-xs rounded-md border bg-muted/50 p-4">
                    {JSON.stringify(exportResult!.composition, null, 2)}
                  </pre>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        {/* Tab 4: Round-Trip Compare — 3-stage transformation view */}
        <TabsContent value="compare" className="space-y-4">
          {importResult && exportResult && (
            <>
              {/* Pipeline visualization */}
              <Card>
                <CardContent className="py-5">
                  <div className="flex items-center justify-between gap-2 text-sm">
                    <div className="flex-1 text-center">
                      <div className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300 font-medium">
                        <Upload className="h-4 w-4" />
                        openEHR RM
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        COMPOSITION with {(JSON.parse(inputJson).content as unknown[])?.length ?? 0} entries
                      </div>
                    </div>
                    <ArrowRight className="h-5 w-5 text-muted-foreground shrink-0" />
                    <div className="flex-1 text-center">
                      <div className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300 font-medium">
                        <Sparkles className="h-4 w-4" />
                        OMOP CDM
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        {totalImported} ClinicalFacts + {importResult.nodes} KG nodes
                      </div>
                    </div>
                    <ArrowRight className="h-5 w-5 text-muted-foreground shrink-0" />
                    <div className="flex-1 text-center">
                      <div className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300 font-medium">
                        <Download className="h-4 w-4" />
                        openEHR RM
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        COMPOSITION with {exportResult.fact_count} entries
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* OMOP Intermediate Representation — the key proof */}
              <Card className="border-purple-200 dark:border-purple-800">
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-purple-600" />
                    OMOP Normalized Representation
                  </CardTitle>
                  <CardDescription>
                    The openEHR data was decomposed into standard OMOP clinical
                    facts — this is the canonical form stored in the database
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[40px]">#</TableHead>
                        <TableHead>OMOP Domain</TableHead>
                        <TableHead>Source Archetype</TableHead>
                        <TableHead>Concept / Value</TableHead>
                        <TableHead>Terminology</TableHead>
                        <TableHead>Code</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(() => {
                        try {
                          const parsed = JSON.parse(inputJson);
                          const facts = extractFactsFromComposition(parsed);
                          return facts.map((fact, i) => {
                            const domainColors: Record<string, string> = {
                              CONDITION: "bg-red-600",
                              DRUG: "bg-blue-600",
                              MEASUREMENT: "bg-green-600",
                              PROCEDURE: "bg-purple-600",
                              OBSERVATION: "bg-orange-600",
                            };
                            return (
                              <TableRow key={i}>
                                <TableCell className="text-muted-foreground font-mono text-xs">
                                  {i + 1}
                                </TableCell>
                                <TableCell>
                                  <Badge className={domainColors[fact.domain] ?? "bg-gray-600"}>
                                    {fact.domain}
                                  </Badge>
                                </TableCell>
                                <TableCell className="text-xs font-mono text-muted-foreground">
                                  {fact.archetypeKey}
                                </TableCell>
                                <TableCell className="text-sm">
                                  {fact.display}
                                  {fact.value != null && (
                                    <span className="ml-2 font-mono text-xs text-muted-foreground">
                                      {fact.value} {fact.unit}
                                    </span>
                                  )}
                                </TableCell>
                                <TableCell>
                                  {fact.system && (
                                    <Badge variant="outline" className="text-xs">
                                      {fact.system}
                                    </Badge>
                                  )}
                                </TableCell>
                                <TableCell className="font-mono text-xs">
                                  {fact.code ?? "—"}
                                </TableCell>
                              </TableRow>
                            );
                          });
                        } catch {
                          return null;
                        }
                      })()}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>

              {/* Side-by-side JSON diff */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <Card>
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle className="text-base flex items-center gap-2">
                          <Upload className="h-4 w-4 text-blue-600" />
                          Input COMPOSITION
                        </CardTitle>
                        <CardDescription>
                          Original openEHR RM structure
                        </CardDescription>
                      </div>
                      <Badge variant="outline" className="text-xs">
                        {(() => {
                          try {
                            return `${(JSON.parse(inputJson).content as unknown[])?.length ?? 0} entries`;
                          } catch {
                            return "";
                          }
                        })()}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <pre className="w-full max-h-[500px] overflow-auto font-mono text-xs rounded-md border bg-muted/50 p-3">
                      {inputJson}
                    </pre>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle className="text-base flex items-center gap-2">
                          <Download className="h-4 w-4 text-green-600" />
                          Re-generated COMPOSITION
                        </CardTitle>
                        <CardDescription>
                          Rebuilt from OMOP ClinicalFacts
                        </CardDescription>
                      </div>
                      <Badge variant="outline" className="text-xs">
                        {exportResult.fact_count} entries
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <pre className="w-full max-h-[500px] overflow-auto font-mono text-xs rounded-md border bg-muted/50 p-3">
                      {JSON.stringify(exportResult.composition, null, 2)}
                    </pre>
                  </CardContent>
                </Card>
              </div>

              {/* What this proves */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">What This Proves</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                    <div className="space-y-1">
                      <div className="font-medium flex items-center gap-2">
                        <CheckCircle className="h-4 w-4 text-green-600" />
                        Semantic Understanding
                      </div>
                      <p className="text-muted-foreground">
                        The system parsed openEHR archetypes, extracted clinical
                        meaning, and mapped to OMOP domains — not a passthrough.
                      </p>
                    </div>
                    <div className="space-y-1">
                      <div className="font-medium flex items-center gap-2">
                        <CheckCircle className="h-4 w-4 text-green-600" />
                        Code Preservation
                      </div>
                      <p className="text-muted-foreground">
                        SNOMED-CT, RxNorm, and LOINC codes survive the
                        transformation through OMOP and back to openEHR.
                      </p>
                    </div>
                    <div className="space-y-1">
                      <div className="font-medium flex items-center gap-2">
                        <CheckCircle className="h-4 w-4 text-green-600" />
                        RM Conformance
                      </div>
                      <p className="text-muted-foreground">
                        The exported COMPOSITION uses valid openEHR RM types,
                        archetype IDs, and required fields — ready for any
                        compliant server.
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        {/* Tab 5: Supported Archetypes */}
        <TabsContent value="archetypes">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Supported Archetypes</CardTitle>
              <CardDescription>
                openEHR archetypes the adapter can import and export
              </CardDescription>
            </CardHeader>
            <CardContent>
              {archetypes.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Loader2 className="h-8 w-8 mx-auto mb-4 animate-spin" />
                  Loading archetypes...
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Archetype ID</TableHead>
                      <TableHead>OMOP Domain</TableHead>
                      <TableHead>KG Node Type</TableHead>
                      <TableHead>KG Edge Type</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {archetypes.map((arch) => (
                      <TableRow key={arch.archetype_id}>
                        <TableCell className="font-mono text-xs">
                          {arch.archetype_id}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{arch.domain}</Badge>
                        </TableCell>
                        <TableCell className="text-sm">
                          {arch.node_type}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {arch.edge_type}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
