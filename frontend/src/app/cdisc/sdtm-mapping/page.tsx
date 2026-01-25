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
import { Progress } from "@/components/ui/progress";
import {
  ArrowRight,
  Database,
  FileSpreadsheet,
  Layers,
  Plus,
  Save,
  Trash2,
  Edit2,
  Check,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Upload,
  Download,
  RefreshCw,
  Play,
  Settings,
  Eye,
  Link2,
  Search,
  Zap,
  Info,
  X,
} from "lucide-react";

// ============================================================================
// Types
// ============================================================================

interface SourceColumn {
  id: string;
  name: string;
  dataType: string;
  sampleValues: string[];
  nullPercentage: number;
  uniqueCount: number;
}

interface SDTMVariable {
  name: string;
  label: string;
  type: string;
  codelistCode?: string;
  core: "Req" | "Exp" | "Perm";
  description: string;
}

interface SDTMDomain {
  code: string;
  name: string;
  description: string;
  class: string;
  variables: SDTMVariable[];
}

interface ColumnMapping {
  id: string;
  sourceColumn: string;
  targetDomain: string;
  targetVariable: string;
  transformationType: "direct" | "lookup" | "derived" | "constant" | "expression";
  transformation?: string;
  codelistMapping?: string;
  validationStatus: "valid" | "warning" | "error" | "pending";
  validationMessage?: string;
}

interface MappingProject {
  id: string;
  name: string;
  description: string;
  sourceFile: string;
  targetVersion: string;
  createdAt: string;
  updatedAt: string;
  status: "draft" | "in_progress" | "validated" | "complete";
  mappingProgress: number;
  mappingCount: number;
}

// ============================================================================
// Mock Data
// ============================================================================

const mockSourceColumns: SourceColumn[] = [
  { id: "1", name: "subject_id", dataType: "VARCHAR(50)", sampleValues: ["SUBJ001", "SUBJ002", "SUBJ003"], nullPercentage: 0, uniqueCount: 1500 },
  { id: "2", name: "visit_date", dataType: "DATE", sampleValues: ["2024-01-15", "2024-02-20", "2024-03-10"], nullPercentage: 2.3, uniqueCount: 450 },
  { id: "3", name: "age_years", dataType: "INTEGER", sampleValues: ["45", "67", "52"], nullPercentage: 0.5, uniqueCount: 75 },
  { id: "4", name: "sex_code", dataType: "CHAR(1)", sampleValues: ["M", "F", "M"], nullPercentage: 0, uniqueCount: 2 },
  { id: "5", name: "race_desc", dataType: "VARCHAR(100)", sampleValues: ["White", "Black or African American", "Asian"], nullPercentage: 5.2, uniqueCount: 8 },
  { id: "6", name: "ethnic_group", dataType: "VARCHAR(50)", sampleValues: ["Not Hispanic", "Hispanic", "Unknown"], nullPercentage: 8.1, uniqueCount: 3 },
  { id: "7", name: "height_cm", dataType: "DECIMAL(5,2)", sampleValues: ["175.5", "162.3", "180.0"], nullPercentage: 3.2, uniqueCount: 280 },
  { id: "8", name: "weight_kg", dataType: "DECIMAL(5,2)", sampleValues: ["72.5", "85.0", "65.2"], nullPercentage: 2.8, uniqueCount: 320 },
  { id: "9", name: "bp_systolic", dataType: "INTEGER", sampleValues: ["120", "135", "142"], nullPercentage: 4.5, uniqueCount: 95 },
  { id: "10", name: "bp_diastolic", dataType: "INTEGER", sampleValues: ["80", "85", "92"], nullPercentage: 4.5, uniqueCount: 70 },
  { id: "11", name: "ae_term", dataType: "VARCHAR(200)", sampleValues: ["Headache", "Nausea", "Fatigue"], nullPercentage: 0, uniqueCount: 156 },
  { id: "12", name: "ae_severity", dataType: "VARCHAR(20)", sampleValues: ["Mild", "Moderate", "Severe"], nullPercentage: 1.2, uniqueCount: 3 },
  { id: "13", name: "medication_name", dataType: "VARCHAR(200)", sampleValues: ["Aspirin", "Metformin", "Lisinopril"], nullPercentage: 0, uniqueCount: 245 },
  { id: "14", name: "dose_value", dataType: "DECIMAL(10,2)", sampleValues: ["100", "500", "10"], nullPercentage: 0.8, uniqueCount: 85 },
  { id: "15", name: "dose_unit", dataType: "VARCHAR(20)", sampleValues: ["mg", "mcg", "mL"], nullPercentage: 0.8, uniqueCount: 12 },
];

