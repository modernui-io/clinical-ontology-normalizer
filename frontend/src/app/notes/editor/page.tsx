"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  FileText,
  Sparkles,
  Save,
  Download,
  Copy,
  Loader2,
  CheckCircle,
  AlertCircle,
  Wand2,
  Settings,
  ChevronRight,
  GripVertical,
  Trash2,
  Plus,
  RefreshCw,
  FileDown,
} from "lucide-react";
import {
  NoteType,
  NoteTemplate,
  GeneratedNoteResponse,
  NoteSectionResponse,
  getNoteTemplates,
  enhanceNote,
  validateNote,
  NoteValidationResponse,
} from "@/lib/api";

// Note type styling
const NOTE_TYPE_LABELS: Record<NoteType, string> = {
  soap: "SOAP Note",
  hp: "History & Physical",
  progress: "Progress Note",
  discharge: "Discharge Summary",
  procedure: "Procedure Note",
};

const SECTION_STATUS_STYLES: Record<string, string> = {
  complete: "border-l-green-500",
  generated: "border-l-blue-500",
  partial: "border-l-yellow-500",
  missing: "border-l-red-500",
  user_provided: "border-l-purple-500",
};

const STATUS_BADGES: Record<string, { color: string; label: string }> = {
  complete: { color: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300", label: "Complete" },
  generated: { color: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300", label: "Generated" },
  partial: { color: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300", label: "Partial" },
  missing: { color: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300", label: "Missing" },
  user_provided: { color: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300", label: "User" },
};

interface EditableSection {
  name: string;
  key: string;
  content: string;
  required: boolean;
  order: number;
  status: string;
  isEditing: boolean;
}

export default function NoteEditorPage() {
  // State
  const [templates, setTemplates] = useState<NoteTemplate[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isEnhancing, setIsEnhancing] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Note state
  const [noteType, setNoteType] = useState<NoteType>("soap");
  const [noteContent, setNoteContent] = useState("");
  const [sections, setSections] = useState<EditableSection[]>([]);
  const [validation, setValidation] = useState<NoteValidationResponse | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<string>("");

  // Original note (for comparison)
  const [originalNote, setOriginalNote] = useState<GeneratedNoteResponse | null>(null);

  // Load initial data
  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      // Load templates
      const templatesRes = await getNoteTemplates();
      setTemplates(templatesRes.templates);

      // Check for note passed via sessionStorage
      const storedNote = sessionStorage.getItem("generatedNote");
      if (storedNote) {
        const note = JSON.parse(storedNote) as GeneratedNoteResponse;
        setOriginalNote(note);
        setNoteType(note.note_type);
        setNoteContent(note.content);
        setSections(
          note.sections.map((s) => ({
            ...s,
            isEditing: false,
          }))
        );
        if (note.template_id) {
          setSelectedTemplate(note.template_id);
        }
        // Clear from sessionStorage
        sessionStorage.removeItem("generatedNote");
      } else {
        // Initialize with empty SOAP sections
        initializeEmptySections("soap");
      }

      setError(null);
    } catch (err) {
      console.error("Failed to load data:", err);
      setError("Failed to load templates.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Initialize empty sections for a note type
  const initializeEmptySections = (type: NoteType) => {
    const sectionConfigs: Record<NoteType, { name: string; key: string; required: boolean }[]> = {
      soap: [
        { name: "Subjective", key: "subjective", required: true },
        { name: "Objective", key: "objective", required: true },
        { name: "Assessment", key: "assessment", required: true },
        { name: "Plan", key: "plan", required: true },
      ],
      hp: [
        { name: "Chief Complaint", key: "cc", required: true },
        { name: "History of Present Illness", key: "hpi", required: true },
        { name: "Past Medical History", key: "pmh", required: true },
        { name: "Medications", key: "medications", required: true },
        { name: "Allergies", key: "allergies", required: true },
        { name: "Family History", key: "fh", required: false },
        { name: "Social History", key: "sh", required: true },
        { name: "Review of Systems", key: "ros", required: true },
        { name: "Physical Examination", key: "pe", required: true },
        { name: "Assessment", key: "assessment", required: true },
        { name: "Plan", key: "plan", required: true },
      ],
      progress: [
        { name: "Interval History", key: "interval", required: true },
        { name: "Current Symptoms", key: "symptoms", required: true },
        { name: "Vital Signs", key: "vitals", required: true },
        { name: "Physical Exam", key: "exam", required: true },
        { name: "Assessment", key: "assessment", required: true },
        { name: "Plan", key: "plan", required: true },
      ],
      discharge: [
        { name: "Admission/Discharge Dates", key: "dates", required: true },
        { name: "Discharge Diagnoses", key: "diagnoses", required: true },
        { name: "Hospital Course", key: "course", required: true },
        { name: "Procedures", key: "procedures", required: false },
        { name: "Discharge Medications", key: "medications", required: true },
        { name: "Discharge Condition", key: "condition", required: true },
        { name: "Follow-up", key: "follow_up", required: true },
        { name: "Discharge Instructions", key: "instructions", required: true },
      ],
      procedure: [
        { name: "Procedure", key: "procedure", required: true },
        { name: "Indication", key: "indication", required: true },
        { name: "Consent", key: "consent", required: true },
        { name: "Anesthesia", key: "anesthesia", required: false },
        { name: "Description", key: "description", required: true },
        { name: "Findings", key: "findings", required: true },
        { name: "Specimens", key: "specimens", required: false },
        { name: "Complications", key: "complications", required: true },
        { name: "Disposition", key: "disposition", required: true },
      ],
    };

    const config = sectionConfigs[type];
    setSections(
      config.map((s, i) => ({
        ...s,
        content: "",
        order: i + 1,
        status: "missing",
        isEditing: false,
      }))
    );
    setNoteContent("");
  };

  // Handle note type change
  const handleNoteTypeChange = (type: NoteType) => {
    setNoteType(type);
    setSelectedTemplate("");
    initializeEmptySections(type);
    setValidation(null);
  };

  // Update section content
  const updateSectionContent = (key: string, content: string) => {
    setSections((prev) =>
      prev.map((s) =>
        s.key === key
          ? { ...s, content, status: content.trim() ? "user_provided" : "missing" }
          : s
      )
    );
  };

  // Toggle section editing
  const toggleSectionEditing = (key: string) => {
    setSections((prev) =>
      prev.map((s) => (s.key === key ? { ...s, isEditing: !s.isEditing } : s))
    );
  };

  // Rebuild full content from sections
  const rebuildContent = () => {
    const content = sections
      .filter((s) => s.content.trim())
      .map((s) => `${s.name.toUpperCase()}:\n${s.content}`)
      .join("\n\n");
    setNoteContent(content);
    return content;
  };

  // Enhance note with AI
  const handleEnhance = async () => {
    setIsEnhancing(true);
    setError(null);
    try {
      const currentContent = rebuildContent();
      const result = await enhanceNote({
        content: currentContent || "Empty note",
        note_type: noteType,
      });

      setNoteContent(result.enhanced_content);
      setSuccessMessage(
        `Enhanced ${result.sections_enhanced.length} sections, added ${result.sections_added.length} sections`
      );
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      console.error("Enhancement failed:", err);
      setError("Failed to enhance note. Please try again.");
    } finally {
      setIsEnhancing(false);
    }
  };

  // Validate note
  const handleValidate = async () => {
    setIsValidating(true);
    setError(null);
    try {
      const currentContent = rebuildContent();
      const result = await validateNote({
        content: currentContent || "Empty note",
        note_type: noteType,
      });

      setValidation(result);
    } catch (err) {
      console.error("Validation failed:", err);
      setError("Failed to validate note. Please try again.");
    } finally {
      setIsValidating(false);
    }
  };

  // Copy to clipboard
  const handleCopy = async () => {
    const content = rebuildContent();
    await navigator.clipboard.writeText(content);
    setSuccessMessage("Copied to clipboard!");
    setTimeout(() => setSuccessMessage(null), 2000);
  };

  // Download as text file
  const handleDownload = () => {
    const content = rebuildContent();
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${noteType}_note_${new Date().toISOString().split("T")[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setSuccessMessage("Downloaded!");
    setTimeout(() => setSuccessMessage(null), 2000);
  };

  // Filter templates for current note type
  const filteredTemplates = templates.filter((t) => t.note_type === noteType);

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                href="/notes"
                className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
              >
                &larr; Notes
              </Link>
              <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                Note Editor
              </h1>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={handleValidate}
                disabled={isValidating}
              >
                {isValidating ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <CheckCircle className="mr-2 h-4 w-4" />
                )}
                Validate
              </Button>
              <Button
                variant="outline"
                onClick={handleEnhance}
                disabled={isEnhancing}
              >
                {isEnhancing ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Wand2 className="mr-2 h-4 w-4" />
                )}
                Enhance
              </Button>
              <Button variant="outline" onClick={handleCopy}>
                <Copy className="mr-2 h-4 w-4" />
                Copy
              </Button>
              <Button onClick={handleDownload}>
                <Download className="mr-2 h-4 w-4" />
                Export
              </Button>
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
          <div className="grid gap-6 lg:grid-cols-4">
            {/* Left Sidebar - Settings & Facts */}
            <div className="space-y-6">
              {/* Note Settings */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Settings className="h-4 w-4" />
                    Settings
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <Label>Note Type</Label>
                    <Select value={noteType} onValueChange={(v) => handleNoteTypeChange(v as NoteType)}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(Object.keys(NOTE_TYPE_LABELS) as NoteType[]).map((type) => (
                          <SelectItem key={type} value={type}>
                            {NOTE_TYPE_LABELS[type]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <Label>Template</Label>
                    <Select value={selectedTemplate} onValueChange={setSelectedTemplate}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select template" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="">Default</SelectItem>
                        {filteredTemplates.map((t) => (
                          <SelectItem key={t.template_id} value={t.template_id}>
                            {t.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </CardContent>
              </Card>

              {/* Validation Results */}
              {validation && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm flex items-center gap-2">
                      {validation.is_valid ? (
                        <CheckCircle className="h-4 w-4 text-green-500" />
                      ) : (
                        <AlertCircle className="h-4 w-4 text-yellow-500" />
                      )}
                      Validation
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-zinc-500">Completeness</span>
                      <span className="font-medium">
                        {Math.round(validation.completeness_score * 100)}%
                      </span>
                    </div>

                    {validation.missing_sections.length > 0 && (
                      <div>
                        <div className="text-sm font-medium text-red-600 dark:text-red-400">
                          Missing Sections
                        </div>
                        <ul className="mt-1 text-xs text-zinc-500">
                          {validation.missing_sections.map((s) => (
                            <li key={s}>- {s}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {validation.suggestions.length > 0 && (
                      <div>
                        <div className="text-sm font-medium text-blue-600 dark:text-blue-400">
                          Suggestions
                        </div>
                        <ul className="mt-1 text-xs text-zinc-500">
                          {validation.suggestions.slice(0, 3).map((s, i) => (
                            <li key={i}>- {s}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* Section Overview */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Sections</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-1">
                    {sections.map((section) => {
                      const statusStyle = STATUS_BADGES[section.status] || STATUS_BADGES.missing;
                      return (
                        <div
                          key={section.key}
                          className={`flex items-center justify-between rounded px-2 py-1 text-sm ${
                            section.content.trim() ? "bg-zinc-100 dark:bg-zinc-800" : ""
                          }`}
                        >
                          <span className="flex items-center gap-1">
                            {section.required && (
                              <span className="text-red-500">*</span>
                            )}
                            {section.name}
                          </span>
                          <Badge className={`text-xs ${statusStyle.color}`}>
                            {statusStyle.label}
                          </Badge>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Main Editor Area */}
            <div className="lg:col-span-3 space-y-4">
              {/* Messages */}
              {error && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-900 dark:bg-red-950">
                  <div className="flex items-center gap-2 text-red-800 dark:text-red-200">
                    <AlertCircle className="h-4 w-4" />
                    {error}
                  </div>
                </div>
              )}

              {successMessage && (
                <div className="rounded-lg border border-green-200 bg-green-50 p-3 dark:border-green-900 dark:bg-green-950">
                  <div className="flex items-center gap-2 text-green-800 dark:text-green-200">
                    <CheckCircle className="h-4 w-4" />
                    {successMessage}
                  </div>
                </div>
              )}

              <Tabs defaultValue="sections" className="space-y-4">
                <TabsList>
                  <TabsTrigger value="sections">Section Editor</TabsTrigger>
                  <TabsTrigger value="raw">Full Text</TabsTrigger>
                </TabsList>

                <TabsContent value="sections" className="space-y-4">
                  {/* Section-based Editor */}
                  {sections.map((section) => (
                    <Card
                      key={section.key}
                      className={`border-l-4 ${SECTION_STATUS_STYLES[section.status] || "border-l-zinc-300"}`}
                    >
                      <CardHeader className="py-3">
                        <div className="flex items-center justify-between">
                          <CardTitle className="text-sm flex items-center gap-2">
                            <GripVertical className="h-4 w-4 text-zinc-400 cursor-grab" />
                            {section.name}
                            {section.required && (
                              <span className="text-red-500">*</span>
                            )}
                          </CardTitle>
                          <div className="flex items-center gap-2">
                            <Badge
                              className={`text-xs ${STATUS_BADGES[section.status]?.color || ""}`}
                            >
                              {STATUS_BADGES[section.status]?.label || section.status}
                            </Badge>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => toggleSectionEditing(section.key)}
                            >
                              {section.isEditing ? "Done" : "Edit"}
                            </Button>
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent className="py-0 pb-4">
                        {section.isEditing ? (
                          <Textarea
                            value={section.content}
                            onChange={(e) => updateSectionContent(section.key, e.target.value)}
                            className="min-h-[150px] font-mono text-sm"
                            placeholder={`Enter ${section.name.toLowerCase()} content...`}
                          />
                        ) : (
                          <div
                            className="min-h-[60px] rounded border bg-zinc-50 p-3 text-sm dark:bg-zinc-900 cursor-pointer hover:bg-zinc-100 dark:hover:bg-zinc-800"
                            onClick={() => toggleSectionEditing(section.key)}
                          >
                            {section.content ? (
                              <pre className="whitespace-pre-wrap">{section.content}</pre>
                            ) : (
                              <span className="text-zinc-400 italic">
                                Click to add {section.name.toLowerCase()}...
                              </span>
                            )}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  ))}
                </TabsContent>

                <TabsContent value="raw">
                  {/* Full text editor */}
                  <Card>
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-sm">Full Note Text</CardTitle>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={rebuildContent}
                        >
                          <RefreshCw className="mr-2 h-4 w-4" />
                          Sync from Sections
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <Textarea
                        value={noteContent}
                        onChange={(e) => setNoteContent(e.target.value)}
                        className="min-h-[600px] font-mono text-sm"
                        placeholder="Enter or paste your clinical note here..."
                      />
                    </CardContent>
                  </Card>
                </TabsContent>
              </Tabs>

              {/* Quick Actions */}
              <div className="flex justify-between items-center pt-4 border-t">
                <div className="text-sm text-zinc-500">
                  {sections.filter((s) => s.content.trim()).length} of {sections.length} sections filled
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() => {
                      initializeEmptySections(noteType);
                      setValidation(null);
                    }}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Clear All
                  </Button>
                  <Button onClick={handleDownload}>
                    <FileDown className="mr-2 h-4 w-4" />
                    Export Note
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
