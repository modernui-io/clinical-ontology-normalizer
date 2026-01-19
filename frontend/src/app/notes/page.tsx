"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  FileText,
  Sparkles,
  Clock,
  AlertCircle,
  CheckCircle,
  Loader2,
  History,
  Settings,
  ChevronRight,
  Clipboard,
  Stethoscope,
  FileOutput,
  ClipboardList,
  Hospital,
} from "lucide-react";
import {
  NoteType,
  NoteTemplate,
  GeneratedNoteResponse,
  NoteHistoryEntry,
  PatientDataInput,
  EncounterDataInput,
  getNoteTemplates,
  generateNote,
  getNoteHistory,
  getPatients,
  Patient,
} from "@/lib/api";

// Note type icons and styling
const NOTE_TYPE_CONFIG: Record<
  NoteType,
  { icon: React.ComponentType<{ className?: string }>; color: string; label: string }
> = {
  soap: {
    icon: Clipboard,
    color: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
    label: "SOAP Note",
  },
  hp: {
    icon: Stethoscope,
    color: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
    label: "History & Physical",
  },
  progress: {
    icon: ClipboardList,
    color: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    label: "Progress Note",
  },
  discharge: {
    icon: Hospital,
    color: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
    label: "Discharge Summary",
  },
  procedure: {
    icon: FileOutput,
    color: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
    label: "Procedure Note",
  },
};

const STATUS_STYLES: Record<string, string> = {
  complete: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  draft: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  incomplete: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
  needs_review: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
};

const CONFIDENCE_STYLES: Record<string, string> = {
  high: "text-green-600 dark:text-green-400",
  medium: "text-yellow-600 dark:text-yellow-400",
  low: "text-red-600 dark:text-red-400",
};

