"use client";

import { useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
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
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { uploadDocument, DocumentCreate } from "@/lib/api";

const NOTE_TYPES = [
  "Discharge Summary",
  "Progress Note",
  "History & Physical",
  "Consultation Note",
  "Operative Report",
  "Radiology Report",
  "Pathology Report",
  "Emergency Department Note",
  "Other",
];

const ACCEPTED_EXTENSIONS = [".txt", ".pdf", ".docx", ".json"];

interface FileUploadItem {
  id: string;
  file: File;
  status: "pending" | "uploading" | "success" | "error";
  progress: number;
  error?: string;
  preview?: string;
  patientId: string;
  noteType: string;
}

function generateId(): string {
  return Math.random().toString(36).substring(2, 15);
}

async function readFileContent(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result as string;
      resolve(content);
    };
    reader.onerror = () => reject(new Error("Failed to read file"));

    if (file.type === "application/json" || file.name.endsWith(".json")) {
      reader.readAsText(file);
    } else if (file.type === "text/plain" || file.name.endsWith(".txt")) {
      reader.readAsText(file);
    } else if (file.type === "application/pdf" || file.name.endsWith(".pdf")) {
      // For PDF, we'll just show a message - actual extraction would need server-side
      resolve("[PDF content - text extraction will be performed server-side]");
    } else if (file.name.endsWith(".docx")) {
      // For DOCX, we'll just show a message - actual extraction would need server-side
      resolve("[DOCX content - text extraction will be performed server-side]");
    } else {
      reader.readAsText(file);
    }
  });
}

function isValidFileType(file: File): boolean {
  const extension = "." + file.name.split(".").pop()?.toLowerCase();
  return ACCEPTED_EXTENSIONS.includes(extension);
}

