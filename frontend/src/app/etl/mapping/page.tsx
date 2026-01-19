"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle,
  ChevronDown,
  Download,
  FileDown,
  FileUp,
  GripVertical,
  Loader2,
  MoreHorizontal,
  RefreshCw,
  Save,
  Search,
  Settings2,
  Trash2,
  Upload,
  Wand2,
  X,
  AlertTriangle,
  ArrowLeftRight,
  Calendar,
  Hash,
  Type,
  Braces,
} from "lucide-react";

// =============================================================================
// Types
// =============================================================================

interface SourceField {
  id: string;
  name: string;
  type: string;
  sampleValues: string[];
  nullable: boolean;
  description?: string;
}

interface TargetField {
  id: string;
  name: string;
  table: string;
  type: string;
  required: boolean;
  description?: string;
}

interface FieldMapping {
  id: string;
  sourceFieldId: string;
  targetFieldId: string | null;
  transformation: TransformationType | null;
  transformationConfig?: Record<string, unknown>;
  confidence: number;
  status: "mapped" | "suggested" | "needs_review" | "unmapped" | "ignored";
}

type TransformationType =
  | "none"
  | "format_date"
  | "convert_units"
  | "lookup_code"
  | "concatenate"
  | "split"
  | "uppercase"
  | "lowercase"
  | "trim"
  | "custom";

interface MappingTemplate {
  id: string;
  name: string;
  description: string;
  mappings: number;
  lastUsed: string;
}

// =============================================================================
// Mock Data
// =============================================================================

const MOCK_SOURCE_FIELDS: SourceField[] = [
  { id: "sf1", name: "patient_id", type: "string", sampleValues: ["P001", "P002", "P003"], nullable: false },
  { id: "sf2", name: "first_name", type: "string", sampleValues: ["John", "Jane", "Robert"], nullable: false },
  { id: "sf3", name: "last_name", type: "string", sampleValues: ["Doe", "Smith", "Johnson"], nullable: false },
  { id: "sf4", name: "date_of_birth", type: "string", sampleValues: ["1985-03-15", "1990-07-22", "1978-11-08"], nullable: false },
  { id: "sf5", name: "gender", type: "string", sampleValues: ["M", "F", "M"], nullable: false },
  { id: "sf6", name: "mrn", type: "string", sampleValues: ["MRN001", "MRN002", "MRN003"], nullable: false },
  { id: "sf7", name: "ssn", type: "string", sampleValues: ["***-**-1234", "***-**-5678", "***-**-9012"], nullable: true },
  { id: "sf8", name: "address_line1", type: "string", sampleValues: ["123 Main St", "456 Oak Ave", "789 Elm Rd"], nullable: true },
  { id: "sf9", name: "city", type: "string", sampleValues: ["Boston", "New York", "Chicago"], nullable: true },
  { id: "sf10", name: "state", type: "string", sampleValues: ["MA", "NY", "IL"], nullable: true },
  { id: "sf11", name: "zip_code", type: "string", sampleValues: ["02101", "10001", "60601"], nullable: true },
  { id: "sf12", name: "phone", type: "string", sampleValues: ["(617) 555-1234", "(212) 555-5678", "(312) 555-9012"], nullable: true },
  { id: "sf13", name: "email", type: "string", sampleValues: ["john@email.com", "jane@email.com", "rob@email.com"], nullable: true },
  { id: "sf14", name: "insurance_id", type: "string", sampleValues: ["INS001", "INS002", "INS003"], nullable: true },
  { id: "sf15", name: "created_date", type: "datetime", sampleValues: ["2024-01-15 10:30:00", "2024-01-16 14:45:00", "2024-01-17 09:15:00"], nullable: false },
];

