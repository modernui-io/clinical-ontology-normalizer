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
import { Label } from "@/components/ui/label";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ArrowLeft,
  ArrowUp,
  ArrowDown,
  Plus,
  Trash2,
  Save,
  Send,
  AlertTriangle,
  CheckCircle,
  XCircle,
  FileText,
  Clock,
  Calculator,
  ClipboardList,
  History,
  Sparkles,
  User,
  Calendar,
  Stethoscope,
} from "lucide-react";

// Types
interface CodeEntry {
  id: string;
  code: string;
  codeType: "ICD10" | "CPT";
  description: string;
  sequence: number;
  isPrimary: boolean;
  confidence: number;
  status: "pending" | "accepted" | "rejected" | "verified";
  source: "manual" | "ai_suggested" | "imported";
  evidenceText: string | null;
  modifier: string | null;
  notes: string | null;
}

interface Encounter {
  id: string;
  patientId: string;
  patientName: string;
  date: string;
  type: string;
  provider: string;
  status: "draft" | "submitted" | "finalized";
}

interface AuditEntry {
  id: string;
  action: string;
  timestamp: string;
  user: string;
  details: string;
}

interface Worksheet {
  encounterId: string;
  patientId: string;
  encounterDate: string;
  status: "draft" | "submitted" | "finalized";
  diagnosisCodes: CodeEntry[];
  procedureCodes: CodeEntry[];
  emCode: CodeEntry | null;
  validationWarnings: string[];
  auditTrail: AuditEntry[];
  createdAt: string;
  updatedAt: string;
  submittedAt: string | null;
  submittedBy: string | null;
}

// Mock encounters
const mockEncounters: Encounter[] = [
  {
    id: "E001",
    patientId: "P001",
    patientName: "John Smith",
    date: "2026-01-19",
    type: "Office Visit",
    provider: "Dr. Johnson",
    status: "draft",
  },
  {
    id: "E002",
    patientId: "P002",
    patientName: "Jane Doe",
    date: "2026-01-18",
    type: "Office Visit",
    provider: "Dr. Johnson",
    status: "submitted",
  },
  {
    id: "E003",
    patientId: "P003",
    patientName: "Mary Johnson",
    date: "2026-01-17",
    type: "Procedure",
    provider: "Dr. Williams",
    status: "finalized",
  },
];

// Mock worksheet data
const mockWorksheet: Worksheet = {
  encounterId: "E001",
  patientId: "P001",
  encounterDate: "2026-01-19",
  status: "draft",
  diagnosisCodes: [
    {
      id: "dx1",
      code: "E11.22",
      codeType: "ICD10",
      description: "Type 2 diabetes mellitus with diabetic chronic kidney disease",
      sequence: 1,
      isPrimary: true,
      confidence: 0.92,
      status: "verified",
      source: "ai_suggested",
      evidenceText: "diabetic nephropathy with CKD stage 3",
      modifier: null,
      notes: "HCC37 - Diabetes with Chronic Complications",
    },
    {
      id: "dx2",
      code: "I50.22",
      codeType: "ICD10",
      description: "Chronic systolic (congestive) heart failure",
      sequence: 2,
      isPrimary: false,
      confidence: 0.95,
      status: "verified",
      source: "ai_suggested",
      evidenceText: "chronic systolic heart failure with EF 35%",
      modifier: null,
      notes: "HCC85 - Heart Failure",
    },
    {
      id: "dx3",
      code: "N18.3",
      codeType: "ICD10",
      description: "Chronic kidney disease, stage 3 (moderate)",
      sequence: 3,
      isPrimary: false,
      confidence: 0.90,
      status: "pending",
      source: "ai_suggested",
      evidenceText: "eGFR 42 mL/min",
      modifier: null,
      notes: null,
    },
  ],
  procedureCodes: [
    {
      id: "px1",
      code: "36415",
      codeType: "CPT",
      description: "Collection of venous blood by venipuncture",
      sequence: 1,
      isPrimary: false,
      confidence: 0.85,
      status: "pending",
      source: "ai_suggested",
      evidenceText: "labs ordered",
      modifier: null,
      notes: null,
    },
  ],
  emCode: {
    id: "em1",
    code: "99214",
    codeType: "CPT",
    description: "Office visit, established patient, moderate MDM or 30-39 min",
    sequence: 0,
    isPrimary: false,
    confidence: 0.88,
    status: "pending",
    source: "ai_suggested",
    evidenceText: "Total time: 35 minutes",
    modifier: null,
    notes: "Time-based billing supported",
  },
  validationWarnings: [
    "INFO: N18.3 may be redundant with E11.22 - verify documentation supports separate condition",
  ],
  auditTrail: [
    {
      id: "a1",
      action: "created",
      timestamp: "2026-01-19T10:00:00Z",
      user: "System",
      details: "Worksheet created from AI suggestions",
    },
    {
      id: "a2",
      action: "code_verified",
      timestamp: "2026-01-19T10:15:00Z",
      user: "coder@example.com",
      details: "Verified E11.22 as primary diagnosis",
    },
    {
      id: "a3",
      action: "code_verified",
      timestamp: "2026-01-19T10:16:00Z",
      user: "coder@example.com",
      details: "Verified I50.22",
    },
  ],
  createdAt: "2026-01-19T10:00:00Z",
  updatedAt: "2026-01-19T10:16:00Z",
  submittedAt: null,
  submittedBy: null,
};

