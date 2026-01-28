"use client";

import { useState, useCallback, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery, useMutation } from "@tanstack/react-query";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  ArrowLeft,
  Plus,
  Trash2,
  Save,
  Eye,
  Users,
  Database,
  GripVertical,
  Search,
  User,
  Stethoscope,
  Pill,
  Activity,
  BarChart3,
  Calendar,
  Code,
  BookmarkPlus,
  ChevronRight,
  Loader2,
  X,
  Edit,
} from "lucide-react";

// Types
interface CodeEntry {
  code: string;
  display: string | null;
  system: string | null;
}

interface AgeRange {
  min_age: number | null;
  max_age: number | null;
}

interface DateRange {
  start_date: string | null;
  end_date: string | null;
}

interface NumericRange {
  min_value: number | null;
  max_value: number | null;
  include_min: boolean;
  include_max: boolean;
}

interface BaseCriterion {
  id: string;
  criterion_type: string;
  name: string | null;
  description: string | null;
  negated: boolean;
}

interface DemographicCriterion extends BaseCriterion {
  criterion_type: "demographic";
  age_range: AgeRange | null;
  genders: string[] | null;
  races: string[] | null;
  ethnicities: string[] | null;
}

interface ConditionCriterion extends BaseCriterion {
  criterion_type: "condition";
  codes: CodeEntry[];
  code_system: string;
  include_descendants: boolean;
  date_range: DateRange | null;
}

interface DrugCriterion extends BaseCriterion {
  criterion_type: "drug";
  codes: CodeEntry[];
  code_system: string;
  include_descendants: boolean;
  date_range: DateRange | null;
  min_days_supply: number | null;
}

interface ProcedureCriterion extends BaseCriterion {
  criterion_type: "procedure";
  codes: CodeEntry[];
  code_system: string;
  include_descendants: boolean;
  date_range: DateRange | null;
}

interface MeasurementCriterion extends BaseCriterion {
  criterion_type: "measurement";
  codes: CodeEntry[];
  code_system: string;
  value_range: NumericRange | null;
  unit: string | null;
  date_range: DateRange | null;
  abnormal_only: boolean;
}

interface VisitCriterion extends BaseCriterion {
  criterion_type: "visit";
  visit_types: string[];
  date_range: DateRange | null;
  min_length_of_stay: number | null;
  max_length_of_stay: number | null;
}

type AnyCriterion =
  | DemographicCriterion
  | ConditionCriterion
  | DrugCriterion
  | ProcedureCriterion
  | MeasurementCriterion
  | VisitCriterion;

interface CohortDefinition {
  id: string;
  name: string;
  description: string | null;
  version: string;
  status: string;
  criteria: AnyCriterion[];
  root_operator: "AND" | "OR" | "NOT";
  tags: string[];
}

interface SavedCriterion {
  id: string;
  name: string;
  description: string | null;
  category: string;
  criterion: AnyCriterion;
  usage_count: number;
}

interface CriteriaLibraryResponse {
  criteria: SavedCriterion[];
  total: number;
}

interface CountPreviewResponse {
  count: number;
  execution_time_ms: number;
  sql_query: string;
}

// API functions
const API_BASE = "/api/cohorts";

async function fetchCohort(id: string): Promise<CohortDefinition> {
  const response = await fetch(`${API_BASE}/${id}`);
  if (!response.ok) throw new Error("Failed to fetch cohort");
  return response.json();
}