const mockSDTMDomains: SDTMDomain[] = [
  {
    code: "DM",
    name: "Demographics",
    description: "Subject demographic information",
    class: "Special Purpose",
    variables: [
      { name: "STUDYID", label: "Study Identifier", type: "Char", core: "Req", description: "Unique identifier for a study" },
      { name: "DOMAIN", label: "Domain Abbreviation", type: "Char", core: "Req", description: "Two-character abbreviation" },
      { name: "USUBJID", label: "Unique Subject Identifier", type: "Char", core: "Req", description: "Unique subject identifier" },
      { name: "SUBJID", label: "Subject Identifier", type: "Char", core: "Req", description: "Subject identifier for the study" },
      { name: "AGE", label: "Age", type: "Num", core: "Exp", description: "Age at consent" },
      { name: "AGEU", label: "Age Units", type: "Char", codelistCode: "C66781", core: "Exp", description: "Age units" },
      { name: "SEX", label: "Sex", type: "Char", codelistCode: "C66731", core: "Req", description: "Sex of the subject" },
      { name: "RACE", label: "Race", type: "Char", codelistCode: "C74457", core: "Exp", description: "Race of the subject" },
      { name: "ETHNIC", label: "Ethnicity", type: "Char", codelistCode: "C66790", core: "Perm", description: "Ethnicity of the subject" },
    ],
  },
  {
    code: "VS",
    name: "Vital Signs",
    description: "Subject vital signs measurements",
    class: "Findings",
    variables: [
      { name: "STUDYID", label: "Study Identifier", type: "Char", core: "Req", description: "Unique identifier for a study" },
      { name: "DOMAIN", label: "Domain Abbreviation", type: "Char", core: "Req", description: "Two-character abbreviation" },
      { name: "USUBJID", label: "Unique Subject Identifier", type: "Char", core: "Req", description: "Unique subject identifier" },
      { name: "VSSEQ", label: "Sequence Number", type: "Num", core: "Req", description: "Sequence number" },
      { name: "VSTESTCD", label: "Vital Signs Test Short Name", type: "Char", codelistCode: "C66741", core: "Req", description: "Test short name" },
      { name: "VSTEST", label: "Vital Signs Test Name", type: "Char", codelistCode: "C67153", core: "Req", description: "Full test name" },
      { name: "VSORRES", label: "Result or Finding in Original Units", type: "Char", core: "Exp", description: "Original result" },
      { name: "VSORRESU", label: "Original Units", type: "Char", codelistCode: "C66770", core: "Exp", description: "Units for original result" },
      { name: "VSSTRESC", label: "Character Result/Finding in Std Format", type: "Char", core: "Exp", description: "Standardized result" },
      { name: "VSSTRESN", label: "Numeric Result/Finding in Standard Units", type: "Num", core: "Exp", description: "Numeric standardized result" },
      { name: "VSSTRESU", label: "Standard Units", type: "Char", codelistCode: "C66770", core: "Exp", description: "Standard units" },
      { name: "VSDTC", label: "Date/Time of Measurements", type: "Char", core: "Exp", description: "Date/time of measurements in ISO 8601" },
    ],
  },
  {
    code: "AE",
    name: "Adverse Events",
    description: "Adverse event information",
    class: "Events",
    variables: [
      { name: "STUDYID", label: "Study Identifier", type: "Char", core: "Req", description: "Unique identifier for a study" },
      { name: "DOMAIN", label: "Domain Abbreviation", type: "Char", core: "Req", description: "Two-character abbreviation" },
      { name: "USUBJID", label: "Unique Subject Identifier", type: "Char", core: "Req", description: "Unique subject identifier" },
      { name: "AESEQ", label: "Sequence Number", type: "Num", core: "Req", description: "Sequence number" },
      { name: "AETERM", label: "Reported Term for the Adverse Event", type: "Char", core: "Req", description: "Verbatim term" },
      { name: "AEDECOD", label: "Dictionary-Derived Term", type: "Char", core: "Req", description: "MedDRA PT" },
      { name: "AEBODSYS", label: "Body System or Organ Class", type: "Char", core: "Exp", description: "MedDRA SOC" },
      { name: "AESEV", label: "Severity/Intensity", type: "Char", codelistCode: "C66769", core: "Exp", description: "Severity" },
      { name: "AESER", label: "Serious Event", type: "Char", codelistCode: "C66742", core: "Exp", description: "Serious event flag" },
      { name: "AESTDTC", label: "Start Date/Time of Adverse Event", type: "Char", core: "Exp", description: "Start date/time in ISO 8601" },
      { name: "AEENDTC", label: "End Date/Time of Adverse Event", type: "Char", core: "Exp", description: "End date/time in ISO 8601" },
    ],
  },
  {
    code: "CM",
    name: "Concomitant Medications",
    description: "Concomitant medication information",
    class: "Interventions",
    variables: [
      { name: "STUDYID", label: "Study Identifier", type: "Char", core: "Req", description: "Unique identifier for a study" },
      { name: "DOMAIN", label: "Domain Abbreviation", type: "Char", core: "Req", description: "Two-character abbreviation" },
      { name: "USUBJID", label: "Unique Subject Identifier", type: "Char", core: "Req", description: "Unique subject identifier" },
      { name: "CMSEQ", label: "Sequence Number", type: "Num", core: "Req", description: "Sequence number" },
      { name: "CMTRT", label: "Reported Name of Drug, Med, or Therapy", type: "Char", core: "Req", description: "Verbatim medication name" },
      { name: "CMDECOD", label: "Standardized Medication Name", type: "Char", core: "Exp", description: "WHO Drug name" },
      { name: "CMDOSE", label: "Dose per Administration", type: "Num", core: "Exp", description: "Dose amount" },
      { name: "CMDOSU", label: "Dose Units", type: "Char", codelistCode: "C71620", core: "Exp", description: "Dose units" },
      { name: "CMDOSFRQ", label: "Dosing Frequency per Interval", type: "Char", codelistCode: "C71113", core: "Exp", description: "Dosing frequency" },
      { name: "CMSTDTC", label: "Start Date/Time of Medication", type: "Char", core: "Exp", description: "Start date/time in ISO 8601" },
      { name: "CMENDTC", label: "End Date/Time of Medication", type: "Char", core: "Exp", description: "End date/time in ISO 8601" },
    ],
  },
];

