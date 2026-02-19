"use client";

import { useState } from "react";
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
  useImportSyntheaFromPath,
  useValidateSyntheaPath,
  useSyntheaImportProgress,
} from "@/hooks/api/useSynthea";
import type { SyntheaValidateResponse } from "@/lib/api";

export default function SyntheaImportPage() {
  const [csvDir, setCsvDir] = useState("");
  const [validation, setValidation] = useState<SyntheaValidateResponse | null>(null);
  const [batchId, setBatchId] = useState<string | null>(null);

  const [chunkSize, setChunkSize] = useState(100);
  const [maxPatients, setMaxPatients] = useState<number | "">("");
  const [maxEncountersPerPatient, setMaxEncountersPerPatient] = useState<number | "">("");
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const [enqueueProcessing, setEnqueueProcessing] = useState(true);

  const validateMutation = useValidateSyntheaPath();
  const importMutation = useImportSyntheaFromPath();
  const { data: progress } = useSyntheaImportProgress(batchId);

  const handleValidate = () => {
    if (!csvDir) return;
    validateMutation.mutate(csvDir, {
      onSuccess: (data) => setValidation(data),
      onError: (err) => toast.error(`Validation failed: ${err.message}`),
    });
  };

  const handleImport = () => {
    if (!csvDir) return;
    importMutation.mutate(
      {
        csv_dir: csvDir,
        chunk_size: chunkSize,
        max_patients: maxPatients || undefined,
        max_encounters_per_patient: maxEncountersPerPatient || undefined,
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
  };

  return (
    <div className="container mx-auto p-6 max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Synthea Import</h1>
          <p className="text-muted-foreground mt-1">
            Import synthetic patient records — encounters, conditions, medications, labs composed into clinical notes
          </p>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline" size="sm">
            <Link href="/datasets">All Datasets</Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link href="/datasets/synthea/validation">Validation Dashboard</Link>
          </Button>
        </div>
      </div>

      {/* Directory Path */}
      <Card>
        <CardHeader>
          <CardTitle>Synthea Output Directory</CardTitle>
          <CardDescription>
            Point to the Synthea output/csv/ directory containing patients.csv, encounters.csv, conditions.csv, etc.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              value={csvDir}
              onChange={(e) => setCsvDir(e.target.value)}
              placeholder="/Volumes/Claude Code 4T 1225/clinical-datasets/synthea/output/csv"
            />
            <Button onClick={handleValidate} disabled={!csvDir || validateMutation.isPending}>
              {validateMutation.isPending ? "Validating..." : "Validate"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Validation Results */}
      {validation && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Directory Validation</CardTitle>
              <Badge variant={validation.valid ? "default" : "destructive"}>
                {validation.valid ? "Valid" : "Invalid"}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <div className="text-2xl font-bold">{validation.patient_count.toLocaleString()}</div>
                <div className="text-sm text-muted-foreground">Patients</div>
              </div>
              <div>
                <div className="text-2xl font-bold">{validation.encounter_count.toLocaleString()}</div>
                <div className="text-sm text-muted-foreground">Encounters</div>
              </div>
              <div>
                <div className="text-2xl font-bold">{validation.condition_count.toLocaleString()}</div>
                <div className="text-sm text-muted-foreground">Conditions</div>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <div className="text-xl font-bold">{validation.observation_count.toLocaleString()}</div>
                <div className="text-sm text-muted-foreground">Observations</div>
              </div>
              <div>
                <div className="text-xl font-bold">{validation.medication_count.toLocaleString()}</div>
                <div className="text-sm text-muted-foreground">Medications</div>
              </div>
              <div>
                <div className="text-xl font-bold">{validation.procedure_count.toLocaleString()}</div>
                <div className="text-sm text-muted-foreground">Procedures</div>
              </div>
            </div>

            {validation.files_found.length > 0 && (
              <div>
                <Label className="text-xs text-muted-foreground">Files Found</Label>
                <div className="flex flex-wrap gap-1 mt-1">
                  {validation.files_found.map((f) => (
                    <Badge key={f} variant="outline" className="text-xs">{f}</Badge>
                  ))}
                </div>
              </div>
            )}

            {validation.sample_patient && (
              <div className="bg-muted rounded p-3">
                <Label className="text-xs text-muted-foreground">Sample Patient</Label>
                <div className="grid grid-cols-4 gap-2 mt-1 text-sm">
                  <div><span className="text-muted-foreground">Name:</span> {validation.sample_patient.name}</div>
                  <div><span className="text-muted-foreground">DOB:</span> {validation.sample_patient.birthdate}</div>
                  <div><span className="text-muted-foreground">Gender:</span> {validation.sample_patient.gender}</div>
                  <div><span className="text-muted-foreground">City:</span> {validation.sample_patient.city}</div>
                </div>
              </div>
            )}

            {validation.errors.length > 0 && (
              <div className="bg-destructive/10 rounded p-3">
                <p className="text-sm font-medium text-destructive">Errors:</p>
                {validation.errors.map((err, i) => (
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
            <CardDescription>
              Each encounter is composed into a clinical note with patient demographics, conditions, observations, medications, and procedures
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
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
                <Label>Max Patients (empty = all)</Label>
                <Input
                  type="number"
                  value={maxPatients}
                  onChange={(e) => setMaxPatients(e.target.value ? Number(e.target.value) : "")}
                  placeholder="All"
                  min={1}
                />
              </div>
              <div className="space-y-2">
                <Label>Max Encounters/Patient</Label>
                <Input
                  type="number"
                  value={maxEncountersPerPatient}
                  onChange={(e) => setMaxEncountersPerPatient(e.target.value ? Number(e.target.value) : "")}
                  placeholder="All"
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
              disabled={importMutation.isPending}
              className="w-full"
              size="lg"
            >
              {importMutation.isPending
                ? "Starting Import..."
                : `Import ${validation.encounter_count.toLocaleString()} Encounters from ${validation.patient_count.toLocaleString()} Patients`}
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
                  <Link href="/datasets/synthea/validation">View Validation Dashboard</Link>
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
