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
  useUploadMtsamplesCsv,
  useValidateMtsamplesCsv,
  useImportMtsamplesFromPath,
  useValidateMtsamplesPath,
  useMtsamplesImportProgress,
} from "@/hooks/api/useMtsamples";
import type { MtsamplesValidateResponse } from "@/lib/api";

type ImportMode = "upload" | "server-path";

export default function MtsamplesImportPage() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<ImportMode>("server-path");
  const [isDragActive, setIsDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [serverPath, setServerPath] = useState("");
  const [validation, setValidation] = useState<MtsamplesValidateResponse | null>(null);
  const [batchId, setBatchId] = useState<string | null>(null);

  const [chunkSize, setChunkSize] = useState(100);
  const [maxRows, setMaxRows] = useState<number | "">("");
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const [enqueueProcessing, setEnqueueProcessing] = useState(true);

  const uploadMutation = useUploadMtsamplesCsv();
  const validateMutation = useValidateMtsamplesCsv();
  const importPathMutation = useImportMtsamplesFromPath();
  const validatePathMutation = useValidateMtsamplesPath();
  const { data: progress } = useMtsamplesImportProgress(batchId);

  const handleFileDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragActive(false);
    const file = e.dataTransfer.files[0];
    if (file?.name.endsWith(".csv")) {
      setSelectedFile(file);
      setValidation(null);
    } else {
      toast.error("Please drop a CSV file");
    }
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setValidation(null);
    }
  }, []);

  const handleValidate = () => {
    if (mode === "upload" && selectedFile) {
      validateMutation.mutate(selectedFile, {
        onSuccess: (data) => setValidation(data),
        onError: (err) => toast.error(`Validation failed: ${err.message}`),
      });
    } else if (mode === "server-path" && serverPath) {
      validatePathMutation.mutate(serverPath, {
        onSuccess: (data) => setValidation(data),
        onError: (err) => toast.error(`Validation failed: ${err.message}`),
      });
    }
  };

  const handleImport = () => {
    if (mode === "upload" && selectedFile) {
      uploadMutation.mutate(
        {
          file: selectedFile,
          chunkSize,
          maxRows: maxRows || undefined,
          skipDuplicates,
          enqueueProcessing,
        },
        {
          onSuccess: (data) => {
            setBatchId(data.batch_id);
            toast.success(data.message);
          },
          onError: (err) => toast.error(`Import failed: ${err.message}`),
        }
      );
    } else if (mode === "server-path" && serverPath) {
      importPathMutation.mutate(
        {
          file_path: serverPath,
          chunk_size: chunkSize,
          max_rows: maxRows || undefined,
          skip_duplicates: skipDuplicates,
          enqueue_processing: enqueueProcessing,
        },
        {
          onSuccess: (data) => {
            setBatchId(data.batch_id);
            toast.success(data.message);
          },
          onError: (err) => toast.error(`Import failed: ${err.message}`),
        }
      );
    }
  };

  const isValidating = validateMutation.isPending || validatePathMutation.isPending;
  const isImporting = uploadMutation.isPending || importPathMutation.isPending;

  return (
    <div className="container mx-auto p-6 max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">MTSamples Import</h1>
          <p className="text-muted-foreground mt-1">
            Import 5K medical transcriptions across 40+ specialties for NLP pipeline validation
          </p>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline" size="sm">
            <Link href="/datasets">All Datasets</Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link href="/datasets/mtsamples/validation">Validation Dashboard</Link>
          </Button>
        </div>
      </div>

      {/* Mode Selector */}
      <Card>
        <CardHeader>
          <CardTitle>Import Source</CardTitle>
          <CardDescription>Choose how to provide the MTSamples CSV</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-4">
            <Button
              variant={mode === "server-path" ? "default" : "outline"}
              onClick={() => { setMode("server-path"); setValidation(null); }}
            >
              Server Path
            </Button>
            <Button
              variant={mode === "upload" ? "default" : "outline"}
              onClick={() => { setMode("upload"); setValidation(null); }}
            >
              File Upload
            </Button>
          </div>

          {mode === "server-path" ? (
            <div className="space-y-2">
              <Label>CSV file path on server</Label>
              <div className="flex gap-2">
                <Input
                  value={serverPath}
                  onChange={(e) => setServerPath(e.target.value)}
                  placeholder="/Volumes/Claude Code 4T 1225/clinical-datasets/mtsamples/mtsamples.csv"
                />
                <Button onClick={handleValidate} disabled={!serverPath || isValidating}>
                  {isValidating ? "Validating..." : "Validate"}
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              <div
                className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                  isDragActive ? "border-primary bg-primary/5" : "border-muted-foreground/25 hover:border-primary/50"
                }`}
                onDrop={handleFileDrop}
                onDragOver={(e) => { e.preventDefault(); setIsDragActive(true); }}
                onDragLeave={() => setIsDragActive(false)}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={handleFileSelect}
                />
                {selectedFile ? (
                  <div>
                    <p className="font-medium">{selectedFile.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {(selectedFile.size / 1024 / 1024).toFixed(1)} MB
                    </p>
                  </div>
                ) : (
                  <p className="text-muted-foreground">
                    Drop MTSamples CSV here or click to browse
                  </p>
                )}
              </div>
              {selectedFile && !validation && (
                <Button onClick={handleValidate} disabled={isValidating} className="w-full">
                  {isValidating ? "Validating..." : "Validate CSV"}
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Validation Results */}
      {validation && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Validation Results</CardTitle>
              <Badge variant={validation.valid ? "default" : "destructive"}>
                {validation.valid ? "Valid" : "Invalid"}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <div className="text-2xl font-bold">{validation.total_rows.toLocaleString()}</div>
                <div className="text-sm text-muted-foreground">Total Transcriptions</div>
              </div>
              <div>
                <div className="text-2xl font-bold">{validation.columns_found.length}</div>
                <div className="text-sm text-muted-foreground">Columns Found</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-green-500">{validation.columns_missing.length === 0 ? "OK" : validation.columns_missing.length}</div>
                <div className="text-sm text-muted-foreground">Missing Columns</div>
              </div>
            </div>
            {validation.columns_found.length > 0 && (
              <div>
                <Label className="text-xs text-muted-foreground">Columns</Label>
                <div className="flex flex-wrap gap-1 mt-1">
                  {validation.columns_found.map((col) => (
                    <Badge key={col} variant="outline" className="text-xs">{col}</Badge>
                  ))}
                </div>
              </div>
            )}
            {validation.errors.length > 0 && (
              <div className="bg-destructive/10 rounded p-3">
                <p className="text-sm font-medium text-destructive">Errors:</p>
                {validation.errors.slice(0, 5).map((err, i) => (
                  <p key={i} className="text-xs text-destructive">{err}</p>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Import Config */}
      {validation?.valid && !batchId && (
        <Card>
          <CardHeader>
            <CardTitle>Import Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Chunk Size</Label>
                <Input
                  type="number"
                  value={chunkSize}
                  onChange={(e) => setChunkSize(Number(e.target.value) || 100)}
                  min={1}
                  max={10000}
                />
              </div>
              <div className="space-y-2">
                <Label>Max Rows (empty = all)</Label>
                <Input
                  type="number"
                  value={maxRows}
                  onChange={(e) => setMaxRows(e.target.value ? Number(e.target.value) : "")}
                  placeholder="All rows"
                  min={1}
                />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <Label>Skip Duplicates</Label>
              <Switch checked={skipDuplicates} onCheckedChange={setSkipDuplicates} />
            </div>
            <div className="flex items-center justify-between">
              <Label>Enqueue NLP Processing</Label>
              <Switch checked={enqueueProcessing} onCheckedChange={setEnqueueProcessing} />
            </div>
            <Button
              onClick={handleImport}
              disabled={isImporting}
              className="w-full"
              size="lg"
            >
              {isImporting ? "Starting Import..." : `Import ${validation.total_rows.toLocaleString()} Transcriptions`}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Progress */}
      {batchId && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Import Progress</CardTitle>
              <Badge variant={
                progress?.status === "completed" ? "default" :
                progress?.status === "failed" ? "destructive" : "secondary"
              }>
                {progress?.status ?? "starting"}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <Progress value={progress?.progress_percent ?? 0} />
            <div className="grid grid-cols-4 gap-4 text-center">
              <div>
                <div className="text-xl font-bold">{progress?.processed ?? 0}</div>
                <div className="text-xs text-muted-foreground">Processed</div>
              </div>
              <div>
                <div className="text-xl font-bold text-green-500">{progress?.created ?? 0}</div>
                <div className="text-xs text-muted-foreground">Created</div>
              </div>
              <div>
                <div className="text-xl font-bold text-yellow-500">{progress?.skipped ?? 0}</div>
                <div className="text-xs text-muted-foreground">Skipped</div>
              </div>
              <div>
                <div className="text-xl font-bold text-red-500">{progress?.failed ?? 0}</div>
                <div className="text-xs text-muted-foreground">Failed</div>
              </div>
            </div>
            {progress?.error && (
              <div className="bg-destructive/10 rounded p-3">
                <p className="text-sm text-destructive">{progress.error}</p>
              </div>
            )}
            {progress?.status === "completed" && (
              <div className="flex gap-2">
                <Button asChild className="flex-1">
                  <Link href="/datasets/mtsamples/validation">View Validation Dashboard</Link>
                </Button>
                <Button asChild variant="outline" className="flex-1">
                  <Link href="/documents">View Documents</Link>
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