const mockMappings: ColumnMapping[] = [
  { id: "1", sourceColumn: "subject_id", targetDomain: "DM", targetVariable: "USUBJID", transformationType: "expression", transformation: "concat(STUDYID, '-', subject_id)", validationStatus: "valid" },
  { id: "2", sourceColumn: "subject_id", targetDomain: "DM", targetVariable: "SUBJID", transformationType: "direct", validationStatus: "valid" },
  { id: "3", sourceColumn: "age_years", targetDomain: "DM", targetVariable: "AGE", transformationType: "direct", validationStatus: "valid" },
  { id: "4", sourceColumn: "sex_code", targetDomain: "DM", targetVariable: "SEX", transformationType: "lookup", codelistMapping: "M=M,F=F", validationStatus: "valid" },
  { id: "5", sourceColumn: "race_desc", targetDomain: "DM", targetVariable: "RACE", transformationType: "lookup", codelistMapping: "See C74457 mapping", validationStatus: "warning", validationMessage: "3 unmapped values found" },
  { id: "6", sourceColumn: "ethnic_group", targetDomain: "DM", targetVariable: "ETHNIC", transformationType: "lookup", codelistMapping: "See C66790 mapping", validationStatus: "valid" },
  { id: "7", sourceColumn: "height_cm", targetDomain: "VS", targetVariable: "VSORRES", transformationType: "direct", validationStatus: "valid" },
  { id: "8", sourceColumn: "weight_kg", targetDomain: "VS", targetVariable: "VSORRES", transformationType: "direct", validationStatus: "valid" },
  { id: "9", sourceColumn: "bp_systolic", targetDomain: "VS", targetVariable: "VSORRES", transformationType: "direct", validationStatus: "valid" },
  { id: "10", sourceColumn: "ae_term", targetDomain: "AE", targetVariable: "AETERM", transformationType: "direct", validationStatus: "valid" },
  { id: "11", sourceColumn: "ae_severity", targetDomain: "AE", targetVariable: "AESEV", transformationType: "lookup", codelistMapping: "Mild=MILD,Moderate=MODERATE,Severe=SEVERE", validationStatus: "valid" },
  { id: "12", sourceColumn: "medication_name", targetDomain: "CM", targetVariable: "CMTRT", transformationType: "direct", validationStatus: "valid" },
  { id: "13", sourceColumn: "dose_value", targetDomain: "CM", targetVariable: "CMDOSE", transformationType: "direct", validationStatus: "error", validationMessage: "Non-numeric values detected in 5 records" },
  { id: "14", sourceColumn: "dose_unit", targetDomain: "CM", targetVariable: "CMDOSU", transformationType: "lookup", codelistMapping: "See C71620 mapping", validationStatus: "warning", validationMessage: "2 unmapped unit values" },
];

