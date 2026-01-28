"use client";

import { useState, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ArrowLeft,
  ArrowRight,
  Plus,
  Trash2,
  List,
  GitBranch,
  Upload,
  FileJson,
  FileSpreadsheet,
  Check,
  AlertCircle,
} from "lucide-react";

// Types
interface ValueSetCode {
  system: string;
  code: string;
  display: string;
}

interface InclusionRule {
  rule_type: string;
  system: string;
  code: string;
  filter_property: string;
  filter_operator: string;
  filter_value: string;
  include: boolean;
}

interface CreateValueSetRequest {
  name: string;
  title?: string;
  description?: string;
  url?: string;
  version: string;
  status: string;
  value_set_type: string;
  codes?: ValueSetCode[];
  rules?: InclusionRule[];
  publisher?: string;
  purpose?: string;
  experimental: boolean;
  immutable: boolean;
}

// API
const API_BASE = "/api/valuesets";

async function createValueSet(request: CreateValueSetRequest): Promise<{ id: string }> {
  const response = await fetch(API_BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to create value set");
  }
  return response.json();
}

async function importFHIR(fhirValueSet: unknown): Promise<{ id: string }> {
  const response = await fetch(`${API_BASE}/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fhirValueSet),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to import FHIR value set");
  }
  return response.json();
}

async function importCSV(formData: FormData): Promise<{ id: string }> {
  const response = await fetch(`${API_BASE}/import/csv`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to import CSV");
  }
  return response.json();
}

// Steps
type WizardStep = "type" | "details" | "content" | "review";

const STEPS: WizardStep[] = ["type", "details", "content", "review"];

const STEP_TITLES: Record<WizardStep, string> = {
  type: "Choose Type",
  details: "Value Set Details",
  content: "Add Content",
  review: "Review & Create",
};

// Common code systems
const CODE_SYSTEMS = [
  { label: "SNOMED CT", value: "http://snomed.info/sct" },
  { label: "ICD-10-CM", value: "http://hl7.org/fhir/sid/icd-10-cm" },
  { label: "ICD-10-PCS", value: "http://www.cms.gov/Medicare/Coding/ICD10" },
  { label: "CPT", value: "http://www.ama-assn.org/go/cpt" },
  { label: "LOINC", value: "http://loinc.org" },
  { label: "RxNorm", value: "http://www.nlm.nih.gov/research/umls/rxnorm" },
  { label: "HCPCS", value: "https://www.cms.gov/Medicare/Coding/MedHCPCSGenInfo" },
  { label: "NDC", value: "http://hl7.org/fhir/sid/ndc" },
];

function NewValueSetContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const importMode = searchParams.get("import");

  // Wizard state
  const [currentStep, setCurrentStep] = useState<WizardStep>(importMode ? "type" : "type");

  // Import state
  const [fhirJson, setFhirJson] = useState("");
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvConfig, setCsvConfig] = useState({
    name: "",
    system: CODE_SYSTEMS[0].value,
    title: "",
    description: "",
    codeColumn: "code",
    displayColumn: "display",
  });

  // Form state
  const [formData, setFormData] = useState<CreateValueSetRequest>({
    name: "",
    title: "",
    description: "",
    url: "",
    version: "1.0.0",
    status: "draft",
    value_set_type: "extensional",
    codes: [],
    rules: [],
    publisher: "",
    purpose: "",
    experimental: false,
    immutable: false,
  });

  // New code form
  const [newCode, setNewCode] = useState<ValueSetCode>({
    system: CODE_SYSTEMS[0].value,
    code: "",
    display: "",
  });

  // New rule form
  const [newRule, setNewRule] = useState<InclusionRule>({
    rule_type: "code",
    system: CODE_SYSTEMS[0].value,
    code: "",
    filter_property: "",
    filter_operator: "=",
    filter_value: "",
    include: true,
  });

  // Mutations
  const createMutation = useMutation({
    mutationFn: createValueSet,
    onSuccess: (data) => {
      toast.success("Value set created successfully");
      router.push(`/valuesets/${data.id}`);
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const importFHIRMutation = useMutation({
    mutationFn: importFHIR,
    onSuccess: (data) => {
      toast.success("FHIR value set imported successfully");
      router.push(`/valuesets/${data.id}`);
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const importCSVMutation = useMutation({
    mutationFn: importCSV,
    onSuccess: (data) => {
      toast.success("CSV imported successfully");
      router.push(`/valuesets/${data.id}`);
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  // Handlers
  const handleAddCode = useCallback(() => {
    if (!newCode.system || !newCode.code) {
      toast.error("System and code are required");
      return;
    }
    setFormData((prev) => ({
      ...prev,
      codes: [...(prev.codes || []), { ...newCode }],
    }));
    setNewCode({ system: newCode.system, code: "", display: "" });
  }, [newCode]);

  const handleRemoveCode = useCallback((index: number) => {
    setFormData((prev) => ({
      ...prev,
      codes: (prev.codes || []).filter((_, i) => i !== index),
    }));
  }, []);

  const handleAddRule = useCallback(() => {
    if (!newRule.system) {
      toast.error("System is required");
      return;
    }
    setFormData((prev) => ({
      ...prev,
      rules: [...(prev.rules || []), { ...newRule }],
    }));
    setNewRule({
      rule_type: "code",
      system: newRule.system,
      code: "",
      filter_property: "",
      filter_operator: "=",
      filter_value: "",
      include: true,
    });
  }, [newRule]);

  const handleRemoveRule = useCallback((index: number) => {
    setFormData((prev) => ({
      ...prev,
      rules: (prev.rules || []).filter((_, i) => i !== index),
    }));
  }, []);

  const handleNext = useCallback(() => {
    const currentIndex = STEPS.indexOf(currentStep);
    if (currentIndex < STEPS.length - 1) {
      setCurrentStep(STEPS[currentIndex + 1]);
    }
  }, [currentStep]);

  const handleBack = useCallback(() => {
    const currentIndex = STEPS.indexOf(currentStep);
    if (currentIndex > 0) {
      setCurrentStep(STEPS[currentIndex - 1]);
    }
  }, [currentStep]);

  const handleCreate = useCallback(() => {
    if (!formData.name) {
      toast.error("Name is required");
      return;
    }
    createMutation.mutate(formData);
  }, [formData, createMutation]);

  const handleImportFHIR = useCallback(() => {
    if (!fhirJson) {
      toast.error("Please paste FHIR JSON");
      return;
    }
    try {
      const parsed = JSON.parse(fhirJson);
      importFHIRMutation.mutate(parsed);
    } catch {
      toast.error("Invalid JSON");
    }
  }, [fhirJson, importFHIRMutation]);

  const handleImportCSV = useCallback(() => {
    if (!csvFile || !csvConfig.name || !csvConfig.system) {
      toast.error("Please provide file, name, and system");
      return;
    }
    const formData = new FormData();
    formData.append("file", csvFile);
    formData.append("name", csvConfig.name);
    formData.append("system", csvConfig.system);
    if (csvConfig.title) formData.append("title", csvConfig.title);
    if (csvConfig.description) formData.append("description", csvConfig.description);
    formData.append("code_column", csvConfig.codeColumn);
    formData.append("display_column", csvConfig.displayColumn);
    importCSVMutation.mutate(formData);
  }, [csvFile, csvConfig, importCSVMutation]);

  const canProceed = useCallback(() => {
    switch (currentStep) {
      case "type":
        return true;
      case "details":
        return !!formData.name;
      case "content":
        return (
          (formData.value_set_type === "extensional" && (formData.codes?.length || 0) > 0) ||
          (formData.value_set_type === "intensional" && (formData.rules?.length || 0) > 0)
        );
      default:
        return true;
    }
  }, [currentStep, formData]);

  // Import mode renders
  if (importMode === "fhir") {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <div className="mb-6">
          <Link href="/valuesets">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Value Sets
            </Button>
          </Link>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileJson className="h-5 w-5" />
              Import FHIR ValueSet
            </CardTitle>
            <CardDescription>
              Paste a FHIR R4 ValueSet resource in JSON format
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="fhirJson">FHIR ValueSet JSON</Label>
              <Textarea
                id="fhirJson"
                placeholder='{"resourceType": "ValueSet", ...}'
                value={fhirJson}
                onChange={(e) => setFhirJson(e.target.value)}
                className="min-h-[300px] font-mono text-sm"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Link href="/valuesets">
                <Button variant="outline">Cancel</Button>
              </Link>
              <Button
                onClick={handleImportFHIR}
                disabled={!fhirJson || importFHIRMutation.isPending}
              >
                <Upload className="mr-2 h-4 w-4" />
                Import
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (importMode === "csv") {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <div className="mb-6">
          <Link href="/valuesets">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Value Sets
            </Button>
          </Link>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileSpreadsheet className="h-5 w-5" />
              Import from CSV
            </CardTitle>
            <CardDescription>
              Import codes from a CSV file with code and display columns
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="csvFile">CSV File</Label>
              <Input
                id="csvFile"
                type="file"
                accept=".csv"
                onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="csvName">Value Set Name *</Label>
                <Input
                  id="csvName"
                  placeholder="MyValueSet"
                  value={csvConfig.name}
                  onChange={(e) => setCsvConfig({ ...csvConfig, name: e.target.value })}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="csvSystem">Code System *</Label>
                <select
                  id="csvSystem"
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={csvConfig.system}
                  onChange={(e) => setCsvConfig({ ...csvConfig, system: e.target.value })}
                >
                  {CODE_SYSTEMS.map((cs) => (
                    <option key={cs.value} value={cs.value}>
                      {cs.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="csvTitle">Title</Label>
                <Input
                  id="csvTitle"
                  placeholder="My Value Set"
                  value={csvConfig.title}
                  onChange={(e) => setCsvConfig({ ...csvConfig, title: e.target.value })}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="csvDescription">Description</Label>
                <Input
                  id="csvDescription"
                  placeholder="Description of the value set"
                  value={csvConfig.description}
                  onChange={(e) => setCsvConfig({ ...csvConfig, description: e.target.value })}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="codeColumn">Code Column Name</Label>
                <Input
                  id="codeColumn"
                  placeholder="code"
                  value={csvConfig.codeColumn}
                  onChange={(e) => setCsvConfig({ ...csvConfig, codeColumn: e.target.value })}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="displayColumn">Display Column Name</Label>
                <Input
                  id="displayColumn"
                  placeholder="display"
                  value={csvConfig.displayColumn}
                  onChange={(e) => setCsvConfig({ ...csvConfig, displayColumn: e.target.value })}
                />
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <Link href="/valuesets">
                <Button variant="outline">Cancel</Button>
              </Link>
              <Button
                onClick={handleImportCSV}
                disabled={!csvFile || !csvConfig.name || importCSVMutation.isPending}
              >
                <Upload className="mr-2 h-4 w-4" />
                Import
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Wizard mode
  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <Link href="/valuesets">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Value Sets
          </Button>
        </Link>
      </div>

      {/* Progress */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          {STEPS.map((step, idx) => (
            <div key={step} className="flex items-center">
              <div
                className={`flex items-center justify-center w-8 h-8 rounded-full border-2 ${
                  currentStep === step
                    ? "border-blue-500 bg-blue-500 text-white"
                    : STEPS.indexOf(currentStep) > idx
                    ? "border-green-500 bg-green-500 text-white"
                    : "border-gray-300 text-gray-400"
                }`}
              >
                {STEPS.indexOf(currentStep) > idx ? (
                  <Check className="h-4 w-4" />
                ) : (
                  idx + 1
                )}
              </div>
              <span
                className={`ml-2 text-sm ${
                  currentStep === step ? "font-medium" : "text-muted-foreground"
                }`}
              >
                {STEP_TITLES[step]}
              </span>
              {idx < STEPS.length - 1 && (
                <div
                  className={`w-16 h-0.5 mx-4 ${
                    STEPS.indexOf(currentStep) > idx ? "bg-green-500" : "bg-gray-300"
                  }`}
                />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Step Content */}
      <Card>
        <CardHeader>
          <CardTitle>{STEP_TITLES[currentStep]}</CardTitle>
        </CardHeader>
        <CardContent>
          {/* Step 1: Type Selection */}
          {currentStep === "type" && (
            <div className="space-y-4">
              <p className="text-muted-foreground">
                Choose how you want to define your value set.
              </p>
              <div className="grid gap-4 md:grid-cols-2">
                <Card
                  className={`cursor-pointer transition-all ${
                    formData.value_set_type === "extensional"
                      ? "ring-2 ring-blue-500"
                      : "hover:border-blue-300"
                  }`}
                  onClick={() =>
                    setFormData({ ...formData, value_set_type: "extensional" })
                  }
                >
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-lg">
                      <List className="h-5 w-5 text-blue-500" />
                      Extensional
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      Define your value set by manually listing specific codes. Best for
                      small, curated sets of codes.
                    </p>
                    <ul className="mt-4 text-sm text-muted-foreground list-disc list-inside">
                      <li>Add codes one by one</li>
                      <li>Full control over which codes are included</li>
                      <li>Simple and straightforward</li>
                    </ul>
                  </CardContent>
                </Card>

                <Card
                  className={`cursor-pointer transition-all ${
                    formData.value_set_type === "intensional"
                      ? "ring-2 ring-purple-500"
                      : "hover:border-purple-300"
                  }`}
                  onClick={() =>
                    setFormData({ ...formData, value_set_type: "intensional" })
                  }
                >
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-lg">
                      <GitBranch className="h-5 w-5 text-purple-500" />
                      Intensional
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      Define your value set using rules that dynamically include codes.
                      Best for large or hierarchical sets.
                    </p>
                    <ul className="mt-4 text-sm text-muted-foreground list-disc list-inside">
                      <li>Include all descendants of a code</li>
                      <li>Filter by properties</li>
                      <li>Automatically updated when source changes</li>
                    </ul>
                  </CardContent>
                </Card>
              </div>
            </div>
          )}

          {/* Step 2: Details */}
          {currentStep === "details" && (
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="name">Name *</Label>
                  <Input
                    id="name"
                    placeholder="DiabetesDiagnoses"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  />
                  <p className="text-xs text-muted-foreground">
                    Internal identifier, no spaces
                  </p>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="title">Title</Label>
                  <Input
                    id="title"
                    placeholder="Diabetes Diagnoses"
                    value={formData.title || ""}
                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  />
                  <p className="text-xs text-muted-foreground">Human-readable title</p>
                </div>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  placeholder="ICD-10 codes for diabetes mellitus diagnoses"
                  value={formData.description || ""}
                  onChange={(e) =>
                    setFormData({ ...formData, description: e.target.value })
                  }
                />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="url">URL</Label>
                  <Input
                    id="url"
                    placeholder="http://example.org/ValueSet/diabetes-diagnoses"
                    value={formData.url || ""}
                    onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                  />
                  <p className="text-xs text-muted-foreground">Canonical URL for FHIR</p>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="version">Version</Label>
                  <Input
                    id="version"
                    placeholder="1.0.0"
                    value={formData.version}
                    onChange={(e) => setFormData({ ...formData, version: e.target.value })}
                  />
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="publisher">Publisher</Label>
                  <Input
                    id="publisher"
                    placeholder="Organization name"
                    value={formData.publisher || ""}
                    onChange={(e) =>
                      setFormData({ ...formData, publisher: e.target.value })
                    }
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="purpose">Purpose</Label>
                  <Input
                    id="purpose"
                    placeholder="Clinical decision support"
                    value={formData.purpose || ""}
                    onChange={(e) => setFormData({ ...formData, purpose: e.target.value })}
                  />
                </div>
              </div>

              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formData.experimental}
                    onChange={(e) =>
                      setFormData({ ...formData, experimental: e.target.checked })
                    }
                    className="h-4 w-4 rounded border-gray-300"
                  />
                  <span className="text-sm">Experimental</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formData.immutable}
                    onChange={(e) =>
                      setFormData({ ...formData, immutable: e.target.checked })
                    }
                    className="h-4 w-4 rounded border-gray-300"
                  />
                  <span className="text-sm">Immutable (cannot be changed after activation)</span>
                </label>
              </div>
            </div>
          )}

          {/* Step 3: Content */}
          {currentStep === "content" && (
            <div className="space-y-6">
              {formData.value_set_type === "extensional" ? (
                <>
                  {/* Add Code Form */}
                  <div className="p-4 border rounded-lg bg-muted/30">
                    <h4 className="font-medium mb-4">Add Code</h4>
                    <div className="grid gap-4 md:grid-cols-4">
                      <div className="grid gap-2">
                        <Label htmlFor="codeSystem">System</Label>
                        <select
                          id="codeSystem"
                          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                          value={newCode.system}
                          onChange={(e) =>
                            setNewCode({ ...newCode, system: e.target.value })
                          }
                        >
                          {CODE_SYSTEMS.map((cs) => (
                            <option key={cs.value} value={cs.value}>
                              {cs.label}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="codeValue">Code</Label>
                        <Input
                          id="codeValue"
                          placeholder="E11.9"
                          value={newCode.code}
                          onChange={(e) =>
                            setNewCode({ ...newCode, code: e.target.value })
                          }
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="codeDisplay">Display</Label>
                        <Input
                          id="codeDisplay"
                          placeholder="Type 2 diabetes mellitus"
                          value={newCode.display}
                          onChange={(e) =>
                            setNewCode({ ...newCode, display: e.target.value })
                          }
                        />
                      </div>
                      <div className="flex items-end">
                        <Button onClick={handleAddCode} className="w-full">
                          <Plus className="mr-2 h-4 w-4" />
                          Add
                        </Button>
                      </div>
                    </div>
                  </div>

                  {/* Codes Table */}
                  {(formData.codes?.length || 0) > 0 ? (
                    <div className="rounded-lg border">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>System</TableHead>
                            <TableHead>Code</TableHead>
                            <TableHead>Display</TableHead>
                            <TableHead className="text-right">Actions</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {formData.codes?.map((code, idx) => (
                            <TableRow key={`${code.system}-${code.code}-${idx}`}>
                              <TableCell>
                                <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                                  {CODE_SYSTEMS.find((cs) => cs.value === code.system)?.label ||
                                    code.system.split("/").pop()}
                                </code>
                              </TableCell>
                              <TableCell className="font-mono">{code.code}</TableCell>
                              <TableCell>{code.display}</TableCell>
                              <TableCell className="text-right">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="text-red-600"
                                  onClick={() => handleRemoveCode(idx)}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  ) : (
                    <div className="py-12 text-center text-zinc-500 border rounded-lg">
                      <List className="mx-auto h-12 w-12 text-muted-foreground/50" />
                      <p className="mt-4">No codes added yet.</p>
                      <p className="text-sm mt-2">Add at least one code to continue.</p>
                    </div>
                  )}
                </>
              ) : (
                <>
                  {/* Add Rule Form */}
                  <div className="p-4 border rounded-lg bg-muted/30">
                    <h4 className="font-medium mb-4">Add Rule</h4>
                    <div className="grid gap-4">
                      <div className="grid gap-4 md:grid-cols-2">
                        <div className="grid gap-2">
                          <Label htmlFor="ruleType">Rule Type</Label>
                          <select
                            id="ruleType"
                            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                            value={newRule.rule_type}
                            onChange={(e) =>
                              setNewRule({ ...newRule, rule_type: e.target.value })
                            }
                          >
                            <option value="code">Include Specific Code</option>
                            <option value="descendants">All Descendants</option>
                            <option value="ancestors">All Ancestors</option>
                            <option value="filter">Filter by Property</option>
                          </select>
                        </div>
                        <div className="grid gap-2">
                          <Label htmlFor="ruleSystem">System</Label>
                          <select
                            id="ruleSystem"
                            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                            value={newRule.system}
                            onChange={(e) =>
                              setNewRule({ ...newRule, system: e.target.value })
                            }
                          >
                            {CODE_SYSTEMS.map((cs) => (
                              <option key={cs.value} value={cs.value}>
                                {cs.label}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>

                      {(newRule.rule_type === "code" ||
                        newRule.rule_type === "descendants" ||
                        newRule.rule_type === "ancestors") && (
                        <div className="grid gap-2">
                          <Label htmlFor="ruleCode">Code</Label>
                          <Input
                            id="ruleCode"
                            placeholder="73211009"
                            value={newRule.code}
                            onChange={(e) =>
                              setNewRule({ ...newRule, code: e.target.value })
                            }
                          />
                        </div>
                      )}

                      {newRule.rule_type === "filter" && (
                        <div className="grid gap-4 md:grid-cols-3">
                          <div className="grid gap-2">
                            <Label htmlFor="filterProperty">Property</Label>
                            <Input
                              id="filterProperty"
                              placeholder="concept"
                              value={newRule.filter_property}
                              onChange={(e) =>
                                setNewRule({ ...newRule, filter_property: e.target.value })
                              }
                            />
                          </div>
                          <div className="grid gap-2">
                            <Label htmlFor="filterOperator">Operator</Label>
                            <select
                              id="filterOperator"
                              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                              value={newRule.filter_operator}
                              onChange={(e) =>
                                setNewRule({ ...newRule, filter_operator: e.target.value })
                              }
                            >
                              <option value="=">=</option>
                              <option value="is-a">is-a</option>
                              <option value="descendent-of">descendent-of</option>
                              <option value="is-not-a">is-not-a</option>
                              <option value="regex">regex</option>
                              <option value="in">in</option>
                              <option value="not-in">not-in</option>
                            </select>
                          </div>
                          <div className="grid gap-2">
                            <Label htmlFor="filterValue">Value</Label>
                            <Input
                              id="filterValue"
                              value={newRule.filter_value}
                              onChange={(e) =>
                                setNewRule({ ...newRule, filter_value: e.target.value })
                              }
                            />
                          </div>
                        </div>
                      )}

                      <div className="flex items-center justify-between">
                        <label className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={newRule.include}
                            onChange={(e) =>
                              setNewRule({ ...newRule, include: e.target.checked })
                            }
                            className="h-4 w-4 rounded border-gray-300"
                          />
                          <span className="text-sm">Include (uncheck to exclude)</span>
                        </label>
                        <Button onClick={handleAddRule}>
                          <Plus className="mr-2 h-4 w-4" />
                          Add Rule
                        </Button>
                      </div>
                    </div>
                  </div>

                  {/* Rules Table */}
                  {(formData.rules?.length || 0) > 0 ? (
                    <div className="rounded-lg border">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Type</TableHead>
                            <TableHead>System</TableHead>
                            <TableHead>Details</TableHead>
                            <TableHead>Include/Exclude</TableHead>
                            <TableHead className="text-right">Actions</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {formData.rules?.map((rule, idx) => (
                            <TableRow key={idx}>
                              <TableCell>
                                <Badge variant="outline">{rule.rule_type}</Badge>
                              </TableCell>
                              <TableCell>
                                <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                                  {CODE_SYSTEMS.find((cs) => cs.value === rule.system)?.label ||
                                    rule.system.split("/").pop()}
                                </code>
                              </TableCell>
                              <TableCell>
                                {rule.code && <span className="font-mono">{rule.code}</span>}
                                {rule.filter_property && (
                                  <span>
                                    {rule.filter_property} {rule.filter_operator} {rule.filter_value}
                                  </span>
                                )}
                              </TableCell>
                              <TableCell>
                                <Badge
                                  className={
                                    rule.include
                                      ? "bg-green-100 text-green-800"
                                      : "bg-red-100 text-red-800"
                                  }
                                >
                                  {rule.include ? "Include" : "Exclude"}
                                </Badge>
                              </TableCell>
                              <TableCell className="text-right">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="text-red-600"
                                  onClick={() => handleRemoveRule(idx)}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  ) : (
                    <div className="py-12 text-center text-zinc-500 border rounded-lg">
                      <GitBranch className="mx-auto h-12 w-12 text-muted-foreground/50" />
                      <p className="mt-4">No rules added yet.</p>
                      <p className="text-sm mt-2">Add at least one rule to continue.</p>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* Step 4: Review */}
          {currentStep === "review" && (
            <div className="space-y-6">
              <div className="p-4 border rounded-lg">
                <h4 className="font-medium mb-4">Summary</h4>
                <dl className="grid gap-2 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Name:</dt>
                    <dd className="font-medium">{formData.name}</dd>
                  </div>
                  {formData.title && (
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Title:</dt>
                      <dd>{formData.title}</dd>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Type:</dt>
                    <dd>
                      <Badge
                        className={
                          formData.value_set_type === "extensional"
                            ? "bg-blue-100 text-blue-800"
                            : "bg-purple-100 text-purple-800"
                        }
                      >
                        {formData.value_set_type}
                      </Badge>
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Version:</dt>
                    <dd>{formData.version}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">
                      {formData.value_set_type === "extensional" ? "Codes:" : "Rules:"}
                    </dt>
                    <dd className="font-medium">
                      {formData.value_set_type === "extensional"
                        ? formData.codes?.length || 0
                        : formData.rules?.length || 0}
                    </dd>
                  </div>
                </dl>
              </div>

              {formData.description && (
                <div className="p-4 border rounded-lg">
                  <h4 className="font-medium mb-2">Description</h4>
                  <p className="text-sm text-muted-foreground">{formData.description}</p>
                </div>
              )}

              <div className="p-4 border rounded-lg bg-yellow-50 dark:bg-yellow-900/20">
                <div className="flex items-start gap-2">
                  <AlertCircle className="h-5 w-5 text-yellow-600 mt-0.5" />
                  <div>
                    <h4 className="font-medium text-yellow-800 dark:text-yellow-200">
                      Ready to Create
                    </h4>
                    <p className="text-sm text-yellow-700 dark:text-yellow-300 mt-1">
                      The value set will be created in draft status. You can activate it after
                      reviewing and verifying the content.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </CardContent>

        {/* Navigation */}
        <div className="flex items-center justify-between px-6 pb-6">
          <Button
            variant="outline"
            onClick={handleBack}
            disabled={currentStep === "type"}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Button>

          {currentStep === "review" ? (
            <Button onClick={handleCreate} disabled={createMutation.isPending}>
              {createMutation.isPending ? (
                <>
                  <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  Creating...
                </>
              ) : (
                <>
                  <Check className="mr-2 h-4 w-4" />
                  Create Value Set
                </>
              )}
            </Button>
          ) : (
            <Button onClick={handleNext} disabled={!canProceed()}>
              Next
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}

export default function NewValueSetPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center">Loading...</div>}>
      <NewValueSetContent />
    </Suspense>
  );
}