// E/M Code Options
const EM_CODES = [
  { code: "99211", description: "Office visit, established, minimal problem", time: "5-10 min" },
  { code: "99212", description: "Office visit, established, straightforward MDM", time: "10-19 min" },
  { code: "99213", description: "Office visit, established, low MDM", time: "20-29 min" },
  { code: "99214", description: "Office visit, established, moderate MDM", time: "30-39 min" },
  { code: "99215", description: "Office visit, established, high MDM", time: "40-54 min" },
  { code: "99202", description: "Office visit, new patient, straightforward MDM", time: "15-29 min" },
  { code: "99203", description: "Office visit, new patient, low MDM", time: "30-44 min" },
  { code: "99204", description: "Office visit, new patient, moderate MDM", time: "45-59 min" },
  { code: "99205", description: "Office visit, new patient, high MDM", time: "60-74 min" },
];

// Helper functions
const getStatusBadge = (status: string) => {
  switch (status) {
    case "verified":
      return (
        <Badge variant="outline" className="border-green-500 text-green-600">
          <CheckCircle className="mr-1 h-3 w-3" />
          Verified
        </Badge>
      );
    case "pending":
      return (
        <Badge variant="outline" className="border-yellow-500 text-yellow-600">
          <Clock className="mr-1 h-3 w-3" />
          Pending
        </Badge>
      );
    case "rejected":
      return (
        <Badge variant="outline" className="border-red-500 text-red-600">
          <XCircle className="mr-1 h-3 w-3" />
          Rejected
        </Badge>
      );
    case "accepted":
      return (
        <Badge variant="outline" className="border-blue-500 text-blue-600">
          <CheckCircle className="mr-1 h-3 w-3" />
          Accepted
        </Badge>
      );
    default:
      return null;
  }
};

const getSourceBadge = (source: string) => {
  switch (source) {
    case "ai_suggested":
      return (
        <Badge variant="secondary" className="text-xs">
          <Sparkles className="mr-1 h-2.5 w-2.5" />
          AI
        </Badge>
      );
    case "manual":
      return (
        <Badge variant="outline" className="text-xs">
          Manual
        </Badge>
      );
    case "imported":
      return (
        <Badge variant="outline" className="text-xs">
          Imported
        </Badge>
      );
    default:
      return null;
  }
};

const getWorksheetStatusBadge = (status: string) => {
  switch (status) {
    case "draft":
      return <Badge variant="outline">Draft</Badge>;
    case "submitted":
      return (
        <Badge className="bg-blue-500 hover:bg-blue-600">Submitted</Badge>
      );
    case "finalized":
      return (
        <Badge className="bg-green-500 hover:bg-green-600">Finalized</Badge>
      );
    default:
      return null;
  }
};