async function createCohort(data: {
  name: string;
  description?: string;
  criteria: AnyCriterion[];
  root_operator: string;
  tags: string[];
}): Promise<CohortDefinition> {
  const response = await fetch(API_BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error("Failed to create cohort");
  return response.json();
}

async function updateCohort(id: string, data: {
  name?: string;
  description?: string;
  criteria?: AnyCriterion[];
  root_operator?: string;
  tags?: string[];
}): Promise<CohortDefinition> {
  const response = await fetch(`${API_BASE}/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error("Failed to update cohort");
  return response.json();
}

async function fetchCriteriaLibrary(category?: string): Promise<CriteriaLibraryResponse> {
  const params = category ? `?category=${encodeURIComponent(category)}` : "";
  const response = await fetch(`${API_BASE}/criteria-library${params}`);
  if (!response.ok) throw new Error("Failed to fetch criteria library");
  return response.json();
}

async function previewCount(criteria: AnyCriterion[], rootOperator: string): Promise<CountPreviewResponse> {
  const response = await fetch(`${API_BASE}/preview/count`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ criteria, root_operator: rootOperator }),
  });
  if (!response.ok) throw new Error("Failed to preview count");
  return response.json();
}

// Criterion type config
const CRITERION_TYPES = [
  {
    type: "demographic",
    label: "Demographics",
    icon: User,
    color: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
    description: "Age, gender, race, ethnicity",
  },
  {
    type: "condition",
    label: "Condition",
    icon: Stethoscope,
    color: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
    description: "ICD-10, SNOMED diagnoses",
  },
  {
    type: "drug",
    label: "Drug",
    icon: Pill,
    color: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
    description: "RxNorm medications",
  },
  {
    type: "procedure",
    label: "Procedure",
    icon: Activity,
    color: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
    description: "CPT, ICD-10-PCS procedures",
  },
  {
    type: "measurement",
    label: "Measurement",
    icon: BarChart3,
    color: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
    description: "LOINC lab values",
  },
  {
    type: "visit",
    label: "Visit",
    icon: Calendar,
    color: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200",
    description: "Encounter types",
  },
];

const GENDER_OPTIONS = [
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
  { value: "other", label: "Other" },
  { value: "unknown", label: "Unknown" },
];

const RACE_OPTIONS = [
  { value: "white", label: "White" },
  { value: "black", label: "Black or African American" },
  { value: "asian", label: "Asian" },
  { value: "native_american", label: "American Indian/Alaska Native" },
  { value: "pacific_islander", label: "Native Hawaiian/Pacific Islander" },
  { value: "other", label: "Other" },
  { value: "unknown", label: "Unknown" },
];

const ETHNICITY_OPTIONS = [
  { value: "hispanic", label: "Hispanic or Latino" },
  { value: "not_hispanic", label: "Not Hispanic or Latino" },
  { value: "unknown", label: "Unknown" },
];

const VISIT_TYPE_OPTIONS = [
  { value: "inpatient", label: "Inpatient" },
  { value: "outpatient", label: "Outpatient" },
  { value: "emergency", label: "Emergency" },
  { value: "long_term_care", label: "Long-term Care" },
  { value: "home_health", label: "Home Health" },
  { value: "telehealth", label: "Telehealth" },
  { value: "other", label: "Other" },
];

// Generate unique ID
function generateId(): string {
  return Math.random().toString(36).substring(2, 15);
}

// Create empty criterion of given type
function createEmptyCriterion(type: string): AnyCriterion {
  const base = {
    id: generateId(),
    name: null,
    description: null,
    negated: false,
  };

  switch (type) {
    case "demographic":
      return {
        ...base,
        criterion_type: "demographic",
        age_range: { min_age: null, max_age: null },
        genders: [],
        races: [],
        ethnicities: [],
      } as DemographicCriterion;
    case "condition":
      return {
        ...base,
        criterion_type: "condition",
        codes: [],
        code_system: "ICD10CM",
        include_descendants: true,
        date_range: null,
      } as ConditionCriterion;
    case "drug":
      return {
        ...base,
        criterion_type: "drug",
        codes: [],
        code_system: "RxNorm",
        include_descendants: true,
        date_range: null,
        min_days_supply: null,
      } as DrugCriterion;
    case "procedure":
      return {
        ...base,
        criterion_type: "procedure",
        codes: [],
        code_system: "CPT",
        include_descendants: true,
        date_range: null,
      } as ProcedureCriterion;
    case "measurement":
      return {
        ...base,
        criterion_type: "measurement",
        codes: [],
        code_system: "LOINC",
        value_range: { min_value: null, max_value: null, include_min: true, include_max: true },
        unit: null,
        date_range: null,
        abnormal_only: false,
      } as MeasurementCriterion;
    case "visit":
      return {
        ...base,
        criterion_type: "visit",
        visit_types: [],
        date_range: null,
        min_length_of_stay: null,
        max_length_of_stay: null,
      } as VisitCriterion;
    default:
      throw new Error(`Unknown criterion type: ${type}`);
  }
}

// Criterion Editor Components
function DemographicEditor({
  criterion,
  onChange,
}: {
  criterion: DemographicCriterion;
  onChange: (c: DemographicCriterion) => void;
}) {
  return (
    <div className="space-y-4">
      {/* Age Range */}
      <div>
        <Label>Age Range</Label>
        <div className="flex items-center gap-2 mt-1">
          <Input
            type="number"
            placeholder="Min"
            value={criterion.age_range?.min_age ?? ""}
            onChange={(e) =>
              onChange({
                ...criterion,
                age_range: {
                  ...criterion.age_range,
                  min_age: e.target.value ? Number(e.target.value) : null,
                  max_age: criterion.age_range?.max_age ?? null,
                },
              })
            }
            className="w-24"
          />
          <span>to</span>
          <Input
            type="number"
            placeholder="Max"
            value={criterion.age_range?.max_age ?? ""}
            onChange={(e) =>
              onChange({
                ...criterion,
                age_range: {
                  ...criterion.age_range,
                  min_age: criterion.age_range?.min_age ?? null,
                  max_age: e.target.value ? Number(e.target.value) : null,
                },
              })
            }
            className="w-24"
          />
          <span className="text-muted-foreground">years</span>
        </div>
      </div>

      {/* Gender */}
      <div>
        <Label>Gender</Label>
        <div className="flex flex-wrap gap-2 mt-1">
          {GENDER_OPTIONS.map((opt) => (
            <label key={opt.value} className="flex items-center gap-1.5">
              <Checkbox
                checked={criterion.genders?.includes(opt.value) ?? false}
                onCheckedChange={(checked) => {
                  const current = criterion.genders || [];
                  onChange({
                    ...criterion,
                    genders: checked
                      ? [...current, opt.value]
                      : current.filter((g) => g !== opt.value),
                  });
                }}
              />
              <span className="text-sm">{opt.label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Race */}
      <div>
        <Label>Race</Label>
        <div className="flex flex-wrap gap-2 mt-1">
          {RACE_OPTIONS.map((opt) => (
            <label key={opt.value} className="flex items-center gap-1.5">
              <Checkbox
                checked={criterion.races?.includes(opt.value) ?? false}
                onCheckedChange={(checked) => {
                  const current = criterion.races || [];
                  onChange({
                    ...criterion,
                    races: checked
                      ? [...current, opt.value]
                      : current.filter((r) => r !== opt.value),
                  });
                }}
              />
              <span className="text-sm">{opt.label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Ethnicity */}
      <div>
        <Label>Ethnicity</Label>
        <div className="flex flex-wrap gap-2 mt-1">
          {ETHNICITY_OPTIONS.map((opt) => (
            <label key={opt.value} className="flex items-center gap-1.5">
              <Checkbox
                checked={criterion.ethnicities?.includes(opt.value) ?? false}
                onCheckedChange={(checked) => {
                  const current = criterion.ethnicities || [];
                  onChange({
                    ...criterion,
                    ethnicities: checked
                      ? [...current, opt.value]
                      : current.filter((e) => e !== opt.value),
                  });
                }}
              />
              <span className="text-sm">{opt.label}</span>
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}

function CodedCriterionEditor({
  criterion,
  onChange,
  codeSystemOptions,
}: {
  criterion: ConditionCriterion | DrugCriterion | ProcedureCriterion;
  onChange: (c: ConditionCriterion | DrugCriterion | ProcedureCriterion) => void;
  codeSystemOptions: { value: string; label: string }[];
}) {
  const [codeInput, setCodeInput] = useState("");
  const [displayInput, setDisplayInput] = useState("");

  const addCode = () => {
    if (!codeInput.trim()) return;
    onChange({
      ...criterion,
      codes: [
        ...criterion.codes,
        { code: codeInput.trim(), display: displayInput.trim() || null, system: criterion.code_system },
      ],
    });
    setCodeInput("");
    setDisplayInput("");
  };

  const removeCode = (index: number) => {
    onChange({
      ...criterion,
      codes: criterion.codes.filter((_, i) => i !== index),
    });
  };

  return (
    <div className="space-y-4">
      {/* Code System */}
      <div>
        <Label>Code System</Label>
        <Select
          value={criterion.code_system}
          onValueChange={(value) => onChange({ ...criterion, code_system: value })}
        >
          <SelectTrigger className="mt-1">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {codeSystemOptions.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Code Input */}
      <div>
        <Label>Add Codes</Label>
        <div className="flex gap-2 mt-1">
          <Input
            placeholder="Code (e.g., E11.9)"
            value={codeInput}
            onChange={(e) => setCodeInput(e.target.value)}
            className="w-32"
          />
          <Input
            placeholder="Description (optional)"
            value={displayInput}
            onChange={(e) => setDisplayInput(e.target.value)}
            className="flex-grow"
          />
          <Button type="button" onClick={addCode} size="sm">
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Code List */}
      {criterion.codes.length > 0 && (
        <div>
          <Label>Selected Codes ({criterion.codes.length})</Label>
          <div className="flex flex-wrap gap-2 mt-1">
            {criterion.codes.map((code, index) => (
              <Badge key={index} variant="secondary" className="pr-1">
                <span>{code.code}</span>
                {code.display && (
                  <span className="text-muted-foreground ml-1 text-xs">
                    ({code.display.substring(0, 20)}...)
                  </span>
                )}
                <button
                  onClick={() => removeCode(index)}
                  className="ml-1 hover:text-red-500"
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Include Descendants */}
      <div className="flex items-center gap-2">
        <Checkbox
          id="include-descendants"
          checked={criterion.include_descendants}
          onCheckedChange={(checked) =>
            onChange({ ...criterion, include_descendants: !!checked })
          }
        />
        <Label htmlFor="include-descendants" className="text-sm">
          Include descendant codes
        </Label>
      </div>

      {/* Date Range */}
      <div>
        <Label>Date Range (optional)</Label>
        <div className="flex items-center gap-2 mt-1">
          <Input
            type="date"
            value={criterion.date_range?.start_date ?? ""}
            onChange={(e) =>
              onChange({
                ...criterion,
                date_range: {
                  start_date: e.target.value || null,
                  end_date: criterion.date_range?.end_date ?? null,
                },
              })
            }
          />
          <span>to</span>
          <Input
            type="date"
            value={criterion.date_range?.end_date ?? ""}
            onChange={(e) =>
              onChange({
                ...criterion,
                date_range: {
                  start_date: criterion.date_range?.start_date ?? null,
                  end_date: e.target.value || null,
                },
              })
            }
          />
        </div>
      </div>
    </div>
  );
}

function MeasurementEditor({
  criterion,
  onChange,
}: {
  criterion: MeasurementCriterion;
  onChange: (c: MeasurementCriterion) => void;
}) {
  const [codeInput, setCodeInput] = useState("");
  const [displayInput, setDisplayInput] = useState("");

  const addCode = () => {
    if (!codeInput.trim()) return;
    onChange({
      ...criterion,
      codes: [
        ...criterion.codes,
        { code: codeInput.trim(), display: displayInput.trim() || null, system: criterion.code_system },
      ],
    });
    setCodeInput("");
    setDisplayInput("");
  };

  const removeCode = (index: number) => {
    onChange({
      ...criterion,
      codes: criterion.codes.filter((_, i) => i !== index),
    });
  };

  return (
    <div className="space-y-4">
      {/* Code Input */}
      <div>
        <Label>LOINC Codes</Label>
        <div className="flex gap-2 mt-1">
          <Input
            placeholder="LOINC Code (e.g., 4548-4)"
            value={codeInput}
            onChange={(e) => setCodeInput(e.target.value)}
            className="w-40"
          />
          <Input
            placeholder="Description"
            value={displayInput}
            onChange={(e) => setDisplayInput(e.target.value)}
            className="flex-grow"
          />
          <Button type="button" onClick={addCode} size="sm">
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Code List */}
      {criterion.codes.length > 0 && (
        <div>
          <div className="flex flex-wrap gap-2">
            {criterion.codes.map((code, index) => (
              <Badge key={index} variant="secondary" className="pr-1">
                {code.code}
                <button onClick={() => removeCode(index)} className="ml-1 hover:text-red-500">
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Value Range */}
      <div>
        <Label>Value Range</Label>
        <div className="flex items-center gap-2 mt-1">
          <Input
            type="number"
            placeholder="Min"
            value={criterion.value_range?.min_value ?? ""}
            onChange={(e) =>
              onChange({
                ...criterion,
                value_range: {
                  ...criterion.value_range!,
                  min_value: e.target.value ? Number(e.target.value) : null,
                },
              })
            }
            className="w-24"
          />
          <span>to</span>
          <Input
            type="number"
            placeholder="Max"
            value={criterion.value_range?.max_value ?? ""}
            onChange={(e) =>
              onChange({
                ...criterion,
                value_range: {
                  ...criterion.value_range!,
                  max_value: e.target.value ? Number(e.target.value) : null,
                },
              })
            }
            className="w-24"
          />
          <Input
            placeholder="Unit"
            value={criterion.unit ?? ""}
            onChange={(e) => onChange({ ...criterion, unit: e.target.value || null })}
            className="w-24"
          />
        </div>
      </div>

      {/* Abnormal Only */}
      <div className="flex items-center gap-2">
        <Checkbox
          checked={criterion.abnormal_only}
          onCheckedChange={(checked) => onChange({ ...criterion, abnormal_only: !!checked })}
        />
        <Label className="text-sm">Abnormal values only</Label>
      </div>
    </div>
  );
}

function VisitEditor({
  criterion,
  onChange,
}: {
  criterion: VisitCriterion;
  onChange: (c: VisitCriterion) => void;
}) {
  return (
    <div className="space-y-4">
      {/* Visit Types */}
      <div>
        <Label>Visit Types</Label>
        <div className="flex flex-wrap gap-2 mt-1">
          {VISIT_TYPE_OPTIONS.map((opt) => (
            <label key={opt.value} className="flex items-center gap-1.5">
              <Checkbox
                checked={criterion.visit_types.includes(opt.value)}
                onCheckedChange={(checked) => {
                  onChange({
                    ...criterion,
                    visit_types: checked
                      ? [...criterion.visit_types, opt.value]
                      : criterion.visit_types.filter((v) => v !== opt.value),
                  });
                }}
              />
              <span className="text-sm">{opt.label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Length of Stay */}
      <div>
        <Label>Length of Stay (days)</Label>
        <div className="flex items-center gap-2 mt-1">
          <Input
            type="number"
            placeholder="Min"
            value={criterion.min_length_of_stay ?? ""}
            onChange={(e) =>
              onChange({
                ...criterion,
                min_length_of_stay: e.target.value ? Number(e.target.value) : null,
              })
            }
            className="w-24"
          />
          <span>to</span>
          <Input
            type="number"
            placeholder="Max"
            value={criterion.max_length_of_stay ?? ""}
            onChange={(e) =>
              onChange({
                ...criterion,
                max_length_of_stay: e.target.value ? Number(e.target.value) : null,
              })
            }
            className="w-24"
          />
        </div>
      </div>

      {/* Date Range */}
      <div>
        <Label>Date Range</Label>
        <div className="flex items-center gap-2 mt-1">
          <Input
            type="date"
            value={criterion.date_range?.start_date ?? ""}
            onChange={(e) =>
              onChange({
                ...criterion,
                date_range: {
                  start_date: e.target.value || null,
                  end_date: criterion.date_range?.end_date ?? null,
                },
              })
            }
          />
          <span>to</span>
          <Input
            type="date"
            value={criterion.date_range?.end_date ?? ""}
            onChange={(e) =>
              onChange({
                ...criterion,
                date_range: {
                  start_date: criterion.date_range?.start_date ?? null,
                  end_date: e.target.value || null,
                },
              })
            }
          />
        </div>
      </div>
    </div>
  );
}

// Main component
function CohortBuilderContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const editId = searchParams.get("edit");

  // Form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [rootOperator, setRootOperator] = useState<"AND" | "OR">("AND");
  const [criteria, setCriteria] = useState<AnyCriterion[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");

  // UI state
  const [selectedCriterion, setSelectedCriterion] = useState<AnyCriterion | null>(null);
  const [editorDialogOpen, setEditorDialogOpen] = useState(false);
  const [sqlDialogOpen, setSqlDialogOpen] = useState(false);
  const [libraryTab, setLibraryTab] = useState("types");

  // Fetch existing cohort for editing
  const { data: existingCohort, isLoading: loadingExisting } = useQuery({
    queryKey: ["cohort", editId],
    queryFn: () => fetchCohort(editId!),
    enabled: !!editId,
  });

  // Load existing cohort data
  useEffect(() => {
    if (existingCohort) {
      setName(existingCohort.name);
      setDescription(existingCohort.description || "");
      setRootOperator(existingCohort.root_operator as "AND" | "OR");
      setCriteria(existingCohort.criteria);
      setTags(existingCohort.tags);
    }
  }, [existingCohort]);

  // Fetch criteria library
  const { data: libraryData } = useQuery({
    queryKey: ["criteria-library"],
    queryFn: () => fetchCriteriaLibrary(),
  });

  // Preview count mutation
  const countMutation = useMutation({
    mutationFn: () => previewCount(criteria, rootOperator),
  });

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: async () => {
      const data = {
        name,
        description: description || undefined,
        criteria,
        root_operator: rootOperator,
        tags,
      };
      if (editId) {
        return updateCohort(editId, data);
      }
      return createCohort(data);
    },
    onSuccess: (saved) => {
      toast.success(editId ? "Cohort updated" : "Cohort created");
      router.push(`/cohorts/${saved.id}`);
    },
    onError: () => {
      toast.error("Failed to save cohort");
    },
  });

  // Handlers
  const handleAddCriterion = useCallback((type: string) => {
    const newCriterion = createEmptyCriterion(type);
    setSelectedCriterion(newCriterion);
    setEditorDialogOpen(true);
  }, []);

  const handleEditCriterion = useCallback((criterion: AnyCriterion) => {
    setSelectedCriterion({ ...criterion });
    setEditorDialogOpen(true);
  }, []);

  const handleSaveCriterion = useCallback(() => {
    if (!selectedCriterion) return;

    setCriteria((prev) => {
      const index = prev.findIndex((c) => c.id === selectedCriterion.id);
      if (index >= 0) {
        // Update existing
        const updated = [...prev];
        updated[index] = selectedCriterion;
        return updated;
      }
      // Add new
      return [...prev, selectedCriterion];
    });

    setEditorDialogOpen(false);
    setSelectedCriterion(null);
    countMutation.reset();
  }, [selectedCriterion, countMutation]);

  const handleDeleteCriterion = useCallback((id: string) => {
    setCriteria((prev) => prev.filter((c) => c.id !== id));
    countMutation.reset();
  }, [countMutation]);

  const handleAddFromLibrary = useCallback((saved: SavedCriterion) => {
    const newCriterion = {
      ...saved.criterion,
      id: generateId(),
    };
    setCriteria((prev) => [...prev, newCriterion]);
    toast.success(`Added "${saved.name}" to criteria`);
    countMutation.reset();
  }, [countMutation]);

  const handleAddTag = useCallback(() => {
    if (tagInput.trim() && !tags.includes(tagInput.trim())) {
      setTags((prev) => [...prev, tagInput.trim()]);
      setTagInput("");
    }
  }, [tagInput, tags]);

  const handleRemoveTag = useCallback((tag: string) => {
    setTags((prev) => prev.filter((t) => t !== tag));
  }, []);

  const handlePreviewCount = useCallback(() => {
    countMutation.mutate();
  }, [countMutation]);

  const handleSave = useCallback(() => {
    if (!name.trim()) {
      toast.error("Please enter a cohort name");
      return;
    }
    saveMutation.mutate();
  }, [name, saveMutation]);

  // Get criterion type config
  const getCriterionConfig = (type: string) => {
    return CRITERION_TYPES.find((t) => t.type === type);
  };

  if (editId && loadingExisting) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      {/* Left Panel - Criteria Palette */}
      <div className="w-80 border-r bg-muted/30 flex flex-col">
        <div className="p-4 border-b">
          <h2 className="font-semibold">Criteria Palette</h2>
          <p className="text-sm text-muted-foreground">
            Click to add criteria to your cohort
          </p>
        </div>

        <Tabs value={libraryTab} onValueChange={setLibraryTab} className="flex-1 flex flex-col">
          <TabsList className="mx-4 mt-2">
            <TabsTrigger value="types">Types</TabsTrigger>
            <TabsTrigger value="library">Library</TabsTrigger>
          </TabsList>

          <TabsContent value="types" className="flex-1 p-4 space-y-2">
            {CRITERION_TYPES.map((type) => {
              const Icon = type.icon;
              return (
                <button
                  key={type.type}
                  onClick={() => handleAddCriterion(type.type)}
                  className="w-full flex items-center gap-3 p-3 rounded-lg border bg-background hover:bg-muted transition-colors text-left"
                >
                  <div className={`p-2 rounded-md ${type.color}`}>
                    <Icon className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="font-medium text-sm">{type.label}</div>
                    <div className="text-xs text-muted-foreground">{type.description}</div>
                  </div>
                </button>
              );
            })}
          </TabsContent>

          <TabsContent value="library" className="flex-1 overflow-hidden">
            <ScrollArea className="h-full">
              <div className="p-4 space-y-2">
                {libraryData?.criteria.map((saved) => {
                  const config = getCriterionConfig(saved.criterion.criterion_type);
                  const Icon = config?.icon || Database;
                  return (
                    <button
                      key={saved.id}
                      onClick={() => handleAddFromLibrary(saved)}
                      className="w-full flex items-center gap-3 p-3 rounded-lg border bg-background hover:bg-muted transition-colors text-left"
                    >
                      <div className={`p-2 rounded-md ${config?.color || "bg-gray-100"}`}>
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="flex-grow min-w-0">
                        <div className="font-medium text-sm truncate">{saved.name}</div>
                        <div className="text-xs text-muted-foreground">{saved.category}</div>
                      </div>
                      <Badge variant="outline" className="text-xs">
                        {saved.usage_count}
                      </Badge>
                    </button>
                  );
                })}
              </div>
            </ScrollArea>
          </TabsContent>
        </Tabs>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Link href="/cohorts">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <h1 className="text-lg font-semibold">
              {editId ? "Edit Cohort" : "New Cohort"}
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => setSqlDialogOpen(true)}>
              <Code className="mr-2 h-4 w-4" />
              Preview SQL
            </Button>
            <Button onClick={handleSave} disabled={saveMutation.isPending}>
              {saveMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              <Save className="mr-2 h-4 w-4" />
              Save Cohort
            </Button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          <div className="max-w-4xl mx-auto space-y-6">
            {/* Basic Info */}
            <Card>
              <CardHeader>
                <CardTitle>Cohort Information</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label htmlFor="name">Name *</Label>
                  <Input
                    id="name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Enter cohort name"
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="description">Description</Label>
                  <Textarea
                    id="description"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Describe the cohort and its purpose"
                    className="mt-1"
                    rows={3}
                  />
                </div>
                <div>
                  <Label>Tags</Label>
                  <div className="flex gap-2 mt-1">
                    <Input
                      value={tagInput}
                      onChange={(e) => setTagInput(e.target.value)}
                      placeholder="Add tag"
                      onKeyPress={(e) => e.key === "Enter" && handleAddTag()}
                    />
                    <Button type="button" onClick={handleAddTag} variant="outline">
                      Add
                    </Button>
                  </div>
                  {tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {tags.map((tag) => (
                        <Badge key={tag} variant="secondary">
                          {tag}
                          <button onClick={() => handleRemoveTag(tag)} className="ml-1">
                            <X className="h-3 w-3" />
                          </button>
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Criteria Builder */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Inclusion Criteria</CardTitle>
                    <CardDescription>
                      Define the criteria that patients must meet
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <Label className="text-sm">Combine with:</Label>
                    <Select
                      value={rootOperator}
                      onValueChange={(v) => {
                        setRootOperator(v as "AND" | "OR");
                        countMutation.reset();
                      }}
                    >
                      <SelectTrigger className="w-24">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="AND">AND</SelectItem>
                        <SelectItem value="OR">OR</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {criteria.length === 0 ? (
                  <div className="text-center py-12 text-muted-foreground border-2 border-dashed rounded-lg">
                    <Database className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>No criteria defined yet</p>
                    <p className="text-sm mt-1">
                      Add criteria from the palette on the left
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {criteria.map((criterion, index) => {
                      const config = getCriterionConfig(criterion.criterion_type);
                      const Icon = config?.icon || Database;

                      return (
                        <div key={criterion.id}>
                          {index > 0 && (
                            <div className="flex justify-center py-2">
                              <Badge variant="outline">{rootOperator}</Badge>
                            </div>
                          )}
                          <div
                            className={`flex items-center gap-3 p-4 rounded-lg border ${
                              criterion.negated ? "border-red-300 bg-red-50/50 dark:border-red-800 dark:bg-red-900/20" : "bg-muted/30"
                            }`}
                          >
                            <GripVertical className="h-5 w-5 text-muted-foreground cursor-move" />
                            <div className={`p-2 rounded-md ${config?.color || "bg-gray-100"}`}>
                              <Icon className="h-4 w-4" />
                            </div>
                            <div className="flex-grow">
                              <div className="font-medium text-sm flex items-center gap-2">
                                {criterion.name || config?.label}
                                {criterion.negated && (
                                  <Badge variant="destructive" className="text-xs">NOT</Badge>
                                )}
                              </div>
                              <div className="text-xs text-muted-foreground">
                                {getCriterionSummary(criterion)}
                              </div>
                            </div>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleEditCriterion(criterion)}
                            >
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteCriterion(criterion.id)}
                            >
                              <Trash2 className="h-4 w-4 text-red-500" />
                            </Button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Patient Count Preview */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-5 w-5" />
                  Patient Count Preview
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-4">
                  <Button
                    onClick={handlePreviewCount}
                    disabled={countMutation.isPending || criteria.length === 0}
                    variant="outline"
                  >
                    {countMutation.isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Eye className="mr-2 h-4 w-4" />
                    )}
                    Calculate Count
                  </Button>
                  {countMutation.data && (
                    <div className="flex items-center gap-4">
                      <div>
                        <span className="text-3xl font-bold">
                          {countMutation.data.count.toLocaleString()}
                        </span>
                        <span className="text-muted-foreground ml-2">patients</span>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        ({countMutation.data.execution_time_ms.toFixed(1)}ms)
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      {/* Criterion Editor Dialog */}
      <Dialog open={editorDialogOpen} onOpenChange={setEditorDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {selectedCriterion?.id && criteria.some((c) => c.id === selectedCriterion.id)
                ? "Edit Criterion"
                : "Add Criterion"}
            </DialogTitle>
            <DialogDescription>
              Configure the criterion parameters
            </DialogDescription>
          </DialogHeader>

          {selectedCriterion && (
            <div className="space-y-4 py-4">
              {/* Name */}
              <div>
                <Label>Criterion Name (optional)</Label>
                <Input
                  value={selectedCriterion.name || ""}
                  onChange={(e) =>
                    setSelectedCriterion({ ...selectedCriterion, name: e.target.value || null })
                  }
                  placeholder="Give this criterion a name"
                  className="mt-1"
                />
              </div>

              {/* Negation */}
              <div className="flex items-center gap-2">
                <Checkbox
                  checked={selectedCriterion.negated}
                  onCheckedChange={(checked) =>
                    setSelectedCriterion({ ...selectedCriterion, negated: !!checked })
                  }
                />
                <Label className="text-sm">Exclude patients matching this criterion (NOT)</Label>
              </div>

              <Separator />

              {/* Type-specific editor */}
              {selectedCriterion.criterion_type === "demographic" && (
                <DemographicEditor
                  criterion={selectedCriterion as DemographicCriterion}
                  onChange={(c) => setSelectedCriterion(c)}
                />
              )}
              {selectedCriterion.criterion_type === "condition" && (
                <CodedCriterionEditor
                  criterion={selectedCriterion as ConditionCriterion}
                  onChange={(c) => setSelectedCriterion(c)}
                  codeSystemOptions={[
                    { value: "ICD10CM", label: "ICD-10-CM" },
                    { value: "SNOMED", label: "SNOMED CT" },
                  ]}
                />
              )}
              {selectedCriterion.criterion_type === "drug" && (
                <CodedCriterionEditor
                  criterion={selectedCriterion as DrugCriterion}
                  onChange={(c) => setSelectedCriterion(c)}
                  codeSystemOptions={[
                    { value: "RxNorm", label: "RxNorm" },
                    { value: "NDC", label: "NDC" },
                  ]}
                />
              )}
              {selectedCriterion.criterion_type === "procedure" && (
                <CodedCriterionEditor
                  criterion={selectedCriterion as ProcedureCriterion}
                  onChange={(c) => setSelectedCriterion(c)}
                  codeSystemOptions={[
                    { value: "CPT", label: "CPT-4" },
                    { value: "ICD10PCS", label: "ICD-10-PCS" },
                    { value: "SNOMED", label: "SNOMED CT" },
                  ]}
                />
              )}
              {selectedCriterion.criterion_type === "measurement" && (
                <MeasurementEditor
                  criterion={selectedCriterion as MeasurementCriterion}
                  onChange={(c) => setSelectedCriterion(c)}
                />
              )}
              {selectedCriterion.criterion_type === "visit" && (
                <VisitEditor
                  criterion={selectedCriterion as VisitCriterion}
                  onChange={(c) => setSelectedCriterion(c)}
                />
              )}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setEditorDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSaveCriterion}>Save Criterion</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* SQL Preview Dialog */}
      <Dialog open={sqlDialogOpen} onOpenChange={setSqlDialogOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Generated SQL Query</DialogTitle>
            <DialogDescription>
              OMOP CDM compatible SQL for this cohort definition
            </DialogDescription>
          </DialogHeader>
          <pre className="bg-muted p-4 rounded-lg overflow-x-auto text-sm max-h-96">
            <code>{countMutation.data?.sql_query || "Click 'Calculate Count' to generate SQL"}</code>
          </pre>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                if (countMutation.data?.sql_query) {
                  navigator.clipboard.writeText(countMutation.data.sql_query);
                  toast.success("SQL copied to clipboard");
                }
              }}
              disabled={!countMutation.data?.sql_query}
            >
              Copy SQL
            </Button>
            <Button onClick={() => setSqlDialogOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function CohortBuilderPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center">Loading Cohort Builder...</div>}>
      <CohortBuilderContent />
    </Suspense>
  );
}

// Helper function to get criterion summary text
function getCriterionSummary(criterion: AnyCriterion): string {
  switch (criterion.criterion_type) {
    case "demographic": {
      const demo = criterion as DemographicCriterion;
      const parts = [];
      if (demo.age_range?.min_age || demo.age_range?.max_age) {
        parts.push(`Age ${demo.age_range.min_age || "*"}-${demo.age_range.max_age || "*"}`);
      }
      if (demo.genders?.length) {
        parts.push(`Gender: ${demo.genders.length} selected`);
      }
      return parts.join(", ") || "No filters";
    }
    case "condition":
    case "drug":
    case "procedure": {
      const coded = criterion as ConditionCriterion | DrugCriterion | ProcedureCriterion;
      return coded.codes.length > 0
        ? `${coded.codes.length} ${coded.code_system} codes`
        : "No codes selected";
    }
    case "measurement": {
      const meas = criterion as MeasurementCriterion;
      const parts = [];
      if (meas.codes.length) parts.push(`${meas.codes.length} LOINC codes`);
      if (meas.value_range?.min_value !== null || meas.value_range?.max_value !== null) {
        parts.push(`Value range set`);
      }
      return parts.join(", ") || "No configuration";
    }
    case "visit": {
      const visit = criterion as VisitCriterion;
      return visit.visit_types.length > 0
        ? `${visit.visit_types.length} visit types`
        : "All visit types";
    }
    default:
      return "Unknown criterion";
  }
}