const mockProjects: MappingProject[] = [
  { id: "1", name: "Study ABC-123 SDTM Mapping", description: "Phase 2 clinical trial data mapping", sourceFile: "abc123_raw_data.csv", targetVersion: "SDTM 3.4", createdAt: "2024-01-15", updatedAt: "2024-02-10", status: "in_progress", mappingProgress: 75, mappingCount: 14 },
  { id: "2", name: "Study XYZ-456 Demographics", description: "Demographics domain mapping only", sourceFile: "xyz456_demographics.xlsx", targetVersion: "SDTM 3.4", createdAt: "2024-01-20", updatedAt: "2024-02-08", status: "validated", mappingProgress: 100, mappingCount: 9 },
  { id: "3", name: "Historical Data Migration", description: "Legacy data to SDTM format", sourceFile: "legacy_combined.csv", targetVersion: "SDTM 3.3", createdAt: "2023-12-01", updatedAt: "2024-01-15", status: "complete", mappingProgress: 100, mappingCount: 42 },
];

// ============================================================================
// Helper Functions
// ============================================================================

const getStatusColor = (status: string) => {
  switch (status) {
    case "valid":
    case "complete":
    case "validated":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
    case "warning":
    case "in_progress":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
    case "error":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
    case "draft":
    case "pending":
      return "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200";
    default:
      return "bg-gray-100 text-gray-800";
  }
};

const getStatusIcon = (status: string) => {
  switch (status) {
    case "valid":
    case "complete":
    case "validated":
      return <CheckCircle2 className="h-4 w-4 text-green-600" />;
    case "warning":
      return <AlertTriangle className="h-4 w-4 text-amber-600" />;
    case "error":
      return <AlertCircle className="h-4 w-4 text-red-600" />;
    default:
      return <Info className="h-4 w-4 text-gray-500" />;
  }
};

const getCoreColor = (core: string) => {
  switch (core) {
    case "Req":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
    case "Exp":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
    case "Perm":
      return "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200";
    default:
      return "bg-gray-100 text-gray-800";
  }
};

// ============================================================================
// Main Component
// ============================================================================