const MOCK_TARGET_FIELDS: TargetField[] = [
  { id: "tf1", name: "person_id", table: "person", type: "bigint", required: true, description: "Unique identifier for each person" },
  { id: "tf2", name: "gender_concept_id", table: "person", type: "integer", required: true, description: "Gender concept from OMOP vocabulary" },
  { id: "tf3", name: "year_of_birth", table: "person", type: "integer", required: true, description: "Year of birth" },
  { id: "tf4", name: "month_of_birth", table: "person", type: "integer", required: false, description: "Month of birth" },
  { id: "tf5", name: "day_of_birth", table: "person", type: "integer", required: false, description: "Day of birth" },
  { id: "tf6", name: "birth_datetime", table: "person", type: "datetime", required: false, description: "Full birth datetime" },
  { id: "tf7", name: "race_concept_id", table: "person", type: "integer", required: true, description: "Race concept from OMOP vocabulary" },
  { id: "tf8", name: "ethnicity_concept_id", table: "person", type: "integer", required: true, description: "Ethnicity concept from OMOP vocabulary" },
  { id: "tf9", name: "location_id", table: "person", type: "bigint", required: false, description: "Reference to location table" },
  { id: "tf10", name: "provider_id", table: "person", type: "bigint", required: false, description: "Reference to provider table" },
  { id: "tf11", name: "care_site_id", table: "person", type: "bigint", required: false, description: "Reference to care site table" },
  { id: "tf12", name: "person_source_value", table: "person", type: "varchar(50)", required: false, description: "Source identifier for the person" },
  { id: "tf13", name: "gender_source_value", table: "person", type: "varchar(50)", required: false, description: "Source value for gender" },
  { id: "tf14", name: "race_source_value", table: "person", type: "varchar(50)", required: false, description: "Source value for race" },
  { id: "tf15", name: "ethnicity_source_value", table: "person", type: "varchar(50)", required: false, description: "Source value for ethnicity" },
];

const MOCK_MAPPINGS: FieldMapping[] = [
  { id: "m1", sourceFieldId: "sf1", targetFieldId: "tf1", transformation: null, confidence: 95, status: "mapped" },
  { id: "m2", sourceFieldId: "sf2", targetFieldId: null, transformation: null, confidence: 0, status: "unmapped" },
  { id: "m3", sourceFieldId: "sf3", targetFieldId: null, transformation: null, confidence: 0, status: "unmapped" },
  { id: "m4", sourceFieldId: "sf4", targetFieldId: "tf6", transformation: "format_date", transformationConfig: { format: "YYYY-MM-DD" }, confidence: 90, status: "mapped" },
  { id: "m5", sourceFieldId: "sf5", targetFieldId: "tf2", transformation: "lookup_code", transformationConfig: { mapping: { M: 8507, F: 8532 } }, confidence: 85, status: "needs_review" },
  { id: "m6", sourceFieldId: "sf6", targetFieldId: "tf12", transformation: null, confidence: 80, status: "suggested" },
  { id: "m7", sourceFieldId: "sf7", targetFieldId: null, transformation: null, confidence: 0, status: "ignored" },
  { id: "m8", sourceFieldId: "sf8", targetFieldId: null, transformation: null, confidence: 0, status: "unmapped" },
  { id: "m9", sourceFieldId: "sf9", targetFieldId: null, transformation: null, confidence: 0, status: "unmapped" },
  { id: "m10", sourceFieldId: "sf10", targetFieldId: null, transformation: null, confidence: 0, status: "unmapped" },
  { id: "m11", sourceFieldId: "sf11", targetFieldId: null, transformation: null, confidence: 0, status: "unmapped" },
  { id: "m12", sourceFieldId: "sf12", targetFieldId: null, transformation: null, confidence: 0, status: "unmapped" },
  { id: "m13", sourceFieldId: "sf13", targetFieldId: null, transformation: null, confidence: 0, status: "unmapped" },
  { id: "m14", sourceFieldId: "sf14", targetFieldId: null, transformation: null, confidence: 0, status: "unmapped" },
  { id: "m15", sourceFieldId: "sf15", targetFieldId: null, transformation: null, confidence: 0, status: "unmapped" },
];

const MOCK_TEMPLATES: MappingTemplate[] = [
  { id: "t1", name: "FHIR R4 Patient to OMOP", description: "Standard mapping for FHIR R4 Patient resources", mappings: 24, lastUsed: "2024-01-15" },
  { id: "t2", name: "HL7v2 ADT to OMOP", description: "HL7 v2.x ADT message mapping", mappings: 18, lastUsed: "2024-01-10" },
  { id: "t3", name: "CSV Lab Results", description: "Generic CSV lab results mapping", mappings: 32, lastUsed: "2024-01-08" },
];

