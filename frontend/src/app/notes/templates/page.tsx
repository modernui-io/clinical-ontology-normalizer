"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  CardFooter,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import {
  FileText,
  Plus,
  Search,
  Edit2,
  Trash2,
  Copy,
  Save,
  Eye,
  Settings,
  Layout,
  Type,
  Hash,
  Calendar,
  Clock,
  User,
  Stethoscope,
  Pill,
  Activity,
  FileSignature,
  GripVertical,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Download,
  Upload,
  Code,
  Braces,
  Check,
  X,
  Sparkles,
  Layers,
  LayoutGrid,
  ListTree,
} from "lucide-react";

// ============================================================================
// Types
// ============================================================================

type FieldType = "text" | "textarea" | "select" | "multiselect" | "date" | "datetime" | "number" | "checkbox" | "radio" | "section" | "divider" | "ai_assist";
type TemplateCategory = "progress" | "admission" | "discharge" | "consult" | "procedure" | "other";

interface TemplateField {
  id: string;
  name: string;
  label: string;
  type: FieldType;
  required: boolean;
  defaultValue?: string;
  placeholder?: string;
  options?: { value: string; label: string }[];
  validation?: {
    minLength?: number;
    maxLength?: number;
    pattern?: string;
  };
  aiAssist?: {
    enabled: boolean;
    prompt?: string;
    dataSource?: string[];
  };
  order: number;
}

interface NoteTemplate {
  id: string;
  name: string;
  description: string;
  category: TemplateCategory;
  version: string;
  isActive: boolean;
  isDefault: boolean;
  createdAt: string;
  updatedAt: string;
  createdBy: string;
  fields: TemplateField[];
  layout: "single" | "two-column" | "sections";
}

// ============================================================================
// Mock Data
// ============================================================================

