"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle,
  Database,
  Eye,
  EyeOff,
  FileText,
  Loader2,
  Server,
  Zap,
} from "lucide-react";
import {
  useCreateSource,
  useTestSourceConnection,
  useSourcePreview,
} from "@/hooks/use-api";
import type { CreateSourceRequest, Source } from "@/lib/api";

// =============================================================================
// Types
// =============================================================================

type SourceType = "fhir" | "hl7v2" | "ccda" | "csv" | "database";

interface WizardStep {
  id: number;
  title: string;
  description: string;
}

const WIZARD_STEPS: WizardStep[] = [
  { id: 1, title: "Select Type", description: "Choose your data source type" },
  { id: 2, title: "Connection", description: "Configure connection parameters" },
  { id: 3, title: "Credentials", description: "Set up authentication" },
  { id: 4, title: "Test & Preview", description: "Verify connection and preview data" },
];

// =============================================================================
// Source Type Configuration
// =============================================================================

const SOURCE_TYPES: Record<
  SourceType,
  {
    icon: React.ReactNode;
    label: string;
    description: string;
    color: string;
    connectionFields: { key: string; label: string; hint: string; type?: string; required?: boolean }[];
    credentialFields: { key: string; label: string; hint: string; masked?: boolean }[];
  }
> = {
  fhir: {
    icon: <Server className="h-6 w-6" />,
    label: "FHIR R4",
    description: "Connect to FHIR R4 compliant servers to extract clinical data",
    color: "text-blue-500 bg-blue-500/10",
    connectionFields: [
      { key: "host", label: "Server URL", hint: "e.g., fhir.example.com", required: true },
      { key: "port", label: "Port", hint: "Default: 443", type: "number" },
      { key: "path", label: "Base Path", hint: "e.g., /fhir" },
    ],
    credentialFields: [
      { key: "auth_token", label: "Bearer Token", hint: "OAuth2 access token", masked: true },
      { key: "client_id", label: "Client ID", hint: "OAuth2 client ID" },
      { key: "client_secret", label: "Client Secret", hint: "OAuth2 client secret", masked: true },
    ],
  },
  hl7v2: {
    icon: <FileText className="h-6 w-6" />,
    label: "HL7 v2 Messages",
    description: "Parse HL7 v2.x messages from a directory",
    color: "text-purple-500 bg-purple-500/10",
    connectionFields: [
      { key: "path", label: "Messages Directory", hint: "e.g., /data/hl7/messages", required: true },
    ],
    credentialFields: [],
  },
  ccda: {
    icon: <FileText className="h-6 w-6" />,
    label: "C-CDA Documents",
    description: "Import clinical data from C-CDA/CCD XML documents",
    color: "text-green-500 bg-green-500/10",
    connectionFields: [
      { key: "path", label: "Documents Directory", hint: "e.g., /data/ccda/documents", required: true },
    ],
    credentialFields: [],
  },
  csv: {
    icon: <FileText className="h-6 w-6" />,
    label: "CSV Files",
    description: "Import clinical data from CSV files in a directory",
    color: "text-orange-500 bg-orange-500/10",
    connectionFields: [
      { key: "path", label: "CSV Directory", hint: "e.g., /data/csv/exports", required: true },
    ],
    credentialFields: [],
  },
  database: {
    icon: <Database className="h-6 w-6" />,
    label: "Database",
    description: "Connect directly to a source database",
    color: "text-indigo-500 bg-indigo-500/10",
    connectionFields: [
      { key: "host", label: "Host", hint: "e.g., db.example.com", required: true },
      { key: "port", label: "Port", hint: "e.g., 5432", type: "number", required: true },
      { key: "database", label: "Database Name", hint: "e.g., clinical_data", required: true },
      { key: "schema", label: "Schema", hint: "e.g., public" },
    ],
    credentialFields: [
      { key: "username", label: "Username", hint: "Database username", masked: false },
      { key: "password", label: "Password", hint: "Database password", masked: true },
    ],
  },
};