const TRANSFORMATION_OPTIONS: { value: TransformationType; label: string; icon: React.ReactNode }[] = [
  { value: "none", label: "No transformation", icon: <ArrowRight className="h-4 w-4" /> },
  { value: "format_date", label: "Format date", icon: <Calendar className="h-4 w-4" /> },
  { value: "convert_units", label: "Convert units", icon: <ArrowLeftRight className="h-4 w-4" /> },
  { value: "lookup_code", label: "Lookup code", icon: <Search className="h-4 w-4" /> },
  { value: "concatenate", label: "Concatenate", icon: <Braces className="h-4 w-4" /> },
  { value: "split", label: "Split", icon: <ArrowLeftRight className="h-4 w-4" /> },
  { value: "uppercase", label: "Uppercase", icon: <Type className="h-4 w-4" /> },
  { value: "lowercase", label: "Lowercase", icon: <Type className="h-4 w-4" /> },
  { value: "trim", label: "Trim whitespace", icon: <Type className="h-4 w-4" /> },
  { value: "custom", label: "Custom expression", icon: <Braces className="h-4 w-4" /> },
];

const OMOP_TABLES = ["person", "visit_occurrence", "condition_occurrence", "drug_exposure", "procedure_occurrence", "measurement", "observation"];

// =============================================================================
// Helper Functions
// =============================================================================

const getTypeIcon = (type: string) => {
  if (type.includes("int") || type.includes("bigint")) return <Hash className="h-4 w-4" />;
  if (type.includes("date") || type.includes("time")) return <Calendar className="h-4 w-4" />;
  return <Type className="h-4 w-4" />;
};

const getStatusBadge = (status: FieldMapping["status"]) => {
  switch (status) {
    case "mapped":
      return <Badge className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">Mapped</Badge>;
    case "suggested":
      return <Badge className="bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">Suggested</Badge>;
    case "needs_review":
      return <Badge className="bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400">Needs Review</Badge>;
    case "unmapped":
      return <Badge variant="outline" className="text-muted-foreground">Unmapped</Badge>;
    case "ignored":
      return <Badge variant="secondary">Ignored</Badge>;
  }
};

// =============================================================================
// Source Field Card (Draggable)
// =============================================================================

interface SourceFieldCardProps {
  field: SourceField;
  mapping: FieldMapping | undefined;
  isDragging?: boolean;
  onDragStart?: () => void;
  onDragEnd?: () => void;
}