const mockTemplates: NoteTemplate[] = [
  {
    id: "1",
    name: "Progress Note - Standard",
    description: "Standard daily progress note template with SOAP format",
    category: "progress",
    version: "2.1",
    isActive: true,
    isDefault: true,
    createdAt: "2024-01-15",
    updatedAt: "2024-02-10",
    createdBy: "Dr. Smith",
    layout: "sections",
    fields: [
      { id: "1", name: "subjective", label: "Subjective", type: "section", required: false, order: 1 },
      { id: "2", name: "chief_complaint", label: "Chief Complaint", type: "textarea", required: true, placeholder: "Patient's main concern in their own words", order: 2, aiAssist: { enabled: true, prompt: "Summarize patient's chief complaint", dataSource: ["recent_visits"] } },
      { id: "3", name: "hpi", label: "History of Present Illness", type: "textarea", required: true, placeholder: "Describe the HPI", order: 3, aiAssist: { enabled: true, prompt: "Generate HPI from symptoms", dataSource: ["symptoms", "timeline"] } },
      { id: "4", name: "ros", label: "Review of Systems", type: "multiselect", required: false, options: [{ value: "constitutional", label: "Constitutional" }, { value: "cardiovascular", label: "Cardiovascular" }, { value: "respiratory", label: "Respiratory" }, { value: "gi", label: "Gastrointestinal" }, { value: "neuro", label: "Neurological" }], order: 4 },
      { id: "5", name: "objective", label: "Objective", type: "section", required: false, order: 5 },
      { id: "6", name: "vitals", label: "Vital Signs", type: "text", required: true, placeholder: "BP, HR, RR, Temp, SpO2", order: 6, aiAssist: { enabled: true, dataSource: ["latest_vitals"] } },
      { id: "7", name: "physical_exam", label: "Physical Examination", type: "textarea", required: true, placeholder: "Document physical exam findings", order: 7 },
      { id: "8", name: "assessment", label: "Assessment", type: "section", required: false, order: 8 },
      { id: "9", name: "diagnoses", label: "Diagnoses", type: "textarea", required: true, placeholder: "List diagnoses with ICD-10 codes", order: 9, aiAssist: { enabled: true, prompt: "Suggest diagnoses based on findings", dataSource: ["findings", "history"] } },
      { id: "10", name: "plan", label: "Plan", type: "section", required: false, order: 10 },
      { id: "11", name: "treatment_plan", label: "Treatment Plan", type: "textarea", required: true, placeholder: "Document treatment plan", order: 11 },
      { id: "12", name: "follow_up", label: "Follow-up", type: "text", required: false, placeholder: "Follow-up instructions", order: 12 },
    ],
  },
  {
    id: "2",
    name: "Admission H&P",
    description: "Complete history and physical for hospital admission",
    category: "admission",
    version: "1.5",
    isActive: true,
    isDefault: false,
    createdAt: "2024-01-10",
    updatedAt: "2024-02-05",
    createdBy: "Dr. Johnson",
    layout: "two-column",
    fields: [
      { id: "1", name: "admission_date", label: "Admission Date/Time", type: "datetime", required: true, order: 1 },
      { id: "2", name: "admitting_diagnosis", label: "Admitting Diagnosis", type: "text", required: true, order: 2 },
      { id: "3", name: "chief_complaint", label: "Chief Complaint", type: "textarea", required: true, order: 3 },
      { id: "4", name: "hpi", label: "History of Present Illness", type: "textarea", required: true, order: 4, aiAssist: { enabled: true } },
      { id: "5", name: "pmh", label: "Past Medical History", type: "textarea", required: true, order: 5, aiAssist: { enabled: true, dataSource: ["conditions"] } },
      { id: "6", name: "psh", label: "Past Surgical History", type: "textarea", required: false, order: 6, aiAssist: { enabled: true, dataSource: ["procedures"] } },
      { id: "7", name: "medications", label: "Current Medications", type: "textarea", required: true, order: 7, aiAssist: { enabled: true, dataSource: ["medications"] } },
      { id: "8", name: "allergies", label: "Allergies", type: "textarea", required: true, order: 8, aiAssist: { enabled: true, dataSource: ["allergies"] } },
      { id: "9", name: "family_history", label: "Family History", type: "textarea", required: false, order: 9 },
      { id: "10", name: "social_history", label: "Social History", type: "textarea", required: true, order: 10 },
      { id: "11", name: "ros", label: "Review of Systems", type: "textarea", required: true, order: 11 },
      { id: "12", name: "physical_exam", label: "Physical Examination", type: "textarea", required: true, order: 12 },
      { id: "13", name: "assessment_plan", label: "Assessment & Plan", type: "textarea", required: true, order: 13 },
    ],
  },
  {
    id: "3",
    name: "Discharge Summary",
    description: "Comprehensive discharge summary template",
    category: "discharge",
    version: "2.0",
    isActive: true,
    isDefault: false,
    createdAt: "2024-01-12",
    updatedAt: "2024-02-08",
    createdBy: "Dr. Williams",
    layout: "sections",
    fields: [
      { id: "1", name: "patient_info", label: "Patient Information", type: "section", required: false, order: 1 },
      { id: "2", name: "admission_date", label: "Admission Date", type: "date", required: true, order: 2 },
      { id: "3", name: "discharge_date", label: "Discharge Date", type: "date", required: true, order: 3 },
      { id: "4", name: "discharge_disposition", label: "Discharge Disposition", type: "select", required: true, options: [{ value: "home", label: "Home" }, { value: "snf", label: "SNF" }, { value: "rehab", label: "Rehab" }, { value: "ltach", label: "LTACH" }, { value: "ama", label: "AMA" }], order: 4 },
      { id: "5", name: "hospital_course", label: "Hospital Course", type: "textarea", required: true, order: 5, aiAssist: { enabled: true, prompt: "Summarize hospital stay", dataSource: ["progress_notes", "events"] } },
      { id: "6", name: "discharge_diagnoses", label: "Discharge Diagnoses", type: "textarea", required: true, order: 6, aiAssist: { enabled: true, dataSource: ["diagnoses"] } },
      { id: "7", name: "discharge_meds", label: "Discharge Medications", type: "textarea", required: true, order: 7, aiAssist: { enabled: true, dataSource: ["medications"] } },
      { id: "8", name: "follow_up", label: "Follow-up Appointments", type: "textarea", required: true, order: 8 },
      { id: "9", name: "patient_instructions", label: "Patient Instructions", type: "textarea", required: true, order: 9, aiAssist: { enabled: true, prompt: "Generate patient-friendly instructions" } },
    ],
  },
  {
    id: "4",
    name: "Consult Note",
    description: "Specialist consultation note template",
    category: "consult",
    version: "1.2",
    isActive: true,
    isDefault: false,
    createdAt: "2024-01-20",
    updatedAt: "2024-02-01",
    createdBy: "Dr. Brown",
    layout: "single",
    fields: [
      { id: "1", name: "consult_date", label: "Consultation Date", type: "datetime", required: true, order: 1 },
      { id: "2", name: "referring_provider", label: "Referring Provider", type: "text", required: true, order: 2 },
      { id: "3", name: "reason", label: "Reason for Consultation", type: "textarea", required: true, order: 3 },
      { id: "4", name: "findings", label: "Findings", type: "textarea", required: true, order: 4 },
      { id: "5", name: "recommendations", label: "Recommendations", type: "textarea", required: true, order: 5, aiAssist: { enabled: true } },
    ],
  },
  {
    id: "5",
    name: "Procedure Note - Brief",
    description: "Brief procedure documentation template",
    category: "procedure",
    version: "1.0",
    isActive: false,
    isDefault: false,
    createdAt: "2024-01-25",
    updatedAt: "2024-01-25",
    createdBy: "Dr. Davis",
    layout: "single",
    fields: [
      { id: "1", name: "procedure_date", label: "Procedure Date/Time", type: "datetime", required: true, order: 1 },
      { id: "2", name: "procedure_name", label: "Procedure Name", type: "text", required: true, order: 2 },
      { id: "3", name: "indication", label: "Indication", type: "textarea", required: true, order: 3 },
      { id: "4", name: "anesthesia", label: "Anesthesia", type: "select", required: true, options: [{ value: "local", label: "Local" }, { value: "moderate", label: "Moderate Sedation" }, { value: "general", label: "General" }, { value: "none", label: "None" }], order: 4 },
      { id: "5", name: "description", label: "Procedure Description", type: "textarea", required: true, order: 5 },
      { id: "6", name: "complications", label: "Complications", type: "textarea", required: false, defaultValue: "None", order: 6 },
      { id: "7", name: "specimens", label: "Specimens", type: "textarea", required: false, order: 7 },
      { id: "8", name: "post_procedure", label: "Post-Procedure Plan", type: "textarea", required: true, order: 8 },
    ],
  },
];