export default function SDTMMappingPage() {
  const [activeTab, setActiveTab] = useState("mappings");
  const [selectedDomain, setSelectedDomain] = useState<string>("DM");
  const [searchQuery, setSearchQuery] = useState("");
  const [mappings, setMappings] = useState<ColumnMapping[]>(mockMappings);
  const [selectedMapping, setSelectedMapping] = useState<ColumnMapping | null>(null);
  const [isAddingMapping, setIsAddingMapping] = useState(false);
  const [projects] = useState<MappingProject[]>(mockProjects);
  const [selectedProject, setSelectedProject] = useState<MappingProject>(mockProjects[0]);

  // New mapping form state
  const [newMapping, setNewMapping] = useState<Partial<ColumnMapping>>({
    sourceColumn: "",
    targetDomain: "DM",
    targetVariable: "",
    transformationType: "direct",
  });

  // Calculate statistics
  const stats = useMemo(() => {
    const total = mappings.length;
    const valid = mappings.filter(m => m.validationStatus === "valid").length;
    const warnings = mappings.filter(m => m.validationStatus === "warning").length;
    const errors = mappings.filter(m => m.validationStatus === "error").length;
    const pending = mappings.filter(m => m.validationStatus === "pending").length;
    const byDomain = mockSDTMDomains.reduce((acc, d) => {
      acc[d.code] = mappings.filter(m => m.targetDomain === d.code).length;
      return acc;
    }, {} as Record<string, number>);
    return { total, valid, warnings, errors, pending, byDomain };
  }, [mappings]);

  // Filter mappings
  const filteredMappings = useMemo(() => {
    return mappings.filter(m => {
      const matchesSearch = searchQuery === "" ||
        m.sourceColumn.toLowerCase().includes(searchQuery.toLowerCase()) ||
        m.targetVariable.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesDomain = selectedDomain === "all" || m.targetDomain === selectedDomain;
      return matchesSearch && matchesDomain;
    });
  }, [mappings, searchQuery, selectedDomain]);

  // Get variables for selected domain
  const domainVariables = useMemo(() => {
    const domain = mockSDTMDomains.find(d => d.code === newMapping.targetDomain);
    return domain?.variables || [];
  }, [newMapping.targetDomain]);

  const handleAddMapping = () => {
    if (!newMapping.sourceColumn || !newMapping.targetVariable) return;

    const mapping: ColumnMapping = {
      id: String(mappings.length + 1),
      sourceColumn: newMapping.sourceColumn,
      targetDomain: newMapping.targetDomain || "DM",
      targetVariable: newMapping.targetVariable,
      transformationType: newMapping.transformationType || "direct",
      transformation: newMapping.transformation,
      validationStatus: "pending",
    };

    setMappings([...mappings, mapping]);
    setNewMapping({ sourceColumn: "", targetDomain: "DM", targetVariable: "", transformationType: "direct" });
    setIsAddingMapping(false);
  };

  const handleDeleteMapping = (id: string) => {
    setMappings(mappings.filter(m => m.id !== id));
  };

  const handleValidateAll = () => {
    // Simulate validation - in real app would call API
    setMappings(mappings.map(m => ({
      ...m,
      validationStatus: Math.random() > 0.2 ? "valid" : (Math.random() > 0.5 ? "warning" : "error"),
    })));
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">SDTM Mapping</h1>
          <p className="text-muted-foreground">
            Map source data to CDISC SDTM domains and variables
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
          <Button variant="outline" size="sm" onClick={handleValidateAll}>
            <Play className="mr-2 h-4 w-4" />
            Validate All
          </Button>
          <Link href="/cdisc">
            <Button variant="outline" size="sm">
              <Database className="mr-2 h-4 w-4" />
              Codelists
            </Button>
          </Link>
        </div>
      </div>

      {/* Project Selector */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Current Project</CardTitle>
            <Button variant="outline" size="sm">
              <Plus className="mr-2 h-4 w-4" />
              New Project
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <Select value={selectedProject.id} onValueChange={(v) => setSelectedProject(projects.find(p => p.id === v) || projects[0])}>
              <SelectTrigger className="w-[300px]">
                <SelectValue placeholder="Select project" />
              </SelectTrigger>
              <SelectContent>
                {projects.map(project => (
                  <SelectItem key={project.id} value={project.id}>
                    {project.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="flex-1">
              <div className="text-sm text-muted-foreground">{selectedProject.description}</div>
              <div className="flex items-center gap-4 mt-1">
                <span className="text-xs text-muted-foreground">Source: {selectedProject.sourceFile}</span>
                <span className="text-xs text-muted-foreground">Target: {selectedProject.targetVersion}</span>
                <Badge className={getStatusColor(selectedProject.status)}>{selectedProject.status}</Badge>
              </div>
            </div>
            <div className="w-32">
              <div className="text-sm font-medium text-right">{selectedProject.mappingProgress}%</div>
              <Progress value={selectedProject.mappingProgress} className="h-2 mt-1" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Statistics */}
      <div className="grid gap-4 md:grid-cols-5">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Mappings</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              Valid
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{stats.valid}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              Warnings
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600">{stats.warnings}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-red-600" />
              Errors
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{stats.errors}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Pending</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-gray-500">{stats.pending}</div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="mappings">Mappings</TabsTrigger>
          <TabsTrigger value="source">Source Data</TabsTrigger>
          <TabsTrigger value="domains">SDTM Domains</TabsTrigger>
          <TabsTrigger value="preview">Preview</TabsTrigger>
        </TabsList>

        <TabsContent value="mappings" className="space-y-4">
          {/* Filters */}
          <div className="flex items-center gap-4">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search mappings..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8"
              />
            </div>
            <Select value={selectedDomain} onValueChange={setSelectedDomain}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Select domain" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Domains</SelectItem>
                {mockSDTMDomains.map(domain => (
                  <SelectItem key={domain.code} value={domain.code}>
                    {domain.code} - {domain.name} ({stats.byDomain[domain.code] || 0})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Dialog open={isAddingMapping} onOpenChange={setIsAddingMapping}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="mr-2 h-4 w-4" />
                  Add Mapping
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl">
                <DialogHeader>
                  <DialogTitle>Add Column Mapping</DialogTitle>
                  <DialogDescription>
                    Map a source column to an SDTM variable
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Source Column</Label>
                      <Select
                        value={newMapping.sourceColumn}
                        onValueChange={(v) => setNewMapping({ ...newMapping, sourceColumn: v })}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select source column" />
                        </SelectTrigger>
                        <SelectContent>
                          {mockSourceColumns.map(col => (
                            <SelectItem key={col.id} value={col.name}>
                              {col.name} ({col.dataType})
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>Target Domain</Label>
                      <Select
                        value={newMapping.targetDomain}
                        onValueChange={(v) => setNewMapping({ ...newMapping, targetDomain: v, targetVariable: "" })}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select domain" />
                        </SelectTrigger>
                        <SelectContent>
                          {mockSDTMDomains.map(domain => (
                            <SelectItem key={domain.code} value={domain.code}>
                              {domain.code} - {domain.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Target Variable</Label>
                      <Select
                        value={newMapping.targetVariable}
                        onValueChange={(v) => setNewMapping({ ...newMapping, targetVariable: v })}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select variable" />
                        </SelectTrigger>
                        <SelectContent>
                          {domainVariables.map(v => (
                            <SelectItem key={v.name} value={v.name}>
                              {v.name} - {v.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>Transformation Type</Label>
                      <Select
                        value={newMapping.transformationType}
                        onValueChange={(v) => setNewMapping({ ...newMapping, transformationType: v as ColumnMapping["transformationType"] })}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select type" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="direct">Direct Copy</SelectItem>
                          <SelectItem value="lookup">Codelist Lookup</SelectItem>
                          <SelectItem value="derived">Derived</SelectItem>
                          <SelectItem value="constant">Constant Value</SelectItem>
                          <SelectItem value="expression">Expression</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  {(newMapping.transformationType === "expression" || newMapping.transformationType === "derived") && (
                    <div className="space-y-2">
                      <Label>Transformation Expression</Label>
                      <Textarea
                        placeholder="e.g., concat(STUDYID, '-', subject_id)"
                        value={newMapping.transformation || ""}
                        onChange={(e) => setNewMapping({ ...newMapping, transformation: e.target.value })}
                      />
                    </div>
                  )}
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setIsAddingMapping(false)}>
                    Cancel
                  </Button>
                  <Button onClick={handleAddMapping}>Add Mapping</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>

          {/* Mappings Table */}
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Source Column</TableHead>
                    <TableHead className="text-center">
                      <ArrowRight className="h-4 w-4 mx-auto" />
                    </TableHead>
                    <TableHead>Target Variable</TableHead>
                    <TableHead>Transformation</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="w-[100px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredMappings.map((mapping) => (
                    <TableRow key={mapping.id}>
                      <TableCell>
                        <div className="font-mono text-sm">{mapping.sourceColumn}</div>
                      </TableCell>
                      <TableCell className="text-center">
                        <Link2 className="h-4 w-4 mx-auto text-muted-foreground" />
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">{mapping.targetDomain}</Badge>
                          <span className="font-mono text-sm">{mapping.targetVariable}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="text-sm">
                          <Badge variant="secondary" className="text-xs">{mapping.transformationType}</Badge>
                          {mapping.transformation && (
                            <div className="text-xs text-muted-foreground mt-1 font-mono">
                              {mapping.transformation}
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {getStatusIcon(mapping.validationStatus)}
                          <Badge className={getStatusColor(mapping.validationStatus)}>
                            {mapping.validationStatus}
                          </Badge>
                        </div>
                        {mapping.validationMessage && (
                          <div className="text-xs text-muted-foreground mt-1">
                            {mapping.validationMessage}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Button variant="ghost" size="sm">
                            <Edit2 className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteMapping(mapping.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="source" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Source Data Columns</CardTitle>
              <CardDescription>
                Available columns from {selectedProject.sourceFile}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Column Name</TableHead>
                    <TableHead>Data Type</TableHead>
                    <TableHead>Sample Values</TableHead>
                    <TableHead>Null %</TableHead>
                    <TableHead>Unique</TableHead>
                    <TableHead>Mapped</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {mockSourceColumns.map((col) => {
                    const isMapped = mappings.some(m => m.sourceColumn === col.name);
                    return (
                      <TableRow key={col.id}>
                        <TableCell className="font-mono text-sm">{col.name}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{col.dataType}</Badge>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {col.sampleValues.slice(0, 3).join(", ")}
                        </TableCell>
                        <TableCell>
                          <span className={col.nullPercentage > 10 ? "text-amber-600" : ""}>
                            {col.nullPercentage}%
                          </span>
                        </TableCell>
                        <TableCell>{col.uniqueCount.toLocaleString()}</TableCell>
                        <TableCell>
                          {isMapped ? (
                            <CheckCircle2 className="h-4 w-4 text-green-600" />
                          ) : (
                            <div className="h-4 w-4 rounded-full border-2 border-gray-300" />
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="domains" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            {mockSDTMDomains.map((domain) => (
              <Card key={domain.code}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        <Badge>{domain.code}</Badge>
                        {domain.name}
                      </CardTitle>
                      <CardDescription>{domain.description}</CardDescription>
                    </div>
                    <Badge variant="outline">{domain.class}</Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <ScrollArea className="h-[200px]">
                    <div className="space-y-2">
                      {domain.variables.map((v) => {
                        const isMapped = mappings.some(m => m.targetDomain === domain.code && m.targetVariable === v.name);
                        return (
                          <div
                            key={v.name}
                            className={`flex items-center justify-between p-2 rounded-lg border ${
                              isMapped ? "bg-green-50 border-green-200 dark:bg-green-950 dark:border-green-800" : ""
                            }`}
                          >
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-sm font-medium">{v.name}</span>
                                <Badge className={`text-xs ${getCoreColor(v.core)}`}>{v.core}</Badge>
                                {v.codelistCode && (
                                  <Link href={`/cdisc/codelists/${v.codelistCode}`}>
                                    <Badge variant="outline" className="text-xs cursor-pointer hover:bg-muted">
                                      {v.codelistCode}
                                    </Badge>
                                  </Link>
                                )}
                              </div>
                              <div className="text-xs text-muted-foreground">{v.label}</div>
                            </div>
                            {isMapped && <CheckCircle2 className="h-4 w-4 text-green-600" />}
                          </div>
                        );
                      })}
                    </div>
                  </ScrollArea>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="preview" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Mapping Preview</CardTitle>
              <CardDescription>
                Preview of the transformed SDTM output
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {mockSDTMDomains.filter(d => stats.byDomain[d.code] > 0).map((domain) => {
                  const domainMappings = mappings.filter(m => m.targetDomain === domain.code);
                  return (
                    <div key={domain.code} className="space-y-2">
                      <h4 className="font-medium flex items-center gap-2">
                        <Badge>{domain.code}</Badge>
                        {domain.name}
                        <span className="text-sm text-muted-foreground">
                          ({domainMappings.length} mappings)
                        </span>
                      </h4>
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm border">
                          <thead className="bg-muted">
                            <tr>
                              {domainMappings.map(m => (
                                <th key={m.id} className="p-2 border text-left font-mono">
                                  {m.targetVariable}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {[1, 2, 3].map((row) => (
                              <tr key={row}>
                                {domainMappings.map(m => (
                                  <td key={m.id} className="p-2 border text-muted-foreground">
                                    {m.transformationType === "constant"
                                      ? m.transformation
                                      : m.transformationType === "expression"
                                      ? `<derived>`
                                      : `<${m.sourceColumn}>`}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