export default function UploadDocumentPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragActive, setIsDragActive] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [fileItems, setFileItems] = useState<FileUploadItem[]>([]);
  const [formData, setFormData] = useState<DocumentCreate>({
    patient_id: "",
    note_type: NOTE_TYPES[0],
    text: "",
  });

  // Handle drag events
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  // Process dropped or selected files
  const processFiles = useCallback(async (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    const newItems: FileUploadItem[] = [];

    for (const file of fileArray) {
      if (!isValidFileType(file)) {
        toast.error(`Invalid file type: ${file.name}. Accepted: ${ACCEPTED_EXTENSIONS.join(", ")}`);
        continue;
      }

      try {
        const preview = await readFileContent(file);
        newItems.push({
          id: generateId(),
          file,
          status: "pending",
          progress: 0,
          preview: preview.substring(0, 500) + (preview.length > 500 ? "..." : ""),
          patientId: "",
          noteType: NOTE_TYPES[0],
        });
      } catch {
        toast.error(`Failed to read file: ${file.name}`);
      }
    }

    if (newItems.length > 0) {
      setFileItems((prev) => [...prev, ...newItems]);
    }
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragActive(false);

      const { files } = e.dataTransfer;
      if (files && files.length > 0) {
        processFiles(files);
      }
    },
    [processFiles]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const { files } = e.target;
      if (files && files.length > 0) {
        processFiles(files);
      }
      // Reset input value to allow selecting the same file again
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    },
    [processFiles]
  );

  const handleRemoveFile = useCallback((id: string) => {
    setFileItems((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const handleUpdateFileItem = useCallback((id: string, updates: Partial<FileUploadItem>) => {
    setFileItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, ...updates } : item))
    );
  }, []);

  // Manual text submission
  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.patient_id.trim()) {
      toast.error("Patient ID is required");
      return;
    }

    if (!formData.text.trim()) {
      toast.error("Document text is required");
      return;
    }

    setIsLoading(true);

    try {
      const result = await uploadDocument(formData);
      toast.success("Document uploaded successfully");
      router.push(`/jobs/${result.job_id}`);
    } catch (error) {
      console.error("Upload failed:", error);
      toast.error("Failed to upload document. Is the backend running?");
    } finally {
      setIsLoading(false);
    }
  };

  // Batch file upload
  const handleBatchUpload = async () => {
    const pendingItems = fileItems.filter((item) => item.status === "pending");

    if (pendingItems.length === 0) {
      toast.error("No files to upload");
      return;
    }

    // Validate all items have patient IDs
    const invalidItems = pendingItems.filter((item) => !item.patientId.trim());
    if (invalidItems.length > 0) {
      toast.error("All files must have a Patient ID");
      return;
    }

    setIsLoading(true);
    let successCount = 0;
    let lastJobId = "";

    for (const item of pendingItems) {
      handleUpdateFileItem(item.id, { status: "uploading", progress: 10 });

      try {
        // Read full content for upload
        const fullContent = await readFileContent(item.file);
        handleUpdateFileItem(item.id, { progress: 30 });

        const documentData: DocumentCreate = {
          patient_id: item.patientId,
          note_type: item.noteType,
          text: fullContent,
        };

        handleUpdateFileItem(item.id, { progress: 50 });

        const result = await uploadDocument(documentData);
        lastJobId = result.job_id;

        handleUpdateFileItem(item.id, { status: "success", progress: 100 });
        successCount++;
      } catch (error) {
        console.error("Upload failed:", error);
        handleUpdateFileItem(item.id, {
          status: "error",
          progress: 0,
          error: "Upload failed",
        });
      }
    }

    setIsLoading(false);

    if (successCount > 0) {
      toast.success(`Successfully uploaded ${successCount} document(s)`);
      if (successCount === 1 && lastJobId) {
        router.push(`/jobs/${lastJobId}`);
      } else {
        router.push("/documents");
      }
    } else {
      toast.error("All uploads failed");
    }
  };

  const getStatusColor = (status: FileUploadItem["status"]) => {
    switch (status) {
      case "pending":
        return "bg-zinc-500";
      case "uploading":
        return "bg-blue-500";
      case "success":
        return "bg-green-500";
      case "error":
        return "bg-red-500";
      default:
        return "bg-zinc-500";
    }
  };

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center gap-4">
            <Link href="/documents" className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100">
              &larr; Documents
            </Link>
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
              Upload Document
            </h1>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <div className="mx-auto max-w-4xl space-y-6">
          {/* Drag and Drop Zone */}
          <Card>
            <CardHeader>
              <CardTitle>Upload Files</CardTitle>
              <CardDescription>
                Drag and drop files or click to browse. Supported: .txt, .pdf, .docx, .json
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div
                className={`
                  relative flex min-h-[200px] cursor-pointer flex-col items-center justify-center
                  rounded-lg border-2 border-dashed transition-all
                  ${
                    isDragActive
                      ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
                      : "border-zinc-300 bg-zinc-50 hover:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-800/50 dark:hover:border-zinc-600"
                  }
                `}
                onDragEnter={handleDragEnter}
                onDragLeave={handleDragLeave}
                onDragOver={handleDragOver}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept={ACCEPTED_EXTENSIONS.join(",")}
                  onChange={handleFileSelect}
                  className="hidden"
                />
                <div className="pointer-events-none text-center">
                  <svg
                    className={`mx-auto h-12 w-12 ${isDragActive ? "text-blue-500" : "text-zinc-400"}`}
                    stroke="currentColor"
                    fill="none"
                    viewBox="0 0 48 48"
                    aria-hidden="true"
                  >
                    <path
                      d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                      strokeWidth={2}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
                    {isDragActive ? (
                      <span className="text-blue-500">Drop files here</span>
                    ) : (
                      <>
                        <span className="font-semibold text-blue-600 dark:text-blue-400">
                          Click to upload
                        </span>{" "}
                        or drag and drop
                      </>
                    )}
                  </p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-500">
                    TXT, PDF, DOCX, or JSON files
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* File List */}
          {fileItems.length > 0 && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Uploaded Files ({fileItems.length})</CardTitle>
                    <CardDescription>
                      Configure each file before uploading
                    </CardDescription>
                  </div>
                  <Button onClick={handleBatchUpload} disabled={isLoading}>
                    {isLoading ? "Uploading..." : "Upload All"}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {fileItems.map((item) => (
                  <div
                    key={item.id}
                    className="rounded-lg border bg-white p-4 dark:bg-zinc-900"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 space-y-3">
                        <div className="flex items-center gap-2">
                          <Badge className={getStatusColor(item.status)}>
                            {item.status.toUpperCase()}
                          </Badge>
                          <span className="font-medium">{item.file.name}</span>
                          <span className="text-sm text-zinc-500">
                            ({(item.file.size / 1024).toFixed(1)} KB)
                          </span>
                        </div>

                        {item.status === "uploading" && (
                          <Progress value={item.progress} className="h-2" />
                        )}

                        {item.status === "error" && item.error && (
                          <p className="text-sm text-red-600">{item.error}</p>
                        )}

                        {item.status === "pending" && (
                          <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1">
                              <Label className="text-xs">Patient ID</Label>
                              <Input
                                placeholder="e.g., P001"
                                value={item.patientId}
                                onChange={(e) =>
                                  handleUpdateFileItem(item.id, {
                                    patientId: e.target.value,
                                  })
                                }
                              />
                            </div>
                            <div className="space-y-1">
                              <Label className="text-xs">Note Type</Label>
                              <select
                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                value={item.noteType}
                                onChange={(e) =>
                                  handleUpdateFileItem(item.id, {
                                    noteType: e.target.value,
                                  })
                                }
                              >
                                {NOTE_TYPES.map((type) => (
                                  <option key={type} value={type}>
                                    {type}
                                  </option>
                                ))}
                              </select>
                            </div>
                          </div>
                        )}

                        {item.preview && item.status === "pending" && (
                          <div className="mt-2">
                            <Label className="text-xs text-zinc-500">Preview</Label>
                            <div className="mt-1 max-h-24 overflow-y-auto rounded bg-zinc-100 p-2 font-mono text-xs dark:bg-zinc-800">
                              {item.preview}
                            </div>
                          </div>
                        )}
                      </div>

                      {item.status === "pending" && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveFile(item.id)}
                          className="text-zinc-500 hover:text-red-500"
                        >
                          Remove
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Manual Entry Option */}
          <Card>
            <CardHeader>
              <CardTitle>Or Enter Text Manually</CardTitle>
              <CardDescription>
                Paste clinical note text directly for NLP processing
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleManualSubmit} className="space-y-6">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="patient_id">Patient ID</Label>
                    <Input
                      id="patient_id"
                      placeholder="e.g., P001"
                      value={formData.patient_id}
                      onChange={(e) =>
                        setFormData({ ...formData, patient_id: e.target.value })
                      }
                      required
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="note_type">Note Type</Label>
                    <select
                      id="note_type"
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      value={formData.note_type}
                      onChange={(e) =>
                        setFormData({ ...formData, note_type: e.target.value })
                      }
                    >
                      {NOTE_TYPES.map((type) => (
                        <option key={type} value={type}>
                          {type}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="text">Clinical Note Text</Label>
                  <Textarea
                    id="text"
                    placeholder="Paste clinical note text here..."
                    className="min-h-[200px]"
                    value={formData.text}
                    onChange={(e) =>
                      setFormData({ ...formData, text: e.target.value })
                    }
                    required
                  />
                  <p className="text-sm text-zinc-500">
                    {formData.text.length} characters
                  </p>
                </div>

                <div className="flex gap-4">
                  <Button type="submit" disabled={isLoading}>
                    {isLoading ? "Uploading..." : "Upload Document"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => router.back()}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