export default function CodingWorksheetPage() {
  const [selectedEncounter, setSelectedEncounter] = useState<Encounter | null>(mockEncounters[0]);
  const [worksheet, setWorksheet] = useState<Worksheet>(mockWorksheet);
  const [showAddCode, setShowAddCode] = useState(false);
  const [newCode, setNewCode] = useState({ code: "", type: "ICD10" as "ICD10" | "CPT" });
  const [activeTab, setActiveTab] = useState("codes");
  const [emTimeMinutes, setEmTimeMinutes] = useState<string>("35");

  // Move diagnosis code up/down
  const moveCode = (id: string, direction: "up" | "down") => {
    const codes = [...worksheet.diagnosisCodes];
    const index = codes.findIndex((c) => c.id === id);
    if (
      (direction === "up" && index === 0) ||
      (direction === "down" && index === codes.length - 1)
    ) {
      return;
    }

    const newIndex = direction === "up" ? index - 1 : index + 1;
    [codes[index], codes[newIndex]] = [codes[newIndex], codes[index]];

    // Update sequences
    codes.forEach((c, i) => {
      c.sequence = i + 1;
    });

    setWorksheet({ ...worksheet, diagnosisCodes: codes });
  };

  // Set primary diagnosis
  const setPrimaryDiagnosis = (id: string) => {
    const codes = worksheet.diagnosisCodes.map((c) => ({
      ...c,
      isPrimary: c.id === id,
    }));
    setWorksheet({ ...worksheet, diagnosisCodes: codes });
  };

  // Verify code
  const verifyCode = (id: string, type: "diagnosis" | "procedure" | "em") => {
    if (type === "diagnosis") {
      const codes = worksheet.diagnosisCodes.map((c) =>
        c.id === id ? { ...c, status: "verified" as const } : c
      );
      setWorksheet({ ...worksheet, diagnosisCodes: codes });
    } else if (type === "procedure") {
      const codes = worksheet.procedureCodes.map((c) =>
        c.id === id ? { ...c, status: "verified" as const } : c
      );
      setWorksheet({ ...worksheet, procedureCodes: codes });
    } else if (type === "em" && worksheet.emCode) {
      setWorksheet({
        ...worksheet,
        emCode: { ...worksheet.emCode, status: "verified" as const },
      });
    }
  };

  // Remove code
  const removeCode = (id: string, type: "diagnosis" | "procedure") => {
    if (type === "diagnosis") {
      const codes = worksheet.diagnosisCodes.filter((c) => c.id !== id);
      codes.forEach((c, i) => {
        c.sequence = i + 1;
      });
      setWorksheet({ ...worksheet, diagnosisCodes: codes });
    } else {
      const codes = worksheet.procedureCodes.filter((c) => c.id !== id);
      codes.forEach((c, i) => {
        c.sequence = i + 1;
      });
      setWorksheet({ ...worksheet, procedureCodes: codes });
    }
  };

  // Add new code
  const addCode = () => {
    if (!newCode.code) return;

    const entry: CodeEntry = {
      id: `new-${Date.now()}`,
      code: newCode.code.toUpperCase(),
      codeType: newCode.type,
      description: "Manual entry - verify description",
      sequence: newCode.type === "ICD10"
        ? worksheet.diagnosisCodes.length + 1
        : worksheet.procedureCodes.length + 1,
      isPrimary: false,
      confidence: 1.0,
      status: "pending",
      source: "manual",
      evidenceText: null,
      modifier: null,
      notes: null,
    };

    if (newCode.type === "ICD10") {
      setWorksheet({
        ...worksheet,
        diagnosisCodes: [...worksheet.diagnosisCodes, entry],
      });
    } else {
      setWorksheet({
        ...worksheet,
        procedureCodes: [...worksheet.procedureCodes, entry],
      });
    }

    setNewCode({ code: "", type: "ICD10" });
    setShowAddCode(false);
  };

  // Update E/M code
  const updateEMCode = (code: string) => {
    const emInfo = EM_CODES.find((e) => e.code === code);
    if (!emInfo) return;

    setWorksheet({
      ...worksheet,
      emCode: {
        id: "em1",
        code: code,
        codeType: "CPT",
        description: emInfo.description,
        sequence: 0,
        isPrimary: false,
        confidence: 0.9,
        status: "pending",
        source: "manual",
        evidenceText: `Time: ${emTimeMinutes} minutes`,
        modifier: null,
        notes: null,
      },
    });
  };

  // Calculate E/M from time
  const calculateEMFromTime = () => {
    const time = parseInt(emTimeMinutes);
    if (isNaN(time)) return;

    let code = "99213";
    if (time >= 40) code = "99215";
    else if (time >= 30) code = "99214";
    else if (time >= 20) code = "99213";
    else if (time >= 10) code = "99212";
    else code = "99211";

    updateEMCode(code);
  };

  // Submit worksheet
  const submitWorksheet = () => {
    // Validate
    const warnings: string[] = [];
    if (worksheet.diagnosisCodes.length === 0) {
      warnings.push("ERROR: At least one diagnosis code is required");
    }
    if (!worksheet.diagnosisCodes.some((c) => c.isPrimary)) {
      warnings.push("WARNING: No primary diagnosis designated");
    }
    if (!worksheet.emCode) {
      warnings.push("WARNING: No E/M code assigned");
    }

    if (warnings.some((w) => w.startsWith("ERROR"))) {
      setWorksheet({ ...worksheet, validationWarnings: warnings });
      return;
    }

    setWorksheet({
      ...worksheet,
      status: "submitted",
      submittedAt: new Date().toISOString(),
      submittedBy: "coder@example.com",
      validationWarnings: warnings,
      auditTrail: [
        ...worksheet.auditTrail,
        {
          id: `a${worksheet.auditTrail.length + 1}`,
          action: "submitted",
          timestamp: new Date().toISOString(),
          user: "coder@example.com",
          details: "Worksheet submitted for billing",
        },
      ],
    });
  };

  // Stats
  const verifiedDxCount = worksheet.diagnosisCodes.filter(
    (c) => c.status === "verified"
  ).length;
  const totalDxCount = worksheet.diagnosisCodes.length;
  const verifiedPxCount = worksheet.procedureCodes.filter(
    (c) => c.status === "verified"
  ).length;
  const totalPxCount = worksheet.procedureCodes.length;

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Link href="/billing">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Coding Worksheet
            </h1>
            <p className="text-muted-foreground">
              Review and submit diagnosis and procedure codes
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline">
            <Save className="mr-2 h-4 w-4" />
            Save Draft
          </Button>
          <Button
            onClick={submitWorksheet}
            disabled={worksheet.status !== "draft"}
          >
            <Send className="mr-2 h-4 w-4" />
            Submit for Billing
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-4">
        {/* Encounter Selector */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-sm">Select Encounter</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {mockEncounters.map((encounter) => (
                <div
                  key={encounter.id}
                  onClick={() => setSelectedEncounter(encounter)}
                  className={`rounded-lg border p-3 cursor-pointer transition-all ${
                    selectedEncounter?.id === encounter.id
                      ? "border-blue-500 bg-blue-50 dark:bg-blue-950/30"
                      : "hover:border-gray-400"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono text-sm">{encounter.id}</span>
                    {getWorksheetStatusBadge(encounter.status)}
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <User className="h-3 w-3" />
                    {encounter.patientName}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground mt-1">
                    <Calendar className="h-3 w-3" />
                    {encounter.date}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {encounter.type} - {encounter.provider}
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Main Worksheet */}
        <div className="lg:col-span-3 space-y-6">
          {/* Patient/Encounter Info */}
          <Card>
            <CardContent className="pt-6">
              <div className="flex flex-wrap gap-6 justify-between">
                <div>
                  <Label className="text-xs text-muted-foreground">Patient</Label>
                  <p className="font-medium">
                    {selectedEncounter?.patientName} ({selectedEncounter?.patientId})
                  </p>
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">Encounter</Label>
                  <p className="font-medium">{selectedEncounter?.id}</p>
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">Date</Label>
                  <p className="font-medium">{worksheet.encounterDate}</p>
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">Status</Label>
                  <div className="mt-1">{getWorksheetStatusBadge(worksheet.status)}</div>
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">Progress</Label>
                  <p className="font-medium">
                    {verifiedDxCount}/{totalDxCount} DX, {verifiedPxCount}/{totalPxCount} PX verified
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Validation Warnings */}
          {worksheet.validationWarnings.length > 0 && (
            <Card className="border-yellow-300 dark:border-yellow-700">
              <CardContent className="pt-4">
                <div className="space-y-2">
                  {worksheet.validationWarnings.map((warning, idx) => (
                    <div
                      key={idx}
                      className={`flex items-start gap-2 text-sm ${
                        warning.startsWith("ERROR")
                          ? "text-red-600"
                          : warning.startsWith("WARNING")
                          ? "text-yellow-600"
                          : "text-blue-600"
                      }`}
                    >
                      <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                      {warning}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList>
              <TabsTrigger value="codes">
                <ClipboardList className="mr-2 h-4 w-4" />
                Codes
              </TabsTrigger>
              <TabsTrigger value="em">
                <Calculator className="mr-2 h-4 w-4" />
                E/M Level
              </TabsTrigger>
              <TabsTrigger value="audit">
                <History className="mr-2 h-4 w-4" />
                Audit Trail
              </TabsTrigger>
            </TabsList>

            <TabsContent value="codes" className="space-y-6">
              {/* Diagnosis Codes */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      <Stethoscope className="h-5 w-5" />
                      Diagnosis Codes ({totalDxCount})
                    </CardTitle>
                    <Button size="sm" onClick={() => setShowAddCode(true)}>
                      <Plus className="mr-1 h-4 w-4" />
                      Add Code
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {showAddCode && (
                    <div className="mb-4 p-4 rounded-lg border bg-muted/50">
                      <div className="flex gap-4 items-end">
                        <div className="flex-1">
                          <Label>Code</Label>
                          <Input
                            placeholder="Enter code (e.g., E11.22)"
                            value={newCode.code}
                            onChange={(e) =>
                              setNewCode({ ...newCode, code: e.target.value })
                            }
                          />
                        </div>
                        <div>
                          <Label>Type</Label>
                          <Select
                            value={newCode.type}
                            onValueChange={(v) =>
                              setNewCode({ ...newCode, type: v as "ICD10" | "CPT" })
                            }
                          >
                            <SelectTrigger className="w-32">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="ICD10">ICD-10</SelectItem>
                              <SelectItem value="CPT">CPT</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <Button onClick={addCode}>Add</Button>
                        <Button
                          variant="outline"
                          onClick={() => setShowAddCode(false)}
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  )}

                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-12">Seq</TableHead>
                        <TableHead className="w-24">Code</TableHead>
                        <TableHead>Description</TableHead>
                        <TableHead className="w-24">Source</TableHead>
                        <TableHead className="w-28">Status</TableHead>
                        <TableHead className="w-32">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {worksheet.diagnosisCodes.map((dx) => (
                        <TableRow key={dx.id}>
                          <TableCell>
                            <div className="flex items-center gap-1">
                              <span className="font-mono">{dx.sequence}</span>
                              {dx.isPrimary && (
                                <Badge className="bg-blue-500 text-xs px-1">
                                  1st
                                </Badge>
                              )}
                            </div>
                          </TableCell>
                          <TableCell>
                            <code className="font-mono font-bold">{dx.code}</code>
                          </TableCell>
                          <TableCell>
                            <div>
                              <p className="text-sm">{dx.description}</p>
                              {dx.evidenceText && (
                                <p className="text-xs text-muted-foreground mt-1">
                                  Evidence: {dx.evidenceText}
                                </p>
                              )}
                              {dx.notes && (
                                <p className="text-xs text-green-600 mt-1">
                                  {dx.notes}
                                </p>
                              )}
                            </div>
                          </TableCell>
                          <TableCell>{getSourceBadge(dx.source)}</TableCell>
                          <TableCell>{getStatusBadge(dx.status)}</TableCell>
                          <TableCell>
                            <div className="flex gap-1">
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7"
                                onClick={() => moveCode(dx.id, "up")}
                                disabled={dx.sequence === 1}
                              >
                                <ArrowUp className="h-3 w-3" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7"
                                onClick={() => moveCode(dx.id, "down")}
                                disabled={dx.sequence === worksheet.diagnosisCodes.length}
                              >
                                <ArrowDown className="h-3 w-3" />
                              </Button>
                              {dx.status !== "verified" && (
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-7 w-7 text-green-600"
                                  onClick={() => verifyCode(dx.id, "diagnosis")}
                                >
                                  <CheckCircle className="h-3 w-3" />
                                </Button>
                              )}
                              {!dx.isPrimary && (
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-7 w-7 text-blue-600"
                                  onClick={() => setPrimaryDiagnosis(dx.id)}
                                  title="Set as Primary"
                                >
                                  <span className="text-xs font-bold">1st</span>
                                </Button>
                              )}
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 text-red-600"
                                onClick={() => removeCode(dx.id, "diagnosis")}
                              >
                                <Trash2 className="h-3 w-3" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>

              {/* Procedure Codes */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="h-5 w-5" />
                    Procedure Codes ({totalPxCount})
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-12">Seq</TableHead>
                        <TableHead className="w-24">Code</TableHead>
                        <TableHead>Description</TableHead>
                        <TableHead className="w-24">Modifier</TableHead>
                        <TableHead className="w-24">Source</TableHead>
                        <TableHead className="w-28">Status</TableHead>
                        <TableHead className="w-24">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {worksheet.procedureCodes.map((px) => (
                        <TableRow key={px.id}>
                          <TableCell className="font-mono">{px.sequence}</TableCell>
                          <TableCell>
                            <code className="font-mono font-bold">{px.code}</code>
                          </TableCell>
                          <TableCell>
                            <p className="text-sm">{px.description}</p>
                          </TableCell>
                          <TableCell>
                            <Input
                              placeholder="-"
                              className="w-16 h-8 text-center font-mono"
                              value={px.modifier || ""}
                              onChange={(e) => {
                                const codes = worksheet.procedureCodes.map((c) =>
                                  c.id === px.id ? { ...c, modifier: e.target.value } : c
                                );
                                setWorksheet({ ...worksheet, procedureCodes: codes });
                              }}
                            />
                          </TableCell>
                          <TableCell>{getSourceBadge(px.source)}</TableCell>
                          <TableCell>{getStatusBadge(px.status)}</TableCell>
                          <TableCell>
                            <div className="flex gap-1">
                              {px.status !== "verified" && (
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-7 w-7 text-green-600"
                                  onClick={() => verifyCode(px.id, "procedure")}
                                >
                                  <CheckCircle className="h-3 w-3" />
                                </Button>
                              )}
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 text-red-600"
                                onClick={() => removeCode(px.id, "procedure")}
                              >
                                <Trash2 className="h-3 w-3" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                      {totalPxCount === 0 && (
                        <TableRow>
                          <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                            No procedure codes added
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="em">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Calculator className="h-5 w-5" />
                    E/M Level Selection
                  </CardTitle>
                  <CardDescription>
                    Select the appropriate E/M code based on time or MDM complexity
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Current E/M Code */}
                  {worksheet.emCode && (
                    <div className="rounded-lg border p-4 bg-blue-50 dark:bg-blue-950/30">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <code className="text-xl font-mono font-bold">
                              {worksheet.emCode.code}
                            </code>
                            {getStatusBadge(worksheet.emCode.status)}
                            {getSourceBadge(worksheet.emCode.source)}
                          </div>
                          <p className="mt-1">{worksheet.emCode.description}</p>
                          {worksheet.emCode.evidenceText && (
                            <p className="text-sm text-muted-foreground mt-1">
                              {worksheet.emCode.evidenceText}
                            </p>
                          )}
                        </div>
                        {worksheet.emCode.status !== "verified" && (
                          <Button
                            onClick={() => verifyCode(worksheet.emCode!.id, "em")}
                          >
                            <CheckCircle className="mr-2 h-4 w-4" />
                            Verify
                          </Button>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Time-based Calculator */}
                  <div className="rounded-lg border p-4">
                    <h4 className="font-semibold mb-4 flex items-center gap-2">
                      <Clock className="h-4 w-4" />
                      Time-Based Calculation
                    </h4>
                    <div className="flex items-end gap-4">
                      <div className="flex-1 max-w-xs">
                        <Label>Total Time (minutes)</Label>
                        <Input
                          type="number"
                          placeholder="Enter total time"
                          value={emTimeMinutes}
                          onChange={(e) => setEmTimeMinutes(e.target.value)}
                        />
                      </div>
                      <Button onClick={calculateEMFromTime}>
                        <Calculator className="mr-2 h-4 w-4" />
                        Calculate E/M
                      </Button>
                    </div>
                    <p className="text-xs text-muted-foreground mt-2">
                      Total time includes face-to-face and non-face-to-face time on encounter date
                    </p>
                  </div>

                  {/* Manual Selection */}
                  <div className="rounded-lg border p-4">
                    <h4 className="font-semibold mb-4">Manual Selection</h4>
                    <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
                      {EM_CODES.map((em) => (
                        <div
                          key={em.code}
                          onClick={() => updateEMCode(em.code)}
                          className={`rounded-lg border p-3 cursor-pointer transition-all ${
                            worksheet.emCode?.code === em.code
                              ? "border-blue-500 bg-blue-50 dark:bg-blue-950/30"
                              : "hover:border-gray-400"
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <code className="font-mono font-bold">{em.code}</code>
                            <Badge variant="outline" className="text-xs">
                              {em.time}
                            </Badge>
                          </div>
                          <p className="text-xs text-muted-foreground mt-1">
                            {em.description}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="audit">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <History className="h-5 w-5" />
                    Audit Trail
                  </CardTitle>
                  <CardDescription>
                    Complete history of changes to this worksheet
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {worksheet.auditTrail.map((entry) => (
                      <div
                        key={entry.id}
                        className="flex gap-4 pb-4 border-b last:border-0"
                      >
                        <div className="w-32 shrink-0">
                          <p className="text-xs text-muted-foreground">
                            {new Date(entry.timestamp).toLocaleString()}
                          </p>
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className="capitalize">
                              {entry.action.replace("_", " ")}
                            </Badge>
                            <span className="text-sm text-muted-foreground">
                              by {entry.user}
                            </span>
                          </div>
                          <p className="text-sm mt-1">{entry.details}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}
