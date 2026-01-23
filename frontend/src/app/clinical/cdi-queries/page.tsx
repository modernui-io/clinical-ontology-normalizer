"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  ArrowLeft,
  ClipboardList,
  Send,
  Plus,
  FileText,
  AlertCircle,
} from "lucide-react";

type QueryType = "specificity" | "clinical_significance" | "present_on_admission" | "link_condition" | "complication";
type QueryStatus = "draft" | "sent" | "answered" | "expired";
type ImpactType = "hcc" | "drg" | "quality" | "severity";

interface CDIQueryTemplate {
  id: string;
  type: QueryType;
  label: string;
  template: string;
  impacts: ImpactType[];
}

interface CDIQuery {
  id: string;
  patient_id: string;
  encounter_id: string;
  provider: string;
  query_type: QueryType;
  condition: string;
  icd10_current: string;
  icd10_target: string;
  query_text: string;
  status: QueryStatus;
  created_at: string;
  impacts: ImpactType[];
  raf_impact: number | null;
}

const queryTemplates: CDIQueryTemplate[] = [
  {
    id: "t1", type: "specificity", label: "Code Specificity",
    template: "Based on the clinical documentation, [CONDITION] is currently coded as [CURRENT_CODE]. Could you please clarify [SPECIFICITY_QUESTION] to allow more specific coding to [TARGET_CODE]?",
    impacts: ["hcc", "drg"],
  },
  {
    id: "t2", type: "clinical_significance", label: "Clinical Significance",
    template: "The documentation indicates [FINDING]. Could you please document the clinical significance of this finding and any treatment/monitoring plan, so it may be appropriately coded?",
    impacts: ["hcc", "severity"],
  },
  {
    id: "t3", type: "present_on_admission", label: "Present on Admission",
    template: "Could you please clarify whether [CONDITION] was present on admission or developed during the hospital stay? This impacts the POA indicator for coding.",
    impacts: ["drg", "quality"],
  },
  {
    id: "t4", type: "link_condition", label: "Causal Relationship",
    template: "The patient has both [CONDITION_A] and [CONDITION_B]. Could you please document whether there is a causal or contributory relationship between these conditions?",
    impacts: ["hcc", "drg"],
  },
  {
    id: "t5", type: "complication", label: "Complication/Comorbidity",
    template: "Could you please clarify whether [CONDITION] represents a complication of [PROCEDURE/CONDITION] or a pre-existing comorbidity? This distinction affects coding specificity.",
    impacts: ["drg", "quality"],
  },
];

const mockQueries: CDIQuery[] = [
  {
    id: "q1", patient_id: "P-12345", encounter_id: "E-98765", provider: "Dr. Smith",
    query_type: "specificity", condition: "Diabetes mellitus",
    icd10_current: "E11.9", icd10_target: "E11.65",
    query_text: "Based on the clinical documentation, Type 2 Diabetes is currently coded as E11.9 (without complications). The lab results show eGFR of 42 and urine albumin/creatinine ratio of 350. Could you please document whether the patient has diabetic nephropathy to allow more specific coding to E11.65?",
    status: "sent", created_at: "2025-01-12", impacts: ["hcc", "drg"], raf_impact: 0.318,
  },
  {
    id: "q2", patient_id: "P-12345", encounter_id: "E-98765", provider: "Dr. Smith",
    query_type: "clinical_significance", condition: "Protein-calorie malnutrition",
    icd10_current: "", icd10_target: "E44.0",
    query_text: "The documentation indicates BMI of 17.2, albumin of 2.8, and unintentional weight loss of 12 lbs over 3 months. Could you please document the clinical significance of these findings and confirm if the patient has protein-calorie malnutrition, so it may be appropriately coded?",
    status: "answered", created_at: "2025-01-10", impacts: ["hcc", "severity"], raf_impact: 0.545,
  },
  {
    id: "q3", patient_id: "P-67890", encounter_id: "E-11111", provider: "Dr. Jones",
    query_type: "link_condition", condition: "Heart failure with CKD",
    icd10_current: "I50.9", icd10_target: "I13.0",
    query_text: "The patient has both hypertensive heart disease and chronic kidney disease stage 3. Could you please document whether there is a causal relationship between the hypertension and both the heart disease and CKD? This would allow combination coding to I13.0.",
    status: "draft", created_at: "2025-01-14", impacts: ["hcc", "drg"], raf_impact: 0.368,
  },
  {
    id: "q4", patient_id: "P-55555", encounter_id: "E-22222", provider: "Dr. Williams",
    query_type: "complication", condition: "Acute kidney injury",
    icd10_current: "N17.9", icd10_target: "T36-T50",
    query_text: "The patient developed acute kidney injury during the admission. Could you please clarify whether this represents a complication of the contrast dye administration during the cardiac catheterization or an exacerbation of pre-existing CKD?",
    status: "sent", created_at: "2025-01-13", impacts: ["drg", "quality"], raf_impact: null,
  },
  {
    id: "q5", patient_id: "P-33333", encounter_id: "E-44444", provider: "Dr. Smith",
    query_type: "specificity", condition: "COPD",
    icd10_current: "J44.1", icd10_target: "J44.0",
    query_text: "The patient is admitted with COPD exacerbation coded as J44.1. The sputum culture shows Pseudomonas aeruginosa. Could you please document the acute lower respiratory infection to support coding to J44.0 (COPD with acute lower respiratory infection)?",
    status: "expired", created_at: "2025-01-05", impacts: ["drg"], raf_impact: null,
  },
];

