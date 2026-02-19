"use client";

import { useState, useCallback, useRef } from "react";
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
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  useUploadMimicCsv,
  useValidateMimicCsv,
  useImportMimicFromPath,
  useValidateMimicPath,
  useMimicImportProgress,
} from "@/hooks/api/useMimic";
import type { MimicValidateResponse } from "@/lib/api";

type ImportMode = "upload" | "server-path";

export default function MimicImportPage() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<ImportMode>("server-path");
  const [isDragActive, setIsDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [serverPath, setServerPath] = useState("");
  const [validation, setValidation] = useState<MimicValidateResponse | null>(null);
  const [batchId, setBatchId] = useState<string | null>(null);

  // Config state
  const [chunkSize, setChunkSize] = useState(100);
  const [maxRows, setMaxRows] = useState<string>("");
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const [enqueueProcessing, setEnqueueProcessing] = useState(true);

  const onValidationResult = (data: MimicValidateResponse) => {
    setValidation(data);
    if (data.valid) {
      toast.success(`CSV valid: ${data.total_rows.toLocaleString()} rows found`);
    } else {
      toast.error(`CSV validation failed: ${data.errors.length} error(s)`);
    }
  };

  const validateFileMutation = useValidateMimicCsv({
    onSuccess: onValidationResult,
    onError: () => toast.error("Failed to validate CSV"),
  });

  const validatePathMutation = useValidateMimicPath({
    onSuccess: onValidationResult,
    onError: (err) => toast.error(err.message || "Failed to validate server path"),
  });

  const uploadMutation = useUploadMimicCsv({
    onSuccess: (data) => { setBatchId(data.batch_id); toast.success(data.message); },
    onError: () => toast.error("Failed to start MIMIC import"),
  });

  const pathImportMutation = useImportMimicFromPath({
    onSuccess: (data) => { setBatchId(data.batch_id); toast.success(data.message); },
    onError: (err) => toast.error(err.message || "Failed to start import from path"),
  });

  const { data: progress } = useMimicImportProgress(batchId);

  const handleFileSelect = useCallback(
    (file: File) => {
      if (!file.name.endsWith(".csv")) {
        toast.error("Please select a CSV file");
        return;
      }
      setSelectedFile(file);
      setValidation(null);
      setBatchId(null);
      validateFileMutation.mutate(file);
    },
    [validateFileMutation]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragActive(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFileSelect(file);
    },
    [handleFileSelect]
  );

  const handleValidatePath = () => {
    if (!serverPath.trim()) {
      toast.error("Enter a file path");
      return;
    }
    setValidation(null);
    setBatchId(null);
    validatePathMutation.mutate(serverPath.trim());
  };

  const handleImport = () => {
    const parsedMaxRows = maxRows ? parseInt(maxRows, 10) : undefined;

    if (mode === "upload") {
      if (!selectedFile) return;
      uploadMutation.mutate({
        file: selectedFile,
        chunkSize,
        maxRows: parsedMaxRows,
        skipDuplicates,
        enqueueProcessing,
      });
    } else {
      if (!serverPath.trim()) return;
      pathImportMutation.mutate({
        file_path: serverPath.trim(),
        chunk_size: chunkSize,
        max_rows: parsedMaxRows,
        skip_duplicates: skipDuplicates,
        enqueue_processing: enqueueProcessing,
      });
    }
  };

  const isValidating = validateFileMutation.isPending || validatePathMutation.isPending;
  const isStarting = uploadMutation.isPending || pathImportMutation.isPending;
  const isCompleted = progress?.status === "completed";
  const isFailed = progress?.status === "failed";

  const switchMode = (newMode: ImportMode) => {
    setMode(newMode);
    setValidation(null);
    setBatchId(null);
    setSelectedFile(null);
    setServerPath("");
  };

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                MIMIC-IV-Note Import
              </h1>
              <Badge variant="secondary">Validation Pipeline</Badge>
            </div>
            <Link href="/mimic/validation">
              <Button variant="outline">Validation Dashboard</Button>
            </Link>
          </div>
          <p className="mt-1 text-sm text-zinc-500">
            Import MIMIC-IV discharge summaries to validate the NLP pipeline against real ICU data
          </p>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <div className="mx-auto max-w-4xl space-y-6">
          {/* Mode Selector */}
          <div className="flex gap-2">
            <Button
              variant={mode === "server-path" ? "default" : "outline"}
              onClick={() => switchMode("server-path")}
            >
              Server File Path
            </Button>
            <Button
              variant={mode === "upload" ? "default" : "outline"}
              onClick={() => switchMode("upload")}
            >
              Browser Upload
            </Button>
          </div>

          {/* Server Path Mode */}
          {mode === "server-path" && (
            <Card>
              <CardHeader>
                <CardTitle>Import from Server Path</CardTitle>
                <CardDescription>
                  Point to a MIMIC CSV already on the server. Recommended for large files (331K+ rows) — no browser upload needed.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="server_path">File Path</Label>
                  <div className="flex gap-2">
                    <Input
                      id="server_path"
                      placeholder="/data/mimic-iv-note/discharge.csv"
                      value={serverPath}
                      onChange={(e) => setServerPath(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") handleValidatePath(); }}
                      className="font-mono text-sm"
                    />
                    <Button
                      onClick={handleValidatePath}
                      disabled={isValidating || !serverPath.trim()}
                      variant="secondary"
                    >
                      {isValidating ? "Validating..." : "Validate"}
                    </Button>
                  </div>
                  <p className="text-xs text-zinc-500">
                    Absolute path to the CSV on the server filesystem
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Browser Upload Mode */}
          {mode === "upload" && (
            <Card>
              <CardHeader>
                <CardTitle>Upload MIMIC CSV</CardTitle>
                <CardDescription>
                  Upload a small MIMIC CSV via browser. For large files, use Server File Path instead.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div
                  className={`
                    relative flex min-h-[180px] cursor-pointer flex-col items-center justify-center
                    rounded-lg border-2 border-dashed transition-all
                    ${
                      isDragActive
                        ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
                        : "border-zinc-300 bg-zinc-50 hover:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-800/50"
                    }
                  `}
                  onDragEnter={(e) => { e.preventDefault(); setIsDragActive(true); }}
                  onDragLeave={(e) => { e.preventDefault(); setIsDragActive(false); }}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) handleFileSelect(file);
                      if (fileInputRef.current) fileInputRef.current.value = "";
                    }}
                    className="hidden"
                  />
                  <div className="pointer-events-none text-center">
                    <svg
                      className={`mx-auto h-12 w-12 ${isDragActive ? "text-blue-500" : "text-zinc-400"}`}
                      stroke="currentColor"
                      fill="none"
                      viewBox="0 0 48 48"
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
                        <span className="text-blue-500">Drop CSV here</span>
                      ) : (
                        <>
                          <span className="font-semibold text-blue-600 dark:text-blue-400">
                            Click to upload
                          </span>{" "}
                          or drag and drop
                        </>
                      )}
                    </p>
                    <p className="text-xs text-zinc-500">CSV files only</p>
                  </div>
                </div>

                {selectedFile && (
                  <div className="mt-3 flex items-center gap-2 text-sm">
                    <Badge variant="outline">{selectedFile.name}</Badge>
                    <span className="text-zinc-500">
                      ({(selectedFile.size / (1024 * 1024)).toFixed(1)} MB)
                    </span>
                    {validateFileMutation.isPending && (
                      <span className="text-blue-500">Validating...</span>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Validation Preview */}
          {validation && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  CSV Validation
                  <Badge variant={validation.valid ? "default" : "destructive"}>
                    {validation.valid ? "Valid" : "Invalid"}
                  </Badge>
                </CardTitle>
                <CardDescription>
                  {validation.total_rows.toLocaleString()} rows found
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label className="text-xs font-medium">Columns Found</Label>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {validation.columns_found.map((col) => (
                      <Badge key={col} variant="secondary" className="text-xs">
                        {col}
                      </Badge>
                    ))}
                  </div>
                </div>

                {validation.columns_missing.length > 0 && (
                  <div>
                    <Label className="text-xs font-medium text-red-600">Missing Columns</Label>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {validation.columns_missing.map((col) => (
                        <Badge key={col} variant="destructive" className="text-xs">
                          {col}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {validation.errors.length > 0 && (
                  <div>
                    <Label className="text-xs font-medium text-red-600">Errors</Label>
                    <ul className="mt-1 space-y-1">
                      {validation.errors.map((err, i) => (
                        <li key={i} className="text-xs text-red-600">{err}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {validation.sample_rows.length > 0 && (
                  <div>
                    <Label className="text-xs font-medium">Sample Rows</Label>
                    <div className="mt-1 max-h-48 overflow-auto rounded border">
                      <table className="w-full text-xs">
                        <thead className="bg-zinc-100 dark:bg-zinc-800">
                          <tr>
                            {validation.columns_found.slice(0, 5).map((col) => (
                              <th key={col} className="px-2 py-1 text-left font-medium">
                                {col}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {validation.sample_rows.map((row, i) => (
                            <tr key={i} className="border-t">
                              {validation.columns_found.slice(0, 5).map((col) => (
                                <td key={col} className="max-w-[200px] truncate px-2 py-1">
                                  {row[col] ?? ""}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Import Configuration */}
          {validation?.valid && !batchId && (
            <Card>
              <CardHeader>
                <CardTitle>Import Configuration</CardTitle>
                <CardDescription>
                  Configure how the {validation.total_rows.toLocaleString()} rows should be imported
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="chunk_size">Chunk Size</Label>
                    <Input
                      id="chunk_size"
                      type="number"
                      min={1}
                      max={10000}
                      value={chunkSize}
                      onChange={(e) => setChunkSize(parseInt(e.target.value, 10) || 100)}
                    />
                    <p className="text-xs text-zinc-500">Documents per database commit</p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="max_rows">Max Rows (optional)</Label>
                    <Input
                      id="max_rows"
                      type="number"
                      min={1}
                      placeholder="All rows"
                      value={maxRows}
                      onChange={(e) => setMaxRows(e.target.value)}
                    />
                    <p className="text-xs text-zinc-500">Limit for testing (empty = all)</p>
                  </div>
                </div>

                <div className="flex items-center justify-between rounded-lg border p-3">
                  <div>
                    <Label>Skip Duplicates</Label>
                    <p className="text-xs text-zinc-500">Skip rows with existing mimic_note_id</p>
                  </div>
                  <Switch checked={skipDuplicates} onCheckedChange={setSkipDuplicates} />
                </div>

                <div className="flex items-center justify-between rounded-lg border p-3">
                  <div>
                    <Label>Enqueue NLP Processing</Label>
                    <p className="text-xs text-zinc-500">Run NLP extraction on imported documents</p>
                  </div>
                  <Switch checked={enqueueProcessing} onCheckedChange={setEnqueueProcessing} />
                </div>

                <Button onClick={handleImport} disabled={isStarting} className="w-full">
                  {isStarting
                    ? "Starting Import..."
                    : `Import ${validation.total_rows.toLocaleString()} Documents`}
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Import Progress */}
          {batchId && progress && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  Import Progress
                  <Badge
                    variant={
                      isCompleted ? "default" : isFailed ? "destructive" : "secondary"
                    }
                  >
                    {progress.status}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <Progress value={progress.progress_percent} className="h-3" />
                <p className="text-sm text-zinc-600 dark:text-zinc-400">
                  {progress.progress_percent.toFixed(1)}% complete
                </p>

                <div className="grid grid-cols-4 gap-4 text-center">
                  <div className="rounded-lg bg-zinc-100 p-3 dark:bg-zinc-800">
                    <p className="text-2xl font-bold">{progress.processed.toLocaleString()}</p>
                    <p className="text-xs text-zinc-500">Processed</p>
                  </div>
                  <div className="rounded-lg bg-green-50 p-3 dark:bg-green-900/20">
                    <p className="text-2xl font-bold text-green-600">{progress.created.toLocaleString()}</p>
                    <p className="text-xs text-zinc-500">Created</p>
                  </div>
                  <div className="rounded-lg bg-yellow-50 p-3 dark:bg-yellow-900/20">
                    <p className="text-2xl font-bold text-yellow-600">{progress.skipped.toLocaleString()}</p>
                    <p className="text-xs text-zinc-500">Skipped</p>
                  </div>
                  <div className="rounded-lg bg-red-50 p-3 dark:bg-red-900/20">
                    <p className="text-2xl font-bold text-red-600">{progress.failed.toLocaleString()}</p>
                    <p className="text-xs text-zinc-500">Failed</p>
                  </div>
                </div>

                {progress.error && (
                  <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
                    {progress.error}
                  </div>
                )}

                {isCompleted && (
                  <div className="flex gap-3">
                    <Link href="/documents">
                      <Button variant="outline">View Documents</Button>
                    </Link>
                    <Link href="/mimic/validation">
                      <Button>View Validation Dashboard</Button>
                    </Link>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </main>
    </div>
  );
}
