"use client";

import { useState, useEffect, useCallback } from "react";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Switch } from "@/components/ui/switch";
import {
  generateSyntheticData,
  getSyntheticJobStatus,
  getSyntheticTemplates,
  getSyntheticStats,
  previewSyntheticData,
  downloadSyntheticData,
  SyntheticTemplate,
  SyntheticJob,
  SyntheticStats,
  SyntheticGenerateRequest,
} from "@/lib/api";

const OUTPUT_FORMATS = [
  { value: "fhir_json", label: "FHIR R4 JSON" },
  { value: "csv", label: "CSV" },
  { value: "omop", label: "OMOP CDM JSON" },
];

const EPSILON_PRESETS = [
  { value: 0.1, label: "Very Private", description: "Strong privacy, lower utility" },
  { value: 0.5, label: "Private", description: "Good privacy, moderate utility" },
  { value: 1.0, label: "Balanced", description: "Balanced privacy and utility" },
  { value: 2.0, label: "Utility-Focused", description: "Lower privacy, high utility" },
  { value: 5.0, label: "Minimal Privacy", description: "Minimal privacy protection" },
];

export default function SyntheticDataPage() {
  // State
  const [templates, setTemplates] = useState<SyntheticTemplate[]>([]);
  const [stats, setStats] = useState<SyntheticStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Configuration state
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [patientCount, setPatientCount] = useState(100);
  const [outputFormat, setOutputFormat] = useState("fhir_json");

  // Demographics
  const [ageMin, setAgeMin] = useState(0);
  const [ageMax, setAgeMax] = useState(100);
  const [ageMean, setAgeMean] = useState(45);
  const [ageStd, setAgeStd] = useState(20);
  const [maleRatio, setMaleRatio] = useState(0.49);

  // Privacy
  const [enablePrivacy, setEnablePrivacy] = useState(false);
  const [epsilon, setEpsilon] = useState(1.0);
  const [kAnonymity, setKAnonymity] = useState(5);
  const [lDiversity, setLDiversity] = useState(2);

  // Job tracking
  const [currentJob, setCurrentJob] = useState<SyntheticJob | null>(null);
  const [previewData, setPreviewData] = useState<any[] | null>(null);

  // Fetch initial data
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [templatesData, statsData] = await Promise.all([
        getSyntheticTemplates(),
        getSyntheticStats(),
      ]);
      setTemplates(templatesData.templates);
      setStats(statsData);
      setError(null);
    } catch (err) {
      console.error("Failed to fetch data:", err);
      setError("Failed to load synthetic data configuration. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Poll job status
  useEffect(() => {
    if (!currentJob || currentJob.status === "completed" || currentJob.status === "failed") {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const job = await getSyntheticJobStatus(currentJob.job_id);
        setCurrentJob(job);

        if (job.status === "completed" || job.status === "failed") {
          setGenerating(false);
          fetchData(); // Refresh stats
        }
      } catch (err) {
        console.error("Failed to poll job status:", err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [currentJob, fetchData]);

  // Handle generation
  const handleGenerate = async () => {
    try {
      setGenerating(true);
      setError(null);

      const request: SyntheticGenerateRequest = {
        patient_count: patientCount,
        output_format: outputFormat,
      };

      // Add template if selected
      if (selectedTemplate) {
        request.template_id = selectedTemplate;
      } else {
        // Add custom configuration
        request.age_distribution = {
          min_age: ageMin,
          max_age: ageMax,
          mean_age: ageMean,
          std_dev: ageStd,
        };
        request.gender_distribution = {
          male_ratio: maleRatio,
          female_ratio: 1.0 - maleRatio - 0.01,
          other_ratio: 0.01,
        };
      }

      // Add privacy config if enabled
      if (enablePrivacy) {
        request.privacy_config = {
          epsilon,
          delta: 1e-5,
          k_anonymity: kAnonymity,
          l_diversity: lDiversity,
          t_closeness: 0.3,
        };
      }

      const response = await generateSyntheticData(request);
      const job = await getSyntheticJobStatus(response.job_id);
      setCurrentJob(job);
    } catch (err) {
      console.error("Failed to start generation:", err);
      setError("Failed to start generation. Please try again.");
      setGenerating(false);
    }
  };

  // Handle preview
  const handlePreview = async () => {
    try {
      const data = await previewSyntheticData(
        Math.min(patientCount, 10),
        selectedTemplate || undefined
      );
      setPreviewData(data.preview);
    } catch (err) {
      console.error("Failed to generate preview:", err);
      setError("Failed to generate preview.");
    }
  };

  // Handle download
  const handleDownload = async (format: string) => {
    if (!currentJob || currentJob.status !== "completed") return;

    try {
      await downloadSyntheticData(currentJob.job_id, format);
    } catch (err) {
      console.error("Failed to download:", err);
      setError("Failed to download generated data.");
    }
  };

  // Calculate privacy score visualization
  const getPrivacyLevel = (eps: number) => {
    if (eps <= 0.5) return { level: "High", color: "text-green-600" };
    if (eps <= 1.0) return { level: "Medium", color: "text-yellow-600" };
    if (eps <= 2.0) return { level: "Low", color: "text-orange-600" };
    return { level: "Minimal", color: "text-red-600" };
  };

  const getUtilityLevel = (eps: number) => {
    if (eps >= 2.0) return { level: "High", color: "text-green-600" };
    if (eps >= 1.0) return { level: "Medium", color: "text-yellow-600" };
    if (eps >= 0.5) return { level: "Low", color: "text-orange-600" };
    return { level: "Minimal", color: "text-red-600" };
  };

  const privacyLevel = getPrivacyLevel(epsilon);
  const utilityLevel = getUtilityLevel(epsilon);

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900 flex items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-300 border-t-zinc-900" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                href="/"
                className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
              >
                &larr; Home
              </Link>
              <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                Synthetic Data Generator
              </h1>
            </div>
            {stats && (
              <div className="text-sm text-zinc-500">
                {stats.total_patients_generated.toLocaleString()} patients generated
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {error && (
          <div className="mb-6 rounded-lg bg-red-50 p-4 text-red-800 dark:bg-red-900/20 dark:text-red-200">
            {error}
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Configuration Panel */}
          <div className="lg:col-span-2 space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Generation Configuration</CardTitle>
                <CardDescription>
                  Configure synthetic patient population parameters
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Tabs defaultValue="basic">
                  <TabsList className="grid w-full grid-cols-3">
                    <TabsTrigger value="basic">Basic</TabsTrigger>
                    <TabsTrigger value="demographics">Demographics</TabsTrigger>
                    <TabsTrigger value="privacy">Privacy</TabsTrigger>
                  </TabsList>

                  {/* Basic Tab */}
                  <TabsContent value="basic" className="space-y-6 pt-4">
                    <div className="space-y-4">
                      <div>
                        <Label htmlFor="template">Template</Label>
                        <Select
                          value={selectedTemplate || "custom"}
                          onValueChange={(v) =>
                            setSelectedTemplate(v === "custom" ? null : v)
                          }
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Select template" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="custom">Custom Configuration</SelectItem>
                            {templates.map((t) => (
                              <SelectItem key={t.template_id} value={t.template_id}>
                                {t.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        {selectedTemplate && (
                          <p className="mt-1 text-sm text-zinc-500">
                            {templates.find((t) => t.template_id === selectedTemplate)
                              ?.description}
                          </p>
                        )}
                      </div>

                      <div>
                        <Label htmlFor="patientCount">
                          Patient Count: {patientCount.toLocaleString()}
                        </Label>
                        <Slider
                          id="patientCount"
                          min={10}
                          max={10000}
                          step={10}
                          value={[patientCount]}
                          onValueChange={([v]) => setPatientCount(v)}
                          className="mt-2"
                        />
                        <div className="flex justify-between text-xs text-zinc-500 mt-1">
                          <span>10</span>
                          <span>10,000</span>
                        </div>
                      </div>

                      <div>
                        <Label htmlFor="format">Output Format</Label>
                        <Select value={outputFormat} onValueChange={setOutputFormat}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {OUTPUT_FORMATS.map((f) => (
                              <SelectItem key={f.value} value={f.value}>
                                {f.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </TabsContent>

                  {/* Demographics Tab */}
                  <TabsContent value="demographics" className="space-y-6 pt-4">
                    {selectedTemplate ? (
                      <p className="text-zinc-500">
                        Demographics are configured by the selected template.
                        Select &ldquo;Custom Configuration&rdquo; to customize.
                      </p>
                    ) : (
                      <div className="space-y-6">
                        <div>
                          <Label>
                            Age Range: {ageMin} - {ageMax} years
                          </Label>
                          <div className="flex gap-4 mt-2">
                            <div className="flex-1">
                              <Input
                                type="number"
                                min={0}
                                max={120}
                                value={ageMin}
                                onChange={(e) => setAgeMin(parseInt(e.target.value) || 0)}
                                placeholder="Min age"
                              />
                            </div>
                            <div className="flex-1">
                              <Input
                                type="number"
                                min={0}
                                max={120}
                                value={ageMax}
                                onChange={(e) => setAgeMax(parseInt(e.target.value) || 100)}
                                placeholder="Max age"
                              />
                            </div>
                          </div>
                        </div>

                        <div>
                          <Label>Mean Age: {ageMean} years</Label>
                          <Slider
                            min={0}
                            max={100}
                            step={1}
                            value={[ageMean]}
                            onValueChange={([v]) => setAgeMean(v)}
                            className="mt-2"
                          />
                        </div>

                        <div>
                          <Label>Age Standard Deviation: {ageStd}</Label>
                          <Slider
                            min={5}
                            max={40}
                            step={1}
                            value={[ageStd]}
                            onValueChange={([v]) => setAgeStd(v)}
                            className="mt-2"
                          />
                        </div>

                        <div>
                          <Label>Male Ratio: {(maleRatio * 100).toFixed(0)}%</Label>
                          <Slider
                            min={0}
                            max={100}
                            step={1}
                            value={[maleRatio * 100]}
                            onValueChange={([v]) => setMaleRatio(v / 100)}
                            className="mt-2"
                          />
                          <div className="flex justify-between text-xs text-zinc-500 mt-1">
                            <span>0% Male</span>
                            <span>50%</span>
                            <span>100% Male</span>
                          </div>
                        </div>
                      </div>
                    )}
                  </TabsContent>

                  {/* Privacy Tab */}
                  <TabsContent value="privacy" className="space-y-6 pt-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <Label htmlFor="enablePrivacy">
                          Enable Differential Privacy
                        </Label>
                        <p className="text-sm text-zinc-500">
                          Add mathematical privacy guarantees to generated data
                        </p>
                      </div>
                      <Switch
                        id="enablePrivacy"
                        checked={enablePrivacy}
                        onCheckedChange={setEnablePrivacy}
                      />
                    </div>

                    {enablePrivacy && (
                      <>
                        <div>
                          <Label>
                            Epsilon (Privacy Budget): {epsilon.toFixed(2)}
                          </Label>
                          <Slider
                            min={0.1}
                            max={5}
                            step={0.1}
                            value={[epsilon]}
                            onValueChange={([v]) => setEpsilon(v)}
                            className="mt-2"
                          />
                          <div className="flex justify-between text-xs mt-1">
                            <span className="text-green-600">More Private</span>
                            <span className="text-red-600">Less Private</span>
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <Label>K-Anonymity: {kAnonymity}</Label>
                            <Slider
                              min={2}
                              max={20}
                              step={1}
                              value={[kAnonymity]}
                              onValueChange={([v]) => setKAnonymity(v)}
                              className="mt-2"
                            />
                          </div>
                          <div>
                            <Label>L-Diversity: {lDiversity}</Label>
                            <Slider
                              min={1}
                              max={10}
                              step={1}
                              value={[lDiversity]}
                              onValueChange={([v]) => setLDiversity(v)}
                              className="mt-2"
                            />
                          </div>
                        </div>

                        {/* Privacy vs Utility Visualization */}
                        <Card className="bg-zinc-50 dark:bg-zinc-800">
                          <CardContent className="pt-4">
                            <div className="flex justify-between mb-4">
                              <div className="text-center">
                                <div className={`text-2xl font-bold ${privacyLevel.color}`}>
                                  {privacyLevel.level}
                                </div>
                                <div className="text-sm text-zinc-500">Privacy</div>
                              </div>
                              <div className="text-center">
                                <div className={`text-2xl font-bold ${utilityLevel.color}`}>
                                  {utilityLevel.level}
                                </div>
                                <div className="text-sm text-zinc-500">Utility</div>
                              </div>
                            </div>
                            <div className="relative h-4 bg-gradient-to-r from-green-500 via-yellow-500 to-red-500 rounded-full">
                              <div
                                className="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-white rounded-full border-2 border-zinc-900 shadow"
                                style={{
                                  left: `${Math.min(100, (epsilon / 5) * 100)}%`,
                                  transform: "translate(-50%, -50%)",
                                }}
                              />
                            </div>
                            <div className="flex justify-between text-xs text-zinc-500 mt-1">
                              <span>High Privacy</span>
                              <span>High Utility</span>
                            </div>
                          </CardContent>
                        </Card>

                        <div className="text-sm text-zinc-500">
                          <p className="font-medium mb-2">Preset Configurations:</p>
                          <div className="flex flex-wrap gap-2">
                            {EPSILON_PRESETS.map((preset) => (
                              <TooltipProvider key={preset.value}>
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <Button
                                      variant={epsilon === preset.value ? "default" : "outline"}
                                      size="sm"
                                      onClick={() => setEpsilon(preset.value)}
                                    >
                                      {preset.label}
                                    </Button>
                                  </TooltipTrigger>
                                  <TooltipContent>
                                    <p>{preset.description}</p>
                                  </TooltipContent>
                                </Tooltip>
                              </TooltipProvider>
                            ))}
                          </div>
                        </div>
                      </>
                    )}
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>

            {/* Preview Section */}
            {previewData && previewData.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Data Preview</CardTitle>
                  <CardDescription>
                    Sample of {previewData.length} synthetic patients
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left py-2 px-2">Patient ID</th>
                          <th className="text-left py-2 px-2">Gender</th>
                          <th className="text-left py-2 px-2">Age</th>
                          <th className="text-left py-2 px-2">Race</th>
                          <th className="text-left py-2 px-2">Conditions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {previewData.map((p: any) => (
                          <tr key={p.patient_id} className="border-b last:border-0">
                            <td className="py-2 px-2 font-mono text-xs">
                              {p.patient_id}
                            </td>
                            <td className="py-2 px-2 capitalize">{p.gender}</td>
                            <td className="py-2 px-2">{p.age}</td>
                            <td className="py-2 px-2 capitalize">
                              {p.race.replace("_", " ")}
                            </td>
                            <td className="py-2 px-2">
                              <div className="flex flex-wrap gap-1">
                                {p.conditions.slice(0, 2).map((c: any, i: number) => (
                                  <Badge key={i} variant="secondary" className="text-xs">
                                    {c.name.length > 20
                                      ? c.name.slice(0, 20) + "..."
                                      : c.name}
                                  </Badge>
                                ))}
                                {p.conditions.length > 2 && (
                                  <Badge variant="outline" className="text-xs">
                                    +{p.conditions.length - 2}
                                  </Badge>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Action Panel */}
          <div className="space-y-6">
            {/* Generate Card */}
            <Card>
              <CardHeader>
                <CardTitle>Generate</CardTitle>
                <CardDescription>
                  Start synthetic data generation
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-2">
                  <Button
                    className="flex-1"
                    onClick={handleGenerate}
                    disabled={generating}
                  >
                    {generating ? "Generating..." : "Generate Data"}
                  </Button>
                  <Button variant="outline" onClick={handlePreview}>
                    Preview
                  </Button>
                </div>

                {/* Job Progress */}
                {currentJob && (
                  <div className="space-y-2 pt-4 border-t">
                    <div className="flex justify-between text-sm">
                      <span>Job: {currentJob.job_id.slice(0, 12)}...</span>
                      <Badge
                        className={
                          currentJob.status === "completed"
                            ? "bg-green-500"
                            : currentJob.status === "failed"
                            ? "bg-red-500"
                            : currentJob.status === "running"
                            ? "bg-blue-500"
                            : "bg-yellow-500"
                        }
                      >
                        {currentJob.status.toUpperCase()}
                      </Badge>
                    </div>
                    <Progress value={currentJob.progress_percent} />
                    <p className="text-sm text-zinc-500">
                      {currentJob.patients_generated.toLocaleString()} patients generated
                    </p>

                    {currentJob.status === "completed" && (
                      <div className="flex gap-2 pt-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDownload("fhir_json")}
                        >
                          FHIR JSON
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDownload("csv")}
                        >
                          CSV
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDownload("omop")}
                        >
                          OMOP
                        </Button>
                      </div>
                    )}

                    {currentJob.error && (
                      <p className="text-sm text-red-500">{currentJob.error}</p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Templates Card */}
            <Card>
              <CardHeader>
                <CardTitle>Templates</CardTitle>
                <CardDescription>Pre-configured generation templates</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {templates.map((t) => (
                    <div
                      key={t.template_id}
                      className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                        selectedTemplate === t.template_id
                          ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
                          : "hover:border-zinc-400"
                      }`}
                      onClick={() => setSelectedTemplate(t.template_id)}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{t.name}</span>
                        {t.has_privacy_config && (
                          <Badge variant="outline" className="text-xs">
                            Privacy
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm text-zinc-500 mt-1">{t.description}</p>
                      <p className="text-xs text-zinc-400 mt-1">
                        Default: {t.patient_count.toLocaleString()} patients
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Stats Card */}
            {stats && (
              <Card>
                <CardHeader>
                  <CardTitle>Statistics</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-2xl font-bold">
                        {stats.total_patients_generated.toLocaleString()}
                      </div>
                      <div className="text-sm text-zinc-500">Total Generated</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold">{stats.completed_jobs}</div>
                      <div className="text-sm text-zinc-500">Completed Jobs</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold">{stats.default_conditions}</div>
                      <div className="text-sm text-zinc-500">Conditions</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold">{stats.default_medications}</div>
                      <div className="text-sm text-zinc-500">Medications</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Info Card */}
            <Card>
              <CardHeader>
                <CardTitle>About</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-zinc-500 space-y-2">
                <p>
                  Generate synthetic patient populations with realistic clinical
                  data including conditions, medications, and lab values.
                </p>
                <p>
                  Data follows Synthea-style generation patterns with configurable
                  demographics and disease prevalence.
                </p>
                <p>
                  Enable differential privacy to add mathematical privacy guarantees
                  suitable for research and development.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}