const fieldTypes: { value: FieldType; label: string; icon: React.ReactNode }[] = [
  { value: "text", label: "Short Text", icon: <Type className="h-4 w-4" /> },
  { value: "textarea", label: "Long Text", icon: <FileText className="h-4 w-4" /> },
  { value: "select", label: "Dropdown", icon: <ChevronDown className="h-4 w-4" /> },
  { value: "multiselect", label: "Multi-Select", icon: <ListTree className="h-4 w-4" /> },
  { value: "date", label: "Date", icon: <Calendar className="h-4 w-4" /> },
  { value: "datetime", label: "Date & Time", icon: <Clock className="h-4 w-4" /> },
  { value: "number", label: "Number", icon: <Hash className="h-4 w-4" /> },
  { value: "checkbox", label: "Checkbox", icon: <Check className="h-4 w-4" /> },
  { value: "section", label: "Section Header", icon: <Layout className="h-4 w-4" /> },
  { value: "divider", label: "Divider", icon: <Layers className="h-4 w-4" /> },
  { value: "ai_assist", label: "AI-Assisted", icon: <Sparkles className="h-4 w-4" /> },
];

// ============================================================================
// Helper Functions
// ============================================================================

const getCategoryColor = (category: TemplateCategory) => {
  switch (category) {
    case "progress":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
    case "admission":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
    case "discharge":
      return "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200";
    case "consult":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
    case "procedure":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
    default:
      return "bg-gray-100 text-gray-800";
  }
};

const getCategoryIcon = (category: TemplateCategory) => {
  switch (category) {
    case "progress":
      return <Activity className="h-4 w-4" />;
    case "admission":
      return <User className="h-4 w-4" />;
    case "discharge":
      return <FileSignature className="h-4 w-4" />;
    case "consult":
      return <Stethoscope className="h-4 w-4" />;
    case "procedure":
      return <Pill className="h-4 w-4" />;
    default:
      return <FileText className="h-4 w-4" />;
  }
};

// ============================================================================
// Field Editor Component
// ============================================================================