function SourceFieldCard({ field, mapping, isDragging, onDragStart, onDragEnd }: SourceFieldCardProps) {
  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      className={`flex items-center gap-3 rounded-lg border bg-card p-3 transition-all ${
        isDragging ? "opacity-50 scale-95" : "cursor-grab hover:border-primary/50 hover:shadow-sm"
      } ${mapping?.status === "mapped" ? "border-green-500/30 bg-green-500/5" : ""}`}
    >
      <GripVertical className="h-4 w-4 text-muted-foreground flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          {getTypeIcon(field.type)}
          <span className="font-mono text-sm font-medium truncate">{field.name}</span>
          {!field.nullable && <span className="text-destructive">*</span>}
        </div>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-xs text-muted-foreground">{field.type}</span>
          {mapping && getStatusBadge(mapping.status)}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Target Field Card (Drop Zone)
// =============================================================================

interface TargetFieldCardProps {
  field: TargetField;
  mapping: FieldMapping | undefined;
  sourceField: SourceField | undefined;
  isDropTarget?: boolean;
  onDrop?: (sourceFieldId: string, targetFieldId: string) => void;
  onRemoveMapping?: () => void;
}

function TargetFieldCard({
  field,
  mapping,
  sourceField,
  isDropTarget,
  onDrop,
  onRemoveMapping,
}: TargetFieldCardProps) {
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const sourceFieldId = e.dataTransfer.getData("sourceFieldId");
    if (sourceFieldId && onDrop) {
      onDrop(sourceFieldId, field.id);
    }
  };

  return (
    <div
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      className={`rounded-lg border-2 border-dashed p-3 transition-all ${
        isDropTarget
          ? "border-primary bg-primary/5"
          : mapping
          ? "border-solid border-green-500/30 bg-green-500/5"
          : "border-muted hover:border-muted-foreground/30"
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {getTypeIcon(field.type)}
          <span className="font-mono text-sm font-medium">{field.name}</span>
          {field.required && <span className="text-destructive">*</span>}
        </div>
        {mapping && onRemoveMapping && (
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onRemoveMapping}>
            <X className="h-3 w-3" />
          </Button>
        )}
      </div>
      <div className="flex items-center gap-2 mt-1">
        <Badge variant="secondary" className="text-xs">{field.table}</Badge>
        <span className="text-xs text-muted-foreground">{field.type}</span>
      </div>
      {mapping && sourceField && (
        <div className="mt-2 pt-2 border-t flex items-center gap-2 text-xs">
          <ArrowLeft className="h-3 w-3 text-green-500" />
          <span className="font-mono">{sourceField.name}</span>
          {mapping.transformation && mapping.transformation !== "none" && (
            <Badge variant="outline" className="text-xs">
              {TRANSFORMATION_OPTIONS.find((t) => t.value === mapping.transformation)?.label}
            </Badge>
          )}
        </div>
      )}
      {!mapping && (
        <p className="mt-2 text-xs text-muted-foreground italic">
          Drop a source field here
        </p>
      )}
    </div>
  );
}

// =============================================================================
// Transformation Dialog
// =============================================================================

interface TransformationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mapping: FieldMapping | null;
  sourceField: SourceField | null;
  targetField: TargetField | null;
  onSave: (transformation: TransformationType, config?: Record<string, unknown>) => void;
}

function TransformationDialog({
  open,
  onOpenChange,
  mapping,
  sourceField,
  targetField,
  onSave,
}: TransformationDialogProps) {
  const [transformation, setTransformation] = useState<TransformationType>(mapping?.transformation || "none");
  const [dateFormat, setDateFormat] = useState("YYYY-MM-DD");
  const [lookupMapping, setLookupMapping] = useState<Record<string, string>>({});

  const handleSave = () => {
    let config: Record<string, unknown> | undefined;
    if (transformation === "format_date") {
      config = { format: dateFormat };
    } else if (transformation === "lookup_code") {
      config = { mapping: lookupMapping };
    }
    onSave(transformation, config);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Configure Transformation</DialogTitle>
          <DialogDescription>
            Set up data transformation from{" "}
            <span className="font-mono font-medium">{sourceField?.name}</span> to{" "}
            <span className="font-mono font-medium">{targetField?.name}</span>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label>Transformation Type</Label>
            <Select value={transformation} onValueChange={(v) => setTransformation(v as TransformationType)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TRANSFORMATION_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    <div className="flex items-center gap-2">
                      {opt.icon}
                      <span>{opt.label}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {transformation === "format_date" && (
            <div className="space-y-2">
              <Label>Date Format</Label>
              <Select value={dateFormat} onValueChange={setDateFormat}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="YYYY-MM-DD">YYYY-MM-DD (ISO)</SelectItem>
                  <SelectItem value="MM/DD/YYYY">MM/DD/YYYY</SelectItem>
                  <SelectItem value="DD/MM/YYYY">DD/MM/YYYY</SelectItem>
                  <SelectItem value="YYYY-MM-DD HH:mm:ss">YYYY-MM-DD HH:mm:ss</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          {transformation === "lookup_code" && (
            <div className="space-y-2">
              <Label>Value Mapping</Label>
              <div className="rounded-lg border p-3 space-y-2">
                {sourceField?.sampleValues.map((value, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <Input value={value} disabled className="flex-1 font-mono text-sm" />
                    <ArrowRight className="h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Concept ID"
                      className="flex-1 font-mono text-sm"
                      value={lookupMapping[value] || ""}
                      onChange={(e) => setLookupMapping((prev) => ({ ...prev, [value]: e.target.value }))}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {sourceField && (
            <div className="rounded-lg bg-muted/50 p-3">
              <p className="text-xs font-medium text-muted-foreground mb-2">Sample Values</p>
              <div className="flex flex-wrap gap-2">
                {sourceField.sampleValues.map((value, idx) => (
                  <Badge key={idx} variant="secondary" className="font-mono">
                    {value}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave}>
            <CheckCircle className="mr-2 h-4 w-4" />
            Apply Transformation
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// =============================================================================
// Import/Export Dialog
// =============================================================================

interface ImportExportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "import" | "export";
  onImport?: (file: File) => void;
  onExport?: () => void;
}

function ImportExportDialog({ open, onOpenChange, mode, onImport, onExport }: ImportExportDialogProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const handleImport = () => {
    if (selectedFile && onImport) {
      onImport(selectedFile);
      onOpenChange(false);
    }
  };

  const handleExport = () => {
    if (onExport) {
      onExport();
      onOpenChange(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{mode === "import" ? "Import Mapping Configuration" : "Export Mapping Configuration"}</DialogTitle>
          <DialogDescription>
            {mode === "import"
              ? "Upload a JSON file containing field mappings"
              : "Download the current field mappings as a JSON file"}
          </DialogDescription>
        </DialogHeader>

        {mode === "import" ? (
          <div className="space-y-4 py-4">
            <div className="rounded-lg border border-dashed p-8 text-center">
              <FileUp className="mx-auto h-12 w-12 text-muted-foreground" />
              <p className="mt-4 text-sm text-muted-foreground">
                Drag and drop a JSON file or click to browse
              </p>
              <input
                type="file"
                accept=".json"
                className="hidden"
                id="mapping-file"
                onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
              />
              <Button className="mt-4" variant="outline" asChild>
                <label htmlFor="mapping-file" className="cursor-pointer">
                  <Upload className="mr-2 h-4 w-4" />
                  Browse Files
                </label>
              </Button>
            </div>
            {selectedFile && (
              <div className="flex items-center gap-2 rounded-lg bg-muted p-3">
                <FileUp className="h-5 w-5" />
                <span className="flex-1 text-sm truncate">{selectedFile.name}</span>
                <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setSelectedFile(null)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            )}
          </div>
        ) : (
          <div className="py-4">
            <div className="rounded-lg bg-muted/50 p-4">
              <div className="flex items-center gap-3">
                <FileDown className="h-8 w-8 text-muted-foreground" />
                <div>
                  <p className="font-medium">mapping_config.json</p>
                  <p className="text-sm text-muted-foreground">Contains all field mappings and transformations</p>
                </div>
              </div>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          {mode === "import" ? (
            <Button onClick={handleImport} disabled={!selectedFile}>
              <Upload className="mr-2 h-4 w-4" />
              Import
            </Button>
          ) : (
            <Button onClick={handleExport}>
              <Download className="mr-2 h-4 w-4" />
              Export
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// =============================================================================
// Main Mapping Page Component
// =============================================================================

export default function MappingPage() {
  const [mappings, setMappings] = useState<FieldMapping[]>(MOCK_MAPPINGS);
  const [sourceFields] = useState<SourceField[]>(MOCK_SOURCE_FIELDS);
  const [targetFields] = useState<TargetField[]>(MOCK_TARGET_FIELDS);
  const [templates] = useState<MappingTemplate[]>(MOCK_TEMPLATES);

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTable, setSelectedTable] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const [draggingFieldId, setDraggingFieldId] = useState<string | null>(null);
  const [dropTargetId, setDropTargetId] = useState<string | null>(null);

  const [transformDialogOpen, setTransformDialogOpen] = useState(false);
  const [selectedMapping, setSelectedMapping] = useState<FieldMapping | null>(null);

  const [importExportOpen, setImportExportOpen] = useState(false);
  const [importExportMode, setImportExportMode] = useState<"import" | "export">("import");

  const [isSaving, setIsSaving] = useState(false);
  const [isAutoMapping, setIsAutoMapping] = useState(false);

  // Filter source fields
  const filteredSourceFields = sourceFields.filter((field) => {
    if (searchQuery && !field.name.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    const mapping = mappings.find((m) => m.sourceFieldId === field.id);
    if (statusFilter !== "all" && mapping?.status !== statusFilter) {
      return false;
    }
    return true;
  });

  // Filter target fields
  const filteredTargetFields = targetFields.filter((field) => {
    if (selectedTable !== "all" && field.table !== selectedTable) {
      return false;
    }
    return true;
  });

  // Get mapping for a source field
  const getMappingForSource = (sourceFieldId: string) =>
    mappings.find((m) => m.sourceFieldId === sourceFieldId);

  // Get mapping for a target field
  const getMappingForTarget = (targetFieldId: string) =>
    mappings.find((m) => m.targetFieldId === targetFieldId);

  // Handle drag start
  const handleDragStart = (fieldId: string) => {
    setDraggingFieldId(fieldId);
  };

  // Handle drop
  const handleDrop = (sourceFieldId: string, targetFieldId: string) => {
    setMappings((prev) =>
      prev.map((m) =>
        m.sourceFieldId === sourceFieldId
          ? { ...m, targetFieldId, status: "mapped" as const, confidence: 100 }
          : m
      )
    );
    setDraggingFieldId(null);
    setDropTargetId(null);
    toast.success("Field mapping created");
  };

  // Remove mapping
  const handleRemoveMapping = (mappingId: string) => {
    setMappings((prev) =>
      prev.map((m) =>
        m.id === mappingId
          ? { ...m, targetFieldId: null, status: "unmapped" as const, confidence: 0, transformation: null }
          : m
      )
    );
    toast.success("Mapping removed");
  };

  // Open transformation dialog
  const handleOpenTransformDialog = (mapping: FieldMapping) => {
    setSelectedMapping(mapping);
    setTransformDialogOpen(true);
  };

  // Save transformation
  const handleSaveTransformation = (transformation: TransformationType, config?: Record<string, unknown>) => {
    if (!selectedMapping) return;
    setMappings((prev) =>
      prev.map((m) =>
        m.id === selectedMapping.id
          ? { ...m, transformation, transformationConfig: config }
          : m
      )
    );
    toast.success("Transformation configured");
  };

  // Auto-map fields
  const handleAutoMap = async () => {
    setIsAutoMapping(true);
    await new Promise((resolve) => setTimeout(resolve, 1500));
    // Simulate auto-mapping
    toast.success("Auto-mapping complete. 8 new mappings suggested.");
    setIsAutoMapping(false);
  };

  // Save all mappings
  const handleSave = async () => {
    setIsSaving(true);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    toast.success("Mapping configuration saved");
    setIsSaving(false);
  };

  // Import/Export handlers
  const handleImport = (file: File) => {
    toast.success(`Imported mappings from ${file.name}`);
  };

  const handleExport = () => {
    toast.success("Mapping configuration exported");
  };

  // Calculate statistics
  const stats = {
    total: sourceFields.length,
    mapped: mappings.filter((m) => m.status === "mapped").length,
    suggested: mappings.filter((m) => m.status === "suggested").length,
    needsReview: mappings.filter((m) => m.status === "needs_review").length,
    unmapped: mappings.filter((m) => m.status === "unmapped").length,
    ignored: mappings.filter((m) => m.status === "ignored").length,
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Link
            href="/etl/sources"
            className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground mb-2"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Data Sources
          </Link>
          <h1 className="text-2xl font-bold tracking-tight">Field Mapping</h1>
          <p className="text-muted-foreground">
            Map source fields to OMOP CDM target fields with transformations
          </p>
        </div>
        <div className="flex gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <Settings2 className="mr-2 h-4 w-4" />
                Actions
                <ChevronDown className="ml-2 h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => { setImportExportMode("import"); setImportExportOpen(true); }}>
                <FileUp className="mr-2 h-4 w-4" />
                Import Mappings
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => { setImportExportMode("export"); setImportExportOpen(true); }}>
                <FileDown className="mr-2 h-4 w-4" />
                Export Mappings
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleAutoMap} disabled={isAutoMapping}>
                <Wand2 className="mr-2 h-4 w-4" />
                Auto-Map Fields
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button size="sm" onClick={handleSave} disabled={isSaving}>
            {isSaving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="mr-2 h-4 w-4" />
                Save Mappings
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Statistics */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-6">
        <Card>
          <CardContent className="p-4">
            <p className="text-2xl font-bold">{stats.total}</p>
            <p className="text-xs text-muted-foreground">Total Fields</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-2xl font-bold text-green-600">{stats.mapped}</p>
            <p className="text-xs text-muted-foreground">Mapped</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-2xl font-bold text-blue-600">{stats.suggested}</p>
            <p className="text-xs text-muted-foreground">Suggested</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-2xl font-bold text-yellow-600">{stats.needsReview}</p>
            <p className="text-xs text-muted-foreground">Needs Review</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-2xl font-bold text-muted-foreground">{stats.unmapped}</p>
            <p className="text-xs text-muted-foreground">Unmapped</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-2xl font-bold text-muted-foreground">{stats.ignored}</p>
            <p className="text-xs text-muted-foreground">Ignored</p>
          </CardContent>
        </Card>
      </div>

      {/* Progress Bar */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">Mapping Progress</span>
            <span className="text-sm text-muted-foreground">
              {Math.round((stats.mapped / stats.total) * 100)}% complete
            </span>
          </div>
          <Progress value={(stats.mapped / stats.total) * 100} className="h-2" />
        </CardContent>
      </Card>

      {/* Main Mapping Interface */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Source Fields */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">Source Fields</CardTitle>
                <CardDescription>
                  Drag fields to map them to OMOP CDM targets
                </CardDescription>
              </div>
            </div>
            <div className="flex gap-2 pt-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search fields..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-[140px]">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="mapped">Mapped</SelectItem>
                  <SelectItem value="suggested">Suggested</SelectItem>
                  <SelectItem value="needs_review">Needs Review</SelectItem>
                  <SelectItem value="unmapped">Unmapped</SelectItem>
                  <SelectItem value="ignored">Ignored</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[500px] pr-4">
              <div className="space-y-2">
                {filteredSourceFields.map((field) => {
                  const mapping = getMappingForSource(field.id);
                  return (
                    <div key={field.id} className="group">
                      <SourceFieldCard
                        field={field}
                        mapping={mapping}
                        isDragging={draggingFieldId === field.id}
                        onDragStart={() => handleDragStart(field.id)}
                        onDragEnd={() => setDraggingFieldId(null)}
                      />
                      {mapping && mapping.targetFieldId && (
                        <div className="ml-7 mt-1 flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs"
                            onClick={() => handleOpenTransformDialog(mapping)}
                          >
                            <Settings2 className="mr-1 h-3 w-3" />
                            Transform
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs text-destructive"
                            onClick={() => handleRemoveMapping(mapping.id)}
                          >
                            <Trash2 className="mr-1 h-3 w-3" />
                            Remove
                          </Button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Target Fields */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">OMOP CDM Target Fields</CardTitle>
                <CardDescription>
                  Drop source fields onto target fields to create mappings
                </CardDescription>
              </div>
            </div>
            <div className="pt-2">
              <Select value={selectedTable} onValueChange={setSelectedTable}>
                <SelectTrigger>
                  <SelectValue placeholder="Filter by table" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Tables</SelectItem>
                  {OMOP_TABLES.map((table) => (
                    <SelectItem key={table} value={table}>
                      {table}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[500px] pr-4">
              <div className="space-y-2">
                {filteredTargetFields.map((field) => {
                  const mapping = getMappingForTarget(field.id);
                  const sourceField = mapping
                    ? sourceFields.find((sf) => sf.id === mapping.sourceFieldId)
                    : undefined;
                  return (
                    <TargetFieldCard
                      key={field.id}
                      field={field}
                      mapping={mapping}
                      sourceField={sourceField}
                      isDropTarget={dropTargetId === field.id}
                      onDrop={handleDrop}
                      onRemoveMapping={
                        mapping ? () => handleRemoveMapping(mapping.id) : undefined
                      }
                    />
                  );
                })}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>

      {/* Mapping Templates */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Mapping Templates</CardTitle>
          <CardDescription>
            Load a pre-configured mapping template or save the current configuration
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {templates.map((template) => (
              <div
                key={template.id}
                className="flex items-center gap-4 rounded-lg border p-4 hover:bg-muted/50 cursor-pointer transition-colors"
              >
                <div className="flex-1">
                  <p className="font-medium">{template.name}</p>
                  <p className="text-sm text-muted-foreground line-clamp-1">
                    {template.description}
                  </p>
                  <div className="flex items-center gap-2 mt-2">
                    <Badge variant="secondary">{template.mappings} mappings</Badge>
                    <span className="text-xs text-muted-foreground">
                      Last used: {template.lastUsed}
                    </span>
                  </div>
                </div>
                <Button variant="outline" size="sm">
                  Load
                </Button>
              </div>
            ))}
          </div>
        </CardContent>
        <CardFooter className="border-t pt-4">
          <Button variant="outline">
            <Save className="mr-2 h-4 w-4" />
            Save as Template
          </Button>
        </CardFooter>
      </Card>

      {/* Transformation Dialog */}
      <TransformationDialog
        open={transformDialogOpen}
        onOpenChange={setTransformDialogOpen}
        mapping={selectedMapping}
        sourceField={selectedMapping ? sourceFields.find((f) => f.id === selectedMapping.sourceFieldId) || null : null}
        targetField={selectedMapping?.targetFieldId ? targetFields.find((f) => f.id === selectedMapping.targetFieldId) || null : null}
        onSave={handleSaveTransformation}
      />

      {/* Import/Export Dialog */}
      <ImportExportDialog
        open={importExportOpen}
        onOpenChange={setImportExportOpen}
        mode={importExportMode}
        onImport={handleImport}
        onExport={handleExport}
      />
    </div>
  );
}