// =============================================================================
// Step 1: Type Selection
// =============================================================================

interface TypeSelectionStepProps {
  selectedType: SourceType | null;
  onSelectType: (type: SourceType) => void;
}

function TypeSelectionStep({ selectedType, onSelectType }: TypeSelectionStepProps) {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium">Select Data Source Type</h3>
        <p className="text-sm text-muted-foreground">
          Choose the type of clinical data source you want to connect to.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {(Object.entries(SOURCE_TYPES) as [SourceType, typeof SOURCE_TYPES[SourceType]][]).map(
          ([type, config]) => (
            <button
              key={type}
              type="button"
              onClick={() => onSelectType(type)}
              className={`flex flex-col items-start gap-3 rounded-lg border p-4 text-left transition-all hover:border-primary hover:bg-muted/50 ${
                selectedType === type
                  ? "border-primary bg-primary/5 ring-2 ring-primary ring-offset-2"
                  : "border-border"
              }`}
            >
              <div className={`rounded-lg p-2 ${config.color}`}>{config.icon}</div>
              <div>
                <p className="font-medium">{config.label}</p>
                <p className="text-sm text-muted-foreground">{config.description}</p>
              </div>
              {selectedType === type && (
                <Badge variant="default" className="absolute top-2 right-2">
                  Selected
                </Badge>
              )}
            </button>
          )
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Step 2: Connection Parameters
// =============================================================================

interface ConnectionStepProps {
  sourceType: SourceType;
  name: string;
  description: string;
  connectionParams: Record<string, string>;
  sslEnabled: boolean;
  onNameChange: (name: string) => void;
  onDescriptionChange: (desc: string) => void;
  onConnectionParamChange: (key: string, value: string) => void;
  onSslChange: (enabled: boolean) => void;
}

function ConnectionStep({
  sourceType,
  name,
  description,
  connectionParams,
  sslEnabled,
  onNameChange,
  onDescriptionChange,
  onConnectionParamChange,
  onSslChange,
}: ConnectionStepProps) {
  const config = SOURCE_TYPES[sourceType];

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium">Connection Parameters</h3>
        <p className="text-sm text-muted-foreground">
          Configure how to connect to your {config.label} data source.
        </p>
      </div>

      {/* Basic Info */}
      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="name">
            Source Name <span className="text-destructive">*</span>
          </Label>
          <Input
            id="name"
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
            placeholder="e.g., Hospital EHR System"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="description">Description</Label>
          <Textarea
            id="description"
            value={description}
            onChange={(e) => onDescriptionChange(e.target.value)}
            placeholder="Optional description of this data source"
            rows={2}
          />
        </div>
      </div>

      {/* Connection Fields */}
      <div className="space-y-4">
        <h4 className="font-medium">Connection Settings</h4>

        {config.connectionFields.map((field) => (
          <div key={field.key} className="space-y-2">
            <Label htmlFor={field.key}>
              {field.label}
              {field.required && <span className="text-destructive"> *</span>}
            </Label>
            <Input
              id={field.key}
              type={field.type || "text"}
              value={connectionParams[field.key] || ""}
              onChange={(e) => onConnectionParamChange(field.key, e.target.value)}
              placeholder={field.hint}
            />
          </div>
        ))}

        {/* SSL Toggle for network sources */}
        {(sourceType === "fhir" || sourceType === "database") && (
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <Label htmlFor="ssl">Enable SSL/TLS</Label>
              <p className="text-sm text-muted-foreground">
                Use encrypted connection (recommended)
              </p>
            </div>
            <Switch
              id="ssl"
              checked={sslEnabled}
              onCheckedChange={onSslChange}
            />
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Step 3: Credentials
// =============================================================================

interface CredentialsStepProps {
  sourceType: SourceType;
  credentials: Record<string, string>;
  onCredentialChange: (key: string, value: string) => void;
}

function CredentialsStep({ sourceType, credentials, onCredentialChange }: CredentialsStepProps) {
  const config = SOURCE_TYPES[sourceType];
  const [showMasked, setShowMasked] = useState<Record<string, boolean>>({});

  const toggleMask = (key: string) => {
    setShowMasked((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  if (config.credentialFields.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h3 className="text-lg font-medium">Authentication</h3>
          <p className="text-sm text-muted-foreground">
            Configure authentication credentials for your data source.
          </p>
        </div>

        <div className="rounded-lg border border-dashed p-8 text-center">
          <CheckCircle className="mx-auto h-12 w-12 text-green-500" />
          <h4 className="mt-4 font-medium">No Authentication Required</h4>
          <p className="mt-2 text-sm text-muted-foreground">
            {config.label} sources access local files and don&apos;t require credentials.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium">Authentication</h3>
        <p className="text-sm text-muted-foreground">
          Configure authentication credentials for your data source.
          Credentials are encrypted before storage.
        </p>
      </div>

      <div className="space-y-4">
        {config.credentialFields.map((field) => (
          <div key={field.key} className="space-y-2">
            <Label htmlFor={field.key}>{field.label}</Label>
            <div className="relative">
              <Input
                id={field.key}
                type={field.masked && !showMasked[field.key] ? "password" : "text"}
                value={credentials[field.key] || ""}
                onChange={(e) => onCredentialChange(field.key, e.target.value)}
                placeholder={field.hint}
                className={field.masked ? "pr-10" : ""}
              />
              {field.masked && (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute right-0 top-0 h-full px-3"
                  onClick={() => toggleMask(field.key)}
                >
                  {showMasked[field.key] ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// Step 4: Test & Preview
// =============================================================================

interface TestPreviewStepProps {
  createdSource: Source | null;
  isCreating: boolean;
  onTest: () => void;
  isTesting: boolean;
  testResult: { success: boolean; message: string; latency_ms?: number | null } | null;
}

function TestPreviewStep({
  createdSource,
  isCreating,
  onTest,
  isTesting,
  testResult,
}: TestPreviewStepProps) {
  const { data: previewData, isLoading: isLoadingPreview } = useSourcePreview(
    createdSource?.id || "",
    10,
    { enabled: !!createdSource && testResult?.success }
  );

  if (isCreating) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p className="mt-4 text-muted-foreground">Creating data source...</p>
      </div>
    );
  }

  if (!createdSource) {
    return (
      <div className="space-y-6">
        <div>
          <h3 className="text-lg font-medium">Test Connection</h3>
          <p className="text-sm text-muted-foreground">
            Save your configuration and test the connection to your data source.
          </p>
        </div>

        <div className="rounded-lg border border-dashed p-8 text-center">
          <Zap className="mx-auto h-12 w-12 text-muted-foreground" />
          <h4 className="mt-4 font-medium">Ready to Save</h4>
          <p className="mt-2 text-sm text-muted-foreground">
            Click &quot;Create Source&quot; to save your configuration and test the connection.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium">Test Connection & Preview Data</h3>
        <p className="text-sm text-muted-foreground">
          Verify the connection and preview sample data from your source.
        </p>
      </div>

      {/* Connection Test */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Connection Test</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {testResult ? (
            <div
              className={`flex items-center gap-3 rounded-lg p-4 ${
                testResult.success
                  ? "bg-green-500/10 text-green-700"
                  : "bg-red-500/10 text-red-700"
              }`}
            >
              {testResult.success ? (
                <CheckCircle className="h-5 w-5" />
              ) : (
                <Zap className="h-5 w-5" />
              )}
              <div>
                <p className="font-medium">
                  {testResult.success ? "Connection Successful" : "Connection Failed"}
                </p>
                <p className="text-sm opacity-80">
                  {testResult.message}
                  {testResult.latency_ms && ` (${testResult.latency_ms.toFixed(0)}ms)`}
                </p>
              </div>
            </div>
          ) : (
            <Button onClick={onTest} disabled={isTesting}>
              {isTesting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Testing...
                </>
              ) : (
                <>
                  <Zap className="mr-2 h-4 w-4" />
                  Test Connection
                </>
              )}
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Data Preview */}
      {testResult?.success && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Sample Data Preview</CardTitle>
            <CardDescription>
              First {previewData?.record_count || 0} records from the source
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoadingPreview ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : previewData && previewData.records.length > 0 ? (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      {Object.keys(previewData.records[0]).slice(0, 5).map((key) => (
                        <TableHead key={key}>{key}</TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {previewData.records.slice(0, 5).map((record, idx) => (
                      <TableRow key={idx}>
                        {Object.entries(record).slice(0, 5).map(([key, value]) => (
                          <TableCell key={key} className="max-w-[200px] truncate">
                            {String(value ?? "-")}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <p className="text-muted-foreground text-center py-4">
                No sample data available
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// =============================================================================
// Wizard Progress Bar
// =============================================================================

interface WizardProgressProps {
  currentStep: number;
  steps: WizardStep[];
}

function WizardProgress({ currentStep, steps }: WizardProgressProps) {
  return (
    <div className="mb-8">
      <div className="flex items-center justify-between">
        {steps.map((step, index) => (
          <div key={step.id} className="flex items-center">
            <div
              className={`flex h-10 w-10 items-center justify-center rounded-full border-2 ${
                currentStep > step.id
                  ? "border-primary bg-primary text-primary-foreground"
                  : currentStep === step.id
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-muted bg-muted text-muted-foreground"
              }`}
            >
              {currentStep > step.id ? (
                <CheckCircle className="h-5 w-5" />
              ) : (
                step.id
              )}
            </div>
            {index < steps.length - 1 && (
              <div
                className={`mx-2 h-0.5 w-12 sm:w-24 md:w-32 ${
                  currentStep > step.id ? "bg-primary" : "bg-muted"
                }`}
              />
            )}
          </div>
        ))}
      </div>
      <div className="mt-2 flex justify-between">
        {steps.map((step) => (
          <div
            key={step.id}
            className={`text-center ${
              currentStep === step.id ? "text-primary" : "text-muted-foreground"
            }`}
          >
            <p className="text-sm font-medium">{step.title}</p>
            <p className="text-xs hidden sm:block">{step.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// Main Wizard Component
// =============================================================================

export default function NewSourcePage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);

  // Form state
  const [selectedType, setSelectedType] = useState<SourceType | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [connectionParams, setConnectionParams] = useState<Record<string, string>>({});
  const [sslEnabled, setSslEnabled] = useState(true);
  const [credentials, setCredentials] = useState<Record<string, string>>({});

  // Created source for testing
  const [createdSource, setCreatedSource] = useState<Source | null>(null);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
    latency_ms?: number | null;
  } | null>(null);

  // Mutations
  const createSourceMutation = useCreateSource({
    onSuccess: (source) => {
      setCreatedSource(source);
      toast.success("Source created successfully");
    },
    onError: (error) => {
      toast.error(`Failed to create source: ${error.message}`);
    },
  });

  const testConnectionMutation = useTestSourceConnection({
    onSuccess: (data) => {
      setTestResult({
        success: data.success,
        message: data.message,
        latency_ms: data.latency_ms,
      });
      if (data.success) {
        toast.success("Connection test passed");
      } else {
        toast.error(`Connection test failed: ${data.message}`);
      }
    },
    onError: (error) => {
      setTestResult({
        success: false,
        message: error.message,
      });
      toast.error(`Connection test error: ${error.message}`);
    },
  });

  // Handlers
  const handleConnectionParamChange = (key: string, value: string) => {
    setConnectionParams((prev) => ({ ...prev, [key]: value }));
  };

  const handleCredentialChange = (key: string, value: string) => {
    setCredentials((prev) => ({ ...prev, [key]: value }));
  };

  const handleNext = () => {
    if (currentStep === 4 && !createdSource) {
      // Create the source
      if (!selectedType || !name) {
        toast.error("Please complete all required fields");
        return;
      }

      const request: CreateSourceRequest = {
        name,
        description,
        source_type: selectedType,
        connection_params: {
          ...connectionParams,
          port: connectionParams.port ? parseInt(connectionParams.port, 10) : undefined,
          ssl_enabled: sslEnabled,
          verify_ssl: true,
        },
        credentials: Object.keys(credentials).length > 0 ? credentials : undefined,
      };

      createSourceMutation.mutate(request);
    } else if (currentStep < 4) {
      setCurrentStep((prev) => prev + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep((prev) => prev - 1);
    }
  };

  const handleTest = () => {
    if (createdSource) {
      testConnectionMutation.mutate(createdSource.id);
    }
  };

  const handleFinish = () => {
    router.push("/etl/sources");
  };

  // Validation
  const canProceed = () => {
    switch (currentStep) {
      case 1:
        return selectedType !== null;
      case 2:
        if (!name.trim()) return false;
        if (!selectedType) return false;
        const config = SOURCE_TYPES[selectedType];
        return config.connectionFields
          .filter((f) => f.required)
          .every((f) => connectionParams[f.key]?.trim());
      case 3:
        return true; // Credentials are optional
      case 4:
        return testResult?.success || false;
      default:
        return false;
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Page Header */}
      <div className="mb-6">
        <Link
          href="/etl/sources"
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Sources
        </Link>
        <h1 className="mt-4 text-2xl font-bold tracking-tight">Add New Data Source</h1>
        <p className="text-muted-foreground">
          Configure a new connection to a clinical data source.
        </p>
      </div>

      {/* Progress Bar */}
      <WizardProgress currentStep={currentStep} steps={WIZARD_STEPS} />

      {/* Wizard Content */}
      <Card>
        <CardContent className="pt-6">
          {currentStep === 1 && (
            <TypeSelectionStep
              selectedType={selectedType}
              onSelectType={setSelectedType}
            />
          )}

          {currentStep === 2 && selectedType && (
            <ConnectionStep
              sourceType={selectedType}
              name={name}
              description={description}
              connectionParams={connectionParams}
              sslEnabled={sslEnabled}
              onNameChange={setName}
              onDescriptionChange={setDescription}
              onConnectionParamChange={handleConnectionParamChange}
              onSslChange={setSslEnabled}
            />
          )}

          {currentStep === 3 && selectedType && (
            <CredentialsStep
              sourceType={selectedType}
              credentials={credentials}
              onCredentialChange={handleCredentialChange}
            />
          )}

          {currentStep === 4 && (
            <TestPreviewStep
              createdSource={createdSource}
              isCreating={createSourceMutation.isPending}
              onTest={handleTest}
              isTesting={testConnectionMutation.isPending}
              testResult={testResult}
            />
          )}
        </CardContent>

        <CardFooter className="flex justify-between border-t pt-6">
          <Button
            variant="outline"
            onClick={handleBack}
            disabled={currentStep === 1}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Button>

          <div className="flex gap-2">
            {currentStep === 4 && createdSource && testResult?.success ? (
              <Button onClick={handleFinish}>
                <CheckCircle className="mr-2 h-4 w-4" />
                Finish
              </Button>
            ) : (
              <Button
                onClick={handleNext}
                disabled={!canProceed() || createSourceMutation.isPending}
              >
                {createSourceMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Creating...
                  </>
                ) : currentStep === 4 && !createdSource ? (
                  <>
                    Create Source
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </>
                ) : (
                  <>
                    Next
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </>
                )}
              </Button>
            )}
          </div>
        </CardFooter>
      </Card>
    </div>
  );
}