function FieldEditor({
  field,
  onUpdate,
  onDelete,
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
}: {
  field: TemplateField;
  onUpdate: (field: TemplateField) => void;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  isFirst: boolean;
  isLast: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="border rounded-lg p-3 bg-card">
      <div className="flex items-center gap-3">
        <div className="cursor-move text-muted-foreground">
          <GripVertical className="h-4 w-4" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="font-medium">{field.label}</span>
            <Badge variant="outline" className="text-xs">{field.type}</Badge>
            {field.required && <Badge className="bg-red-100 text-red-800 text-xs">Required</Badge>}
            {field.aiAssist?.enabled && (
              <Badge className="bg-purple-100 text-purple-800 text-xs">
                <Sparkles className="h-3 w-3 mr-1" />
                AI
              </Badge>
            )}
          </div>
          <div className="text-xs text-muted-foreground">{field.name}</div>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" onClick={onMoveUp} disabled={isFirst}>
            <ChevronUp className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm" onClick={onMoveDown} disabled={isLast}>
            <ChevronDown className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setIsExpanded(!isExpanded)}>
            <Settings className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm" onClick={onDelete}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {isExpanded && (
        <div className="mt-4 pt-4 border-t space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Field Name</Label>
              <Input
                value={field.name}
                onChange={(e) => onUpdate({ ...field, name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Label</Label>
              <Input
                value={field.label}
                onChange={(e) => onUpdate({ ...field, label: e.target.value })}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Field Type</Label>
              <Select
                value={field.type}
                onValueChange={(v) => onUpdate({ ...field, type: v as FieldType })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {fieldTypes.map(ft => (
                    <SelectItem key={ft.value} value={ft.value}>
                      <div className="flex items-center gap-2">
                        {ft.icon}
                        {ft.label}
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Placeholder</Label>
              <Input
                value={field.placeholder || ""}
                onChange={(e) => onUpdate({ ...field, placeholder: e.target.value })}
              />
            </div>
          </div>
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <Checkbox
                id={`required-${field.id}`}
                checked={field.required}
                onCheckedChange={(c) => onUpdate({ ...field, required: c === true })}
              />
              <Label htmlFor={`required-${field.id}`}>Required</Label>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id={`ai-${field.id}`}
                checked={field.aiAssist?.enabled || false}
                onCheckedChange={(c) =>
                  onUpdate({
                    ...field,
                    aiAssist: { ...field.aiAssist, enabled: c === true },
                  })
                }
              />
              <Label htmlFor={`ai-${field.id}`}>Enable AI Assist</Label>
            </div>
          </div>
          {field.aiAssist?.enabled && (
            <div className="space-y-2 p-3 bg-purple-50 dark:bg-purple-950 rounded-lg">
              <Label>AI Prompt</Label>
              <Textarea
                value={field.aiAssist?.prompt || ""}
                onChange={(e) =>
                  onUpdate({
                    ...field,
                    aiAssist: { ...field.aiAssist, enabled: true, prompt: e.target.value },
                  })
                }
                placeholder="Instructions for AI assistance..."
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function NoteTemplatesPage() {
  const [templates, setTemplates] = useState<NoteTemplate[]>(mockTemplates);
  const [selectedTemplate, setSelectedTemplate] = useState<NoteTemplate | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [activeTab, setActiveTab] = useState("templates");
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [editingFields, setEditingFields] = useState<TemplateField[]>([]);

  // Filter templates
  const filteredTemplates = useMemo(() => {
    return templates.filter(t => {
      const matchesSearch = searchQuery === "" ||
        t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.description.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesCategory = categoryFilter === "all" || t.category === categoryFilter;
      return matchesSearch && matchesCategory;
    });
  }, [templates, searchQuery, categoryFilter]);

  const handleSelectTemplate = (template: NoteTemplate) => {
    setSelectedTemplate(template);
    setEditingFields([...template.fields]);
    setActiveTab("editor");
  };

  const handleUpdateField = (updatedField: TemplateField) => {
    setEditingFields(fields =>
      fields.map(f => (f.id === updatedField.id ? updatedField : f))
    );
  };

  const handleDeleteField = (fieldId: string) => {
    setEditingFields(fields => fields.filter(f => f.id !== fieldId));
  };

  const handleMoveField = (fieldId: string, direction: "up" | "down") => {
    setEditingFields(fields => {
      const index = fields.findIndex(f => f.id === fieldId);
      if (index === -1) return fields;
      if (direction === "up" && index === 0) return fields;
      if (direction === "down" && index === fields.length - 1) return fields;

      const newFields = [...fields];
      const swapIndex = direction === "up" ? index - 1 : index + 1;
      [newFields[index], newFields[swapIndex]] = [newFields[swapIndex], newFields[index]];

      // Update order values
      return newFields.map((f, i) => ({ ...f, order: i + 1 }));
    });
  };

  const handleAddField = () => {
    const newField: TemplateField = {
      id: String(Date.now()),
      name: `field_${editingFields.length + 1}`,
      label: "New Field",
      type: "text",
      required: false,
      order: editingFields.length + 1,
    };
    setEditingFields([...editingFields, newField]);
  };

  const handleSaveTemplate = () => {
    if (!selectedTemplate) return;
    const updatedTemplate = {
      ...selectedTemplate,
      fields: editingFields,
      updatedAt: new Date().toISOString().split("T")[0],
    };
    setTemplates(templates.map(t => (t.id === updatedTemplate.id ? updatedTemplate : t)));
    setSelectedTemplate(updatedTemplate);
    setIsEditing(false);
  };

  const handleDuplicateTemplate = (template: NoteTemplate) => {
    const duplicated: NoteTemplate = {
      ...template,
      id: String(Date.now()),
      name: `${template.name} (Copy)`,
      isDefault: false,
      createdAt: new Date().toISOString().split("T")[0],
      updatedAt: new Date().toISOString().split("T")[0],
    };
    setTemplates([...templates, duplicated]);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Note Templates</h1>
          <p className="text-muted-foreground">
            Create and customize clinical note templates
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm">
            <Upload className="mr-2 h-4 w-4" />
            Import
          </Button>
          <Button variant="outline" size="sm">
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
          <Dialog>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                New Template
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create New Template</DialogTitle>
                <DialogDescription>
                  Start with a blank template or choose from presets
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="space-y-2">
                  <Label>Template Name</Label>
                  <Input placeholder="e.g., Progress Note - Cardiology" />
                </div>
                <div className="space-y-2">
                  <Label>Category</Label>
                  <Select defaultValue="progress">
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="progress">Progress Note</SelectItem>
                      <SelectItem value="admission">Admission</SelectItem>
                      <SelectItem value="discharge">Discharge</SelectItem>
                      <SelectItem value="consult">Consultation</SelectItem>
                      <SelectItem value="procedure">Procedure</SelectItem>
                      <SelectItem value="other">Other</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Description</Label>
                  <Textarea placeholder="Brief description of the template" />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline">Cancel</Button>
                <Button>Create Template</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="templates">Templates</TabsTrigger>
          <TabsTrigger value="editor" disabled={!selectedTemplate}>Editor</TabsTrigger>
          <TabsTrigger value="preview" disabled={!selectedTemplate}>Preview</TabsTrigger>
        </TabsList>

        <TabsContent value="templates" className="space-y-4">
          {/* Filters */}
          <div className="flex items-center gap-4">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search templates..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8"
              />
            </div>
            <Select value={categoryFilter} onValueChange={setCategoryFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Categories</SelectItem>
                <SelectItem value="progress">Progress Notes</SelectItem>
                <SelectItem value="admission">Admission</SelectItem>
                <SelectItem value="discharge">Discharge</SelectItem>
                <SelectItem value="consult">Consultation</SelectItem>
                <SelectItem value="procedure">Procedure</SelectItem>
                <SelectItem value="other">Other</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Templates Grid */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filteredTemplates.map((template) => (
              <Card key={template.id} className={`cursor-pointer hover:border-primary transition-colors ${!template.isActive ? "opacity-60" : ""}`}>
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      {getCategoryIcon(template.category)}
                      <CardTitle className="text-lg">{template.name}</CardTitle>
                    </div>
                    {template.isDefault && (
                      <Badge variant="secondary">Default</Badge>
                    )}
                  </div>
                  <CardDescription>{template.description}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2 mb-3">
                    <Badge className={getCategoryColor(template.category)}>
                      {template.category}
                    </Badge>
                    <Badge variant="outline">v{template.version}</Badge>
                    <Badge variant={template.isActive ? "default" : "secondary"}>
                      {template.isActive ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    <span>{template.fields.length} fields</span>
                    <span>{template.fields.filter(f => f.aiAssist?.enabled).length} AI-assisted</span>
                  </div>
                </CardContent>
                <CardFooter className="flex justify-between pt-0">
                  <div className="text-xs text-muted-foreground">
                    Updated {template.updatedAt}
                  </div>
                  <div className="flex gap-1">
                    <Button variant="ghost" size="sm" onClick={() => handleDuplicateTemplate(template)}>
                      <Copy className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => handleSelectTemplate(template)}>
                      <Edit2 className="h-4 w-4" />
                    </Button>
                  </div>
                </CardFooter>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="editor" className="space-y-4">
          {selectedTemplate && (
            <>
              {/* Template Info */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle>{selectedTemplate.name}</CardTitle>
                      <CardDescription>{selectedTemplate.description}</CardDescription>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2">
                        <Label>Layout</Label>
                        <Select defaultValue={selectedTemplate.layout}>
                          <SelectTrigger className="w-[150px]">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="single">Single Column</SelectItem>
                            <SelectItem value="two-column">Two Columns</SelectItem>
                            <SelectItem value="sections">Sections</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="flex items-center gap-2">
                        <Switch
                          checked={selectedTemplate.isActive}
                          onCheckedChange={(c) =>
                            setSelectedTemplate({ ...selectedTemplate, isActive: c })
                          }
                        />
                        <Label>Active</Label>
                      </div>
                    </div>
                  </div>
                </CardHeader>
              </Card>

              {/* Fields Editor */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle>Template Fields</CardTitle>
                    <Button onClick={handleAddField}>
                      <Plus className="mr-2 h-4 w-4" />
                      Add Field
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <ScrollArea className="h-[500px] pr-4">
                    <div className="space-y-3">
                      {editingFields.map((field, index) => (
                        <FieldEditor
                          key={field.id}
                          field={field}
                          onUpdate={handleUpdateField}
                          onDelete={() => handleDeleteField(field.id)}
                          onMoveUp={() => handleMoveField(field.id, "up")}
                          onMoveDown={() => handleMoveField(field.id, "down")}
                          isFirst={index === 0}
                          isLast={index === editingFields.length - 1}
                        />
                      ))}
                    </div>
                  </ScrollArea>
                </CardContent>
                <CardFooter className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setEditingFields([...selectedTemplate.fields])}>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Reset
                  </Button>
                  <Button onClick={handleSaveTemplate}>
                    <Save className="mr-2 h-4 w-4" />
                    Save Template
                  </Button>
                </CardFooter>
              </Card>
            </>
          )}
        </TabsContent>

        <TabsContent value="preview" className="space-y-4">
          {selectedTemplate && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>Template Preview</CardTitle>
                  <Button variant="outline" size="sm">
                    <Eye className="mr-2 h-4 w-4" />
                    Full Screen
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className={`space-y-4 ${selectedTemplate.layout === "two-column" ? "grid grid-cols-2 gap-4" : ""}`}>
                  {editingFields.map((field) => {
                    if (field.type === "section") {
                      return (
                        <div key={field.id} className={selectedTemplate.layout === "two-column" ? "col-span-2" : ""}>
                          <h3 className="text-lg font-semibold border-b pb-2 mb-4">{field.label}</h3>
                        </div>
                      );
                    }
                    if (field.type === "divider") {
                      return <Separator key={field.id} className={selectedTemplate.layout === "two-column" ? "col-span-2" : ""} />;
                    }
                    return (
                      <div key={field.id} className="space-y-2">
                        <Label className="flex items-center gap-2">
                          {field.label}
                          {field.required && <span className="text-red-500">*</span>}
                          {field.aiAssist?.enabled && (
                            <Sparkles className="h-3 w-3 text-purple-500" />
                          )}
                        </Label>
                        {field.type === "text" && (
                          <Input placeholder={field.placeholder} defaultValue={field.defaultValue} />
                        )}
                        {field.type === "textarea" && (
                          <Textarea placeholder={field.placeholder} defaultValue={field.defaultValue} />
                        )}
                        {field.type === "select" && (
                          <Select defaultValue={field.defaultValue}>
                            <SelectTrigger>
                              <SelectValue placeholder={field.placeholder || "Select..."} />
                            </SelectTrigger>
                            <SelectContent>
                              {field.options?.map(opt => (
                                <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        )}
                        {field.type === "date" && (
                          <Input type="date" defaultValue={field.defaultValue} />
                        )}
                        {field.type === "datetime" && (
                          <Input type="datetime-local" defaultValue={field.defaultValue} />
                        )}
                        {field.type === "number" && (
                          <Input type="number" placeholder={field.placeholder} defaultValue={field.defaultValue} />
                        )}
                        {field.type === "checkbox" && (
                          <div className="flex items-center gap-2">
                            <Checkbox id={field.id} />
                            <Label htmlFor={field.id}>{field.placeholder || field.label}</Label>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