const statusConfig: Record<QueryStatus, { label: string; color: string }> = {
  draft: { label: "Draft", color: "bg-gray-100 text-gray-800" },
  sent: { label: "Sent", color: "bg-blue-100 text-blue-800" },
  answered: { label: "Answered", color: "bg-green-100 text-green-800" },
  expired: { label: "Expired", color: "bg-red-100 text-red-800" },
};

const impactConfig: Record<ImpactType, { label: string; color: string }> = {
  hcc: { label: "HCC/RAF", color: "bg-purple-100 text-purple-800" },
  drg: { label: "DRG", color: "bg-blue-100 text-blue-800" },
  quality: { label: "Quality", color: "bg-green-100 text-green-800" },
  severity: { label: "SOI/ROM", color: "bg-amber-100 text-amber-800" },
};

export default function CDIQueryBuilderPage() {
  const [queries, setQueries] = useState<CDIQuery[]>(mockQueries);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [showBuilder, setShowBuilder] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [builderCondition, setBuilderCondition] = useState("");
  const [builderCurrentCode, setBuilderCurrentCode] = useState("");
  const [builderTargetCode, setBuilderTargetCode] = useState("");
  const [builderProvider, setBuilderProvider] = useState("");

  const filteredQueries = statusFilter === "all"
    ? queries
    : queries.filter((q) => q.status === statusFilter);

  const statusCounts = queries.reduce(
    (acc, q) => { acc[q.status] = (acc[q.status] || 0) + 1; return acc; },
    {} as Record<string, number>
  );

  const totalRafImpact = queries
    .filter((q) => q.raf_impact !== null && q.status !== "expired")
    .reduce((sum, q) => sum + (q.raf_impact || 0), 0);

  return (
    <div className="container mx-auto p-6 max-w-6xl">
      <div className="flex items-center gap-4 mb-6">
        <Link href="/clinical">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-1" /> Clinical
          </Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">CDI Query Builder</h1>
          <p className="text-muted-foreground">
            Clinical Documentation Improvement queries for coding accuracy
          </p>
        </div>
        <Button onClick={() => setShowBuilder(!showBuilder)}>
          <Plus className="h-4 w-4 mr-1" />
          New Query
        </Button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Queries</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{queries.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Pending</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">{statusCounts.sent || 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Answered</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{statusCounts.answered || 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Response Rate</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {queries.length > 0
                ? Math.round(((statusCounts.answered || 0) / queries.length) * 100)
                : 0}%
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">RAF Impact</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-600">{totalRafImpact.toFixed(3)}</div>
          </CardContent>
        </Card>
      </div>

      {/* Query Builder Panel */}
      {showBuilder && (
        <Card className="mb-6 border-2 border-primary/20">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <ClipboardList className="h-5 w-5" /> Build New Query
            </CardTitle>
            <CardDescription>Select a template and fill in the details</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Template Selection */}
              <div>
                <label className="text-sm font-medium mb-2 block">Query Template</label>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                  {queryTemplates.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => setSelectedTemplate(t.id)}
                      className={`p-3 rounded-lg border text-left text-sm transition-colors ${
                        selectedTemplate === t.id
                          ? "border-primary bg-primary/5"
                          : "border-muted hover:border-primary/50"
                      }`}
                    >
                      <div className="font-medium mb-1">{t.label}</div>
                      <div className="flex gap-1">
                        {t.impacts.map((imp) => (
                          <Badge key={imp} className={`text-xs ${impactConfig[imp].color}`}>
                            {impactConfig[imp].label}
                          </Badge>
                        ))}
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {selectedTemplate && (
                <>
                  {/* Query Fields */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-medium mb-1 block">Condition</label>
                      <Input
                        value={builderCondition}
                        onChange={(e) => setBuilderCondition(e.target.value)}
                        placeholder="e.g., Type 2 Diabetes"
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium mb-1 block">Provider</label>
                      <Input
                        value={builderProvider}
                        onChange={(e) => setBuilderProvider(e.target.value)}
                        placeholder="e.g., Dr. Smith"
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium mb-1 block">Current ICD-10</label>
                      <Input
                        value={builderCurrentCode}
                        onChange={(e) => setBuilderCurrentCode(e.target.value)}
                        placeholder="e.g., E11.9"
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium mb-1 block">Target ICD-10</label>
                      <Input
                        value={builderTargetCode}
                        onChange={(e) => setBuilderTargetCode(e.target.value)}
                        placeholder="e.g., E11.65"
                      />
                    </div>
                  </div>

                  {/* Preview */}
                  <div className="bg-muted/50 rounded-lg p-4">
                    <div className="text-xs font-medium text-muted-foreground mb-1">Query Preview</div>
                    <p className="text-sm">
                      {queryTemplates.find((t) => t.id === selectedTemplate)?.template
                        .replace("[CONDITION]", builderCondition || "[condition]")
                        .replace("[CURRENT_CODE]", builderCurrentCode || "[current code]")
                        .replace("[TARGET_CODE]", builderTargetCode || "[target code]")
                        .replace("[FINDING]", builderCondition || "[finding]")
                        .replace("[SPECIFICITY_QUESTION]", "the specific type/manifestation")
                        .replace("[CONDITION_A]", builderCondition || "[condition A]")
                        .replace("[CONDITION_B]", "[condition B]")
                        .replace("[PROCEDURE/CONDITION]", "[procedure/condition]")
                      }
                    </p>
                  </div>

                  <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={() => setShowBuilder(false)}>Cancel</Button>
                    <Button variant="outline">
                      <FileText className="h-4 w-4 mr-1" /> Save Draft
                    </Button>
                    <Button>
                      <Send className="h-4 w-4 mr-1" /> Send Query
                    </Button>
                  </div>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filter */}
      <div className="flex items-center gap-2 mb-4">
        <span className="text-sm font-medium text-muted-foreground">Status:</span>
        {["all", "draft", "sent", "answered", "expired"].map((f) => (
          <Button
            key={f}
            variant={statusFilter === f ? "default" : "outline"}
            size="sm"
            onClick={() => setStatusFilter(f)}
            className="text-xs"
          >
            {f === "all" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
          </Button>
        ))}
      </div>

      {/* Queries List */}
      <div className="space-y-3">
        {filteredQueries.map((query) => {
          const sc = statusConfig[query.status];
          return (
            <Card key={query.id}>
              <CardContent className="pt-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge className={sc.color}>{sc.label}</Badge>
                      <span className="font-semibold text-sm">{query.condition}</span>
                      {query.impacts.map((imp) => (
                        <Badge key={imp} className={`text-xs ${impactConfig[imp].color}`}>
                          {impactConfig[imp].label}
                        </Badge>
                      ))}
                    </div>
                    <p className="text-sm text-muted-foreground mb-2">{query.query_text}</p>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      <span>Patient: {query.patient_id}</span>
                      <span>Provider: {query.provider}</span>
                      <span>Created: {query.created_at}</span>
                      {query.icd10_current && (
                        <span className="font-mono">
                          {query.icd10_current} → {query.icd10_target}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    {query.raf_impact !== null && (
                      <div>
                        <div className="text-sm font-bold text-purple-600">
                          +{query.raf_impact.toFixed(3)}
                        </div>
                        <div className="text-xs text-muted-foreground">RAF</div>
                      </div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
        {filteredQueries.length === 0 && (
          <div className="text-center py-8 text-muted-foreground">
            No queries match the current filter.
          </div>
        )}
      </div>
    </div>
  );
}