export default function NotesPage() {
  const router = useRouter();

  // State
  const [templates, setTemplates] = useState<NoteTemplate[]>([]);
  const [history, setHistory] = useState<NoteHistoryEntry[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generatedNote, setGeneratedNote] = useState<GeneratedNoteResponse | null>(null);

  // Form state
  const [selectedNoteType, setSelectedNoteType] = useState<NoteType>("soap");
  const [selectedTemplate, setSelectedTemplate] = useState<string>("");
  const [selectedPatient, setSelectedPatient] = useState<string>("");

  // Patient data form
  const [patientData, setPatientData] = useState<PatientDataInput>({
    age: undefined,
    sex: undefined,
    chief_complaint: "",
    history_present_illness: "",
    past_medical_history: [],
    medications: [],
    allergies: [],
  });

  // Encounter data form
  const [encounterData, setEncounterData] = useState<EncounterDataInput>({
    encounter_type: "outpatient",
    diagnoses: [],
    plan_items: [],
  });

  // Custom instructions
  const [customInstructions, setCustomInstructions] = useState("");

  // Fetch initial data
  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [templatesRes, historyRes, patientsRes] = await Promise.all([
        getNoteTemplates(),
        getNoteHistory({ limit: 10 }),
        getPatients({ page_size: 50 }),
      ]);
      setTemplates(templatesRes.templates);
      setHistory(historyRes.history);
      setPatients(patientsRes.patients);
      setError(null);
    } catch (err) {
      console.error("Failed to fetch data:", err);
      setError("Failed to load note templates and history.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Filter templates by selected note type
  const filteredTemplates = templates.filter((t) => t.note_type === selectedNoteType);

  // Handle note generation
  const handleGenerate = async () => {
    setIsGenerating(true);
    setError(null);
    setGeneratedNote(null);

    try {
      const result = await generateNote({
        note_type: selectedNoteType,
        patient_data: patientData,
        encounter_data: encounterData,
        template_id: selectedTemplate || undefined,
        custom_instructions: customInstructions || undefined,
        include_codes: true,
      });

      setGeneratedNote(result);

      // Refresh history
      const historyRes = await getNoteHistory({ limit: 10 });
      setHistory(historyRes.history);
    } catch (err) {
      console.error("Note generation failed:", err);
      setError("Failed to generate note. Please check your input and try again.");
    } finally {
      setIsGenerating(false);
    }
  };

  // Parse comma-separated values to array
  const parseArray = (value: string): string[] => {
    return value
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
  };

  // Navigate to editor with generated note
  const openInEditor = () => {
    if (generatedNote) {
      // Store in sessionStorage for the editor to pick up
      sessionStorage.setItem("generatedNote", JSON.stringify(generatedNote));
      router.push("/notes/editor");
    }
  };

  // Copy note to clipboard
  const copyToClipboard = async () => {
    if (generatedNote) {
      await navigator.clipboard.writeText(generatedNote.content);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                href="/dashboard"
                className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
              >
                &larr; Dashboard
              </Link>
              <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                Clinical Note Generation
              </h1>
            </div>
            <div className="flex gap-2">
              <Link href="/notes/editor">
                <Button variant="outline">
                  <Settings className="mr-2 h-4 w-4" />
                  Note Editor
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-8 w-8 animate-spin text-zinc-400" />
          </div>
        ) : (
          <div className="grid gap-6 lg:grid-cols-3">
            {/* Left Panel - Note Configuration */}
            <div className="lg:col-span-2 space-y-6">
              <Tabs defaultValue="generate" className="space-y-4">
                <TabsList>
                  <TabsTrigger value="generate">
                    <Sparkles className="mr-2 h-4 w-4" />
                    Generate Note
                  </TabsTrigger>
                  <TabsTrigger value="history">
                    <History className="mr-2 h-4 w-4" />
                    History
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="generate" className="space-y-6">
                  {/* Note Type Selection */}
                  <Card>
                    <CardHeader>
                      <CardTitle>Note Type</CardTitle>
                      <CardDescription>
                        Select the type of clinical note to generate
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="grid gap-3 sm:grid-cols-5">
                        {(Object.keys(NOTE_TYPE_CONFIG) as NoteType[]).map((type) => {
                          const config = NOTE_TYPE_CONFIG[type];
                          const Icon = config.icon;
                          return (
                            <button
                              key={type}
                              onClick={() => {
                                setSelectedNoteType(type);
                                setSelectedTemplate("");
                              }}
                              className={`flex flex-col items-center gap-2 rounded-lg border p-4 transition-all hover:border-primary/50 ${
                                selectedNoteType === type
                                  ? "border-primary bg-primary/5"
                                  : "border-zinc-200 dark:border-zinc-800"
                              }`}
                            >
                              <div
                                className={`flex h-10 w-10 items-center justify-center rounded-full ${config.color}`}
                              >
                                <Icon className="h-5 w-5" />
                              </div>
                              <span className="text-sm font-medium text-center">
                                {config.label}
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Template Selection */}
                  <Card>
                    <CardHeader>
                      <CardTitle>Template</CardTitle>
                      <CardDescription>
                        Choose a template for the note structure (optional)
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <Select value={selectedTemplate} onValueChange={setSelectedTemplate}>
                        <SelectTrigger>
                          <SelectValue placeholder="Select a template (optional)" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="">Default Template</SelectItem>
                          {filteredTemplates.map((template) => (
                            <SelectItem key={template.template_id} value={template.template_id}>
                              {template.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {selectedTemplate && (
                        <div className="mt-3 text-sm text-zinc-500">
                          {filteredTemplates.find((t) => t.template_id === selectedTemplate)?.description}
                        </div>
                      )}
                    </CardContent>
                  </Card>

                  {/* Patient Context */}
                  <Card>
                    <CardHeader>
                      <CardTitle>Patient Context</CardTitle>
                      <CardDescription>
                        Select a patient or enter patient information manually
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div>
                        <Label>Select Patient (optional)</Label>
                        <Select value={selectedPatient} onValueChange={setSelectedPatient}>
                          <SelectTrigger>
                            <SelectValue placeholder="Select a patient" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="">Manual Entry</SelectItem>
                            {patients.map((patient) => (
                              <SelectItem key={patient.id} value={patient.id}>
                                {patient.external_id} ({patient.fact_count} facts)
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="grid gap-4 sm:grid-cols-2">
                        <div>
                          <Label>Age</Label>
                          <Input
                            type="number"
                            placeholder="e.g., 65"
                            value={patientData.age || ""}
                            onChange={(e) =>
                              setPatientData({
                                ...patientData,
                                age: e.target.value ? parseInt(e.target.value) : undefined,
                              })
                            }
                          />
                        </div>
                        <div>
                          <Label>Sex</Label>
                          <Select
                            value={patientData.sex || ""}
                            onValueChange={(v) =>
                              setPatientData({
                                ...patientData,
                                sex: (v as "M" | "F" | "Other") || undefined,
                              })
                            }
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="Select sex" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="M">Male</SelectItem>
                              <SelectItem value="F">Female</SelectItem>
                              <SelectItem value="Other">Other</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>

                      <div>
                        <Label>Chief Complaint</Label>
                        <Input
                          placeholder="e.g., Chest pain for 2 days"
                          value={patientData.chief_complaint || ""}
                          onChange={(e) =>
                            setPatientData({ ...patientData, chief_complaint: e.target.value })
                          }
                        />
                      </div>

                      <div>
                        <Label>History of Present Illness</Label>
                        <Textarea
                          placeholder="Describe the present illness in detail..."
                          className="min-h-[100px]"
                          value={patientData.history_present_illness || ""}
                          onChange={(e) =>
                            setPatientData({
                              ...patientData,
                              history_present_illness: e.target.value,
                            })
                          }
                        />
                      </div>

                      <div>
                        <Label>Past Medical History (comma-separated)</Label>
                        <Input
                          placeholder="e.g., Hypertension, Type 2 Diabetes, CAD"
                          value={patientData.past_medical_history?.join(", ") || ""}
                          onChange={(e) =>
                            setPatientData({
                              ...patientData,
                              past_medical_history: parseArray(e.target.value),
                            })
                          }
                        />
                      </div>

                      <div>
                        <Label>Current Medications (comma-separated)</Label>
                        <Input
                          placeholder="e.g., Metformin 500mg BID, Lisinopril 10mg daily"
                          value={patientData.medications?.join(", ") || ""}
                          onChange={(e) =>
                            setPatientData({
                              ...patientData,
                              medications: parseArray(e.target.value),
                            })
                          }
                        />
                      </div>

                      <div>
                        <Label>Allergies (comma-separated)</Label>
                        <Input
                          placeholder="e.g., Penicillin - rash, Sulfa - hives"
                          value={patientData.allergies?.join(", ") || ""}
                          onChange={(e) =>
                            setPatientData({
                              ...patientData,
                              allergies: parseArray(e.target.value),
                            })
                          }
                        />
                      </div>
                    </CardContent>
                  </Card>

                  {/* Encounter Data */}
                  <Card>
                    <CardHeader>
                      <CardTitle>Encounter Data</CardTitle>
                      <CardDescription>
                        Enter encounter-specific information
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="grid gap-4 sm:grid-cols-2">
                        <div>
                          <Label>Encounter Type</Label>
                          <Select
                            value={encounterData.encounter_type}
                            onValueChange={(v) =>
                              setEncounterData({ ...encounterData, encounter_type: v })
                            }
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="outpatient">Outpatient</SelectItem>
                              <SelectItem value="inpatient">Inpatient</SelectItem>
                              <SelectItem value="emergency">Emergency</SelectItem>
                              <SelectItem value="telehealth">Telehealth</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label>Encounter Date</Label>
                          <Input
                            type="date"
                            value={encounterData.encounter_date || ""}
                            onChange={(e) =>
                              setEncounterData({ ...encounterData, encounter_date: e.target.value })
                            }
                          />
                        </div>
                      </div>

                      <div>
                        <Label>Diagnoses (comma-separated)</Label>
                        <Input
                          placeholder="e.g., Acute bronchitis, Hypertension"
                          value={encounterData.diagnoses?.join(", ") || ""}
                          onChange={(e) =>
                            setEncounterData({
                              ...encounterData,
                              diagnoses: parseArray(e.target.value),
                            })
                          }
                        />
                      </div>

                      <div>
                        <Label>Plan Items (comma-separated)</Label>
                        <Input
                          placeholder="e.g., Start antibiotics, Follow up in 1 week, Lab work"
                          value={encounterData.plan_items?.join(", ") || ""}
                          onChange={(e) =>
                            setEncounterData({
                              ...encounterData,
                              plan_items: parseArray(e.target.value),
                            })
                          }
                        />
                      </div>

                      <div>
                        <Label>Custom Instructions (optional)</Label>
                        <Textarea
                          placeholder="Any special instructions for generating this note..."
                          value={customInstructions}
                          onChange={(e) => setCustomInstructions(e.target.value)}
                        />
                      </div>
                    </CardContent>
                  </Card>

                  {/* Generate Button */}
                  <div className="flex justify-end gap-2">
                    <Button
                      size="lg"
                      onClick={handleGenerate}
                      disabled={isGenerating}
                      className="min-w-[200px]"
                    >
                      {isGenerating ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Generating...
                        </>
                      ) : (
                        <>
                          <Sparkles className="mr-2 h-4 w-4" />
                          Generate Note
                        </>
                      )}
                    </Button>
                  </div>

                  {/* Error Message */}
                  {error && (
                    <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950">
                      <div className="flex items-center gap-2 text-red-800 dark:text-red-200">
                        <AlertCircle className="h-4 w-4" />
                        {error}
                      </div>
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="history">
                  <Card>
                    <CardHeader>
                      <CardTitle>Recent Notes</CardTitle>
                      <CardDescription>
                        Previously generated clinical notes
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      {history.length === 0 ? (
                        <div className="py-8 text-center text-zinc-500">
                          No notes generated yet.
                        </div>
                      ) : (
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Type</TableHead>
                              <TableHead>Status</TableHead>
                              <TableHead>Generated</TableHead>
                              <TableHead>Model</TableHead>
                              <TableHead>Tokens</TableHead>
                              <TableHead>Preview</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {history.map((entry) => {
                              const config = NOTE_TYPE_CONFIG[entry.note_type];
                              return (
                                <TableRow key={entry.note_id}>
                                  <TableCell>
                                    <Badge className={config.color}>{config.label}</Badge>
                                  </TableCell>
                                  <TableCell>
                                    <Badge className={STATUS_STYLES[entry.status]}>
                                      {entry.status}
                                    </Badge>
                                  </TableCell>
                                  <TableCell className="text-sm text-zinc-500">
                                    {new Date(entry.generated_at).toLocaleString()}
                                  </TableCell>
                                  <TableCell className="text-sm font-mono">
                                    {entry.model_used}
                                  </TableCell>
                                  <TableCell className="text-sm">
                                    {entry.token_usage.toLocaleString()}
                                  </TableCell>
                                  <TableCell className="max-w-[200px] truncate text-sm text-zinc-500">
                                    {entry.preview}
                                  </TableCell>
                                </TableRow>
                              );
                            })}
                          </TableBody>
                        </Table>
                      )}
                    </CardContent>
                  </Card>
                </TabsContent>
              </Tabs>
            </div>

            {/* Right Panel - Generated Note Preview */}
            <div className="space-y-6">
              <Card className="sticky top-6">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      <FileText className="h-5 w-5" />
                      Generated Note
                    </CardTitle>
                    {generatedNote && (
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={copyToClipboard}>
                          <Clipboard className="h-4 w-4" />
                        </Button>
                        <Button size="sm" onClick={openInEditor}>
                          Edit
                          <ChevronRight className="ml-1 h-4 w-4" />
                        </Button>
                      </div>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  {generatedNote ? (
                    <div className="space-y-4">
                      {/* Note Metadata */}
                      <div className="flex flex-wrap gap-2">
                        <Badge className={NOTE_TYPE_CONFIG[generatedNote.note_type].color}>
                          {NOTE_TYPE_CONFIG[generatedNote.note_type].label}
                        </Badge>
                        <Badge className={STATUS_STYLES[generatedNote.status]}>
                          {generatedNote.status === "complete" && (
                            <CheckCircle className="mr-1 h-3 w-3" />
                          )}
                          {generatedNote.status}
                        </Badge>
                        <Badge variant="outline" className={CONFIDENCE_STYLES[generatedNote.confidence]}>
                          {generatedNote.confidence} confidence
                        </Badge>
                      </div>

                      {/* Stats */}
                      <div className="grid grid-cols-3 gap-2 text-sm">
                        <div className="rounded-lg bg-zinc-100 p-2 dark:bg-zinc-800">
                          <div className="text-xs text-zinc-500">Tokens</div>
                          <div className="font-medium">{generatedNote.token_usage.toLocaleString()}</div>
                        </div>
                        <div className="rounded-lg bg-zinc-100 p-2 dark:bg-zinc-800">
                          <div className="text-xs text-zinc-500">Cost</div>
                          <div className="font-medium">${generatedNote.cost_usd.toFixed(4)}</div>
                        </div>
                        <div className="rounded-lg bg-zinc-100 p-2 dark:bg-zinc-800">
                          <div className="text-xs text-zinc-500">Time</div>
                          <div className="font-medium">{(generatedNote.latency_ms / 1000).toFixed(1)}s</div>
                        </div>
                      </div>

                      {/* Validation Warnings */}
                      {generatedNote.validation && !generatedNote.validation.is_valid && (
                        <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-3 dark:border-yellow-900 dark:bg-yellow-950">
                          <div className="font-medium text-yellow-800 dark:text-yellow-200">
                            Validation Issues
                          </div>
                          <ul className="mt-1 list-inside list-disc text-sm text-yellow-700 dark:text-yellow-300">
                            {generatedNote.validation.missing_sections.map((s) => (
                              <li key={s}>Missing: {s}</li>
                            ))}
                            {generatedNote.validation.incomplete_sections.map((s) => (
                              <li key={s}>Incomplete: {s}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Note Content Preview */}
                      <div className="max-h-[500px] overflow-y-auto rounded-lg border bg-white p-4 dark:bg-zinc-950">
                        <pre className="whitespace-pre-wrap text-sm">{generatedNote.content}</pre>
                      </div>
                    </div>
                  ) : (
                    <div className="py-12 text-center">
                      <FileText className="mx-auto h-12 w-12 text-zinc-300 dark:text-zinc-700" />
                      <p className="mt-2 text-zinc-500">
                        Fill in the form and click Generate to create a clinical note.
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Quick Stats */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Session Stats</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Notes Generated</span>
                      <span className="font-medium">{history.length}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Templates Available</span>
                      <span className="font-medium">{templates.length}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Patients</span>
                      <span className="font-medium">{patients.length}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
