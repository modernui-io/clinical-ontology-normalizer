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
import { Progress } from "@/components/ui/progress";
import {
  ArrowLeft,
  ArrowRight,
  Calendar,
  CheckCircle,
  Database,
  Eye,
  EyeOff,
  FileSpreadsheet,
  FileText,
  Loader2,
  Server,
  Shield,
  Upload,
  Zap,
  Clock,
  Save,
} from "lucide-react";

// =============================================================================
// Types
// =============================================================================

type SourceType = "fhir" | "hl7v2" | "ccda" | "csv" | "database";
type AuthType = "none" | "basic" | "oauth" | "smart";
type DatabaseType = "postgresql" | "mysql" | "sqlserver" | "oracle";
type ScheduleFrequency = "once" | "hourly" | "daily" | "weekly";

interface WizardStep {
  id: number;
  title: string;
  description: string;
}

const WIZARD_STEPS: WizardStep[] = [
  { id: 1, title: "Source Type", description: "Select data source type" },
  { id: 2, title: "Connection", description: "Configure connection" },
  { id: 3, title: "Test", description: "Verify connection" },
  { id: 4, title: "Mapping", description: "Review field mappings" },
  { id: 5, title: "Schedule", description: "Set schedule and save" },
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
  }
> = {
  fhir: {
    icon: <Server className="h-8 w-8" />,
    label: "FHIR Server",
    description: "Connect to FHIR R4 compliant servers for clinical data extraction",
    color: "text-blue-500 bg-blue-500/10 border-blue-500/20",
  },
  hl7v2: {
    icon: <FileText className="h-8 w-8" />,
    label: "HL7 v2",
    description: "Parse HL7 v2.x messages from MLLP or file-based sources",
    color: "text-purple-500 bg-purple-500/10 border-purple-500/20",
  },
  ccda: {
    icon: <FileText className="h-8 w-8" />,
    label: "C-CDA",
    description: "Import clinical data from C-CDA/CCD XML documents",
    color: "text-green-500 bg-green-500/10 border-green-500/20",
  },
  csv: {
    icon: <FileSpreadsheet className="h-8 w-8" />,
    label: "CSV/Excel",
    description: "Import data from CSV files or Excel spreadsheets",
    color: "text-orange-500 bg-orange-500/10 border-orange-500/20",
  },
  database: {
    icon: <Database className="h-8 w-8" />,
    label: "Database",
    description: "Direct connection to PostgreSQL, MySQL, SQL Server, or Oracle",
    color: "text-indigo-500 bg-indigo-500/10 border-indigo-500/20",
  },
};

const DATABASE_TYPES: Record<DatabaseType, { label: string; defaultPort: number }> = {
  postgresql: { label: "PostgreSQL", defaultPort: 5432 },
  mysql: { label: "MySQL", defaultPort: 3306 },
  sqlserver: { label: "SQL Server", defaultPort: 1433 },
  oracle: { label: "Oracle", defaultPort: 1521 },
};

// =============================================================================
// Mock Data for Preview
// =============================================================================

const MOCK_SAMPLE_DATA = [
  { patient_id: "P001", first_name: "John", last_name: "Doe", dob: "1985-03-15", gender: "M" },
  { patient_id: "P002", first_name: "Jane", last_name: "Smith", dob: "1990-07-22", gender: "F" },
  { patient_id: "P003", first_name: "Robert", last_name: "Johnson", dob: "1978-11-08", gender: "M" },
  { patient_id: "P004", first_name: "Emily", last_name: "Williams", dob: "1995-01-30", gender: "F" },
  { patient_id: "P005", first_name: "Michael", last_name: "Brown", dob: "1982-09-14", gender: "M" },
];

const MOCK_FIELD_MAPPINGS = [
  { source: "patient_id", target: "person_id", omopTable: "person", confidence: 95, status: "mapped" },
  { source: "first_name", target: "first_name", omopTable: "person", confidence: 100, status: "mapped" },
  { source: "last_name", target: "last_name", omopTable: "person", confidence: 100, status: "mapped" },
  { source: "dob", target: "birth_datetime", omopTable: "person", confidence: 90, status: "mapped" },
  { source: "gender", target: "gender_concept_id", omopTable: "person", confidence: 85, status: "needs_review" },
  { source: "mrn", target: "person_source_value", omopTable: "person", confidence: 80, status: "suggested" },
  { source: "ssn", target: null, omopTable: null, confidence: 0, status: "unmapped" },
];

// =============================================================================
// Step 1: Source Type Selection
// =============================================================================

interface SourceTypeStepProps {
  selectedType: SourceType | null;
  onSelectType: (type: SourceType) => void;
}

function SourceTypeStep({ selectedType, onSelectType }: SourceTypeStepProps) {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold">Select Data Source Type</h3>
        <p className="text-sm text-muted-foreground">
          Choose the type of data source you want to configure for ETL processing.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {(Object.entries(SOURCE_TYPES) as [SourceType, typeof SOURCE_TYPES[SourceType]][]).map(
          ([type, config]) => (
            <button
              key={type}
              type="button"
              onClick={() => onSelectType(type)}
              className={`relative flex flex-col items-center gap-4 rounded-xl border-2 p-6 text-center transition-all hover:shadow-md ${
                selectedType === type
                  ? `${config.color} border-current shadow-md`
                  : "border-border bg-card hover:border-muted-foreground/30"
              }`}
            >
              <div className={`rounded-xl p-4 ${config.color}`}>
                {config.icon}
              </div>
              <div>
                <p className="font-semibold">{config.label}</p>
                <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
                  {config.description}
                </p>
              </div>
              {selectedType === type && (
                <div className="absolute right-3 top-3">
                  <CheckCircle className="h-5 w-5 text-current" />
                </div>
              )}
            </button>
          )
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Step 2: Connection Configuration
// =============================================================================

interface ConnectionConfigStepProps {
  sourceType: SourceType;
  config: ConnectionConfig;
  onConfigChange: (config: ConnectionConfig) => void;
}

interface ConnectionConfig {
  // FHIR
  fhirUrl?: string;
  authType?: AuthType;
  clientId?: string;
  clientSecret?: string;
  username?: string;
  password?: string;
  scope?: string;
  // HL7v2
  hl7Host?: string;
  hl7Port?: string;
  sendingApp?: string;
  receivingApp?: string;
  // C-CDA
  ccdaPath?: string;
  ccdaUploadEndpoint?: string;
  // CSV
  csvPath?: string;
  sftpHost?: string;
  sftpPort?: string;
  sftpUsername?: string;
  sftpPassword?: string;
  // Database
  dbType?: DatabaseType;
  dbHost?: string;
  dbPort?: string;
  dbName?: string;
  dbUsername?: string;
  dbPassword?: string;
  dbSchema?: string;
  sslEnabled?: boolean;
}

function ConnectionConfigStep({ sourceType, config, onConfigChange }: ConnectionConfigStepProps) {
  const [showPassword, setShowPassword] = useState<Record<string, boolean>>({});

  const togglePassword = (field: string) => {
    setShowPassword((prev) => ({ ...prev, [field]: !prev[field] }));
  };

  const updateConfig = (key: keyof ConnectionConfig, value: string | boolean) => {
    onConfigChange({ ...config, [key]: value });
  };

  const renderFHIRConfig = () => (
    <div className="space-y-6">
      <div className="space-y-2">
        <Label htmlFor="fhirUrl">
          FHIR Server URL <span className="text-destructive">*</span>
        </Label>
        <Input
          id="fhirUrl"
          placeholder="https://fhir.example.com/fhir"
          value={config.fhirUrl || ""}
          onChange={(e) => updateConfig("fhirUrl", e.target.value)}
        />
        <p className="text-xs text-muted-foreground">
          The base URL of the FHIR R4 server endpoint
        </p>
      </div>

      <div className="space-y-2">
        <Label>Authentication Type</Label>
        <Select
          value={config.authType || "none"}
          onValueChange={(value) => updateConfig("authType", value as AuthType)}
        >
          <SelectTrigger>
            <SelectValue placeholder="Select authentication type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">No Authentication</SelectItem>
            <SelectItem value="basic">Basic Auth</SelectItem>
            <SelectItem value="oauth">OAuth 2.0</SelectItem>
            <SelectItem value="smart">SMART on FHIR</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {config.authType === "basic" && (
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              value={config.username || ""}
              onChange={(e) => updateConfig("username", e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword.password ? "text" : "password"}
                value={config.password || ""}
                onChange={(e) => updateConfig("password", e.target.value)}
                className="pr-10"
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="absolute right-0 top-0 h-full px-3"
                onClick={() => togglePassword("password")}
              >
                {showPassword.password ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </Button>
            </div>
          </div>
        </div>
      )}

      {(config.authType === "oauth" || config.authType === "smart") && (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="clientId">Client ID</Label>
              <Input
                id="clientId"
                value={config.clientId || ""}
                onChange={(e) => updateConfig("clientId", e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="clientSecret">Client Secret</Label>
              <div className="relative">
                <Input
                  id="clientSecret"
                  type={showPassword.clientSecret ? "text" : "password"}
                  value={config.clientSecret || ""}
                  onChange={(e) => updateConfig("clientSecret", e.target.value)}
                  className="pr-10"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute right-0 top-0 h-full px-3"
                  onClick={() => togglePassword("clientSecret")}
                >
                  {showPassword.clientSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="scope">OAuth Scope</Label>
            <Input
              id="scope"
              placeholder="patient/*.read user/*.read"
              value={config.scope || ""}
              onChange={(e) => updateConfig("scope", e.target.value)}
            />
          </div>
        </>
      )}
    </div>
  );

  const renderHL7v2Config = () => (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="hl7Host">
            Host <span className="text-destructive">*</span>
          </Label>
          <Input
            id="hl7Host"
            placeholder="hl7.example.com"
            value={config.hl7Host || ""}
            onChange={(e) => updateConfig("hl7Host", e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="hl7Port">
            Port <span className="text-destructive">*</span>
          </Label>
          <Input
            id="hl7Port"
            type="number"
            placeholder="2575"
            value={config.hl7Port || ""}
            onChange={(e) => updateConfig("hl7Port", e.target.value)}
          />
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="sendingApp">Sending Application</Label>
          <Input
            id="sendingApp"
            placeholder="SENDING_APP"
            value={config.sendingApp || ""}
            onChange={(e) => updateConfig("sendingApp", e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="receivingApp">Receiving Application</Label>
          <Input
            id="receivingApp"
            placeholder="RECEIVING_APP"
            value={config.receivingApp || ""}
            onChange={(e) => updateConfig("receivingApp", e.target.value)}
          />
        </div>
      </div>
    </div>
  );

  const renderCCDAConfig = () => (
    <div className="space-y-6">
      <div className="space-y-2">
        <Label htmlFor="ccdaPath">
          Documents Directory Path <span className="text-destructive">*</span>
        </Label>
        <Input
          id="ccdaPath"
          placeholder="/data/ccda/documents"
          value={config.ccdaPath || ""}
          onChange={(e) => updateConfig("ccdaPath", e.target.value)}
        />
        <p className="text-xs text-muted-foreground">
          Path to the directory containing C-CDA XML documents
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="ccdaUploadEndpoint">Upload Endpoint (optional)</Label>
        <Input
          id="ccdaUploadEndpoint"
          placeholder="https://api.example.com/upload/ccda"
          value={config.ccdaUploadEndpoint || ""}
          onChange={(e) => updateConfig("ccdaUploadEndpoint", e.target.value)}
        />
      </div>
    </div>
  );

  const renderCSVConfig = () => (
    <div className="space-y-6">
      <div className="rounded-lg border border-dashed p-8 text-center">
        <Upload className="mx-auto h-12 w-12 text-muted-foreground" />
        <h4 className="mt-4 font-medium">Upload CSV/Excel Files</h4>
        <p className="mt-2 text-sm text-muted-foreground">
          Drag and drop files here or click to browse
        </p>
        <Button className="mt-4" variant="outline">
          <Upload className="mr-2 h-4 w-4" />
          Browse Files
        </Button>
      </div>

      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-background px-2 text-muted-foreground">Or configure SFTP</span>
        </div>
      </div>

      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="sftpHost">SFTP Host</Label>
            <Input
              id="sftpHost"
              placeholder="sftp.example.com"
              value={config.sftpHost || ""}
              onChange={(e) => updateConfig("sftpHost", e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="sftpPort">SFTP Port</Label>
            <Input
              id="sftpPort"
              type="number"
              placeholder="22"
              value={config.sftpPort || ""}
              onChange={(e) => updateConfig("sftpPort", e.target.value)}
            />
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="sftpUsername">Username</Label>
            <Input
              id="sftpUsername"
              value={config.sftpUsername || ""}
              onChange={(e) => updateConfig("sftpUsername", e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="sftpPassword">Password</Label>
            <div className="relative">
              <Input
                id="sftpPassword"
                type={showPassword.sftpPassword ? "text" : "password"}
                value={config.sftpPassword || ""}
                onChange={(e) => updateConfig("sftpPassword", e.target.value)}
                className="pr-10"
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="absolute right-0 top-0 h-full px-3"
                onClick={() => togglePassword("sftpPassword")}
              >
                {showPassword.sftpPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </Button>
            </div>
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="csvPath">Remote Directory Path</Label>
          <Input
            id="csvPath"
            placeholder="/exports/csv"
            value={config.csvPath || ""}
            onChange={(e) => updateConfig("csvPath", e.target.value)}
          />
        </div>
      </div>
    </div>
  );

  const renderDatabaseConfig = () => (
    <div className="space-y-6">
      <div className="space-y-2">
        <Label>Database Type</Label>
        <Select
          value={config.dbType || "postgresql"}
          onValueChange={(value) => {
            const dbType = value as DatabaseType;
            updateConfig("dbType", dbType);
            updateConfig("dbPort", DATABASE_TYPES[dbType].defaultPort.toString());
          }}
        >
          <SelectTrigger>
            <SelectValue placeholder="Select database type" />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(DATABASE_TYPES).map(([type, info]) => (
              <SelectItem key={type} value={type}>
                {info.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-2 sm:col-span-2">
          <Label htmlFor="dbHost">
            Host <span className="text-destructive">*</span>
          </Label>
          <Input
            id="dbHost"
            placeholder="db.example.com"
            value={config.dbHost || ""}
            onChange={(e) => updateConfig("dbHost", e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="dbPort">
            Port <span className="text-destructive">*</span>
          </Label>
          <Input
            id="dbPort"
            type="number"
            value={config.dbPort || ""}
            onChange={(e) => updateConfig("dbPort", e.target.value)}
          />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="dbName">
            Database Name <span className="text-destructive">*</span>
          </Label>
          <Input
            id="dbName"
            placeholder="clinical_data"
            value={config.dbName || ""}
            onChange={(e) => updateConfig("dbName", e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="dbSchema">Schema</Label>
          <Input
            id="dbSchema"
            placeholder="public"
            value={config.dbSchema || ""}
            onChange={(e) => updateConfig("dbSchema", e.target.value)}
          />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="dbUsername">
            Username <span className="text-destructive">*</span>
          </Label>
          <Input
            id="dbUsername"
            value={config.dbUsername || ""}
            onChange={(e) => updateConfig("dbUsername", e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="dbPassword">
            Password <span className="text-destructive">*</span>
          </Label>
          <div className="relative">
            <Input
              id="dbPassword"
              type={showPassword.dbPassword ? "text" : "password"}
              value={config.dbPassword || ""}
              onChange={(e) => updateConfig("dbPassword", e.target.value)}
              className="pr-10"
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="absolute right-0 top-0 h-full px-3"
              onClick={() => togglePassword("dbPassword")}
            >
              {showPassword.dbPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between rounded-lg border p-4">
        <div className="space-y-0.5">
          <Label htmlFor="ssl">Enable SSL/TLS</Label>
          <p className="text-sm text-muted-foreground">
            Use encrypted connection (recommended for production)
          </p>
        </div>
        <Switch
          id="ssl"
          checked={config.sslEnabled ?? true}
          onCheckedChange={(checked) => updateConfig("sslEnabled", checked)}
        />
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold">Configure Connection</h3>
        <p className="text-sm text-muted-foreground">
          Enter the connection details for your {SOURCE_TYPES[sourceType].label} data source.
        </p>
      </div>

      {sourceType === "fhir" && renderFHIRConfig()}
      {sourceType === "hl7v2" && renderHL7v2Config()}
      {sourceType === "ccda" && renderCCDAConfig()}
      {sourceType === "csv" && renderCSVConfig()}
      {sourceType === "database" && renderDatabaseConfig()}
    </div>
  );
}

// =============================================================================
// Step 3: Connection Test
// =============================================================================

interface ConnectionTestStepProps {
  sourceType: SourceType;
  onTest: () => void;
  isTesting: boolean;
  testResult: { success: boolean; message: string; latency?: number } | null;
  sampleData: Record<string, unknown>[] | null;
}

function ConnectionTestStep({
  sourceType,
  onTest,
  isTesting,
  testResult,
  sampleData,
}: ConnectionTestStepProps) {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold">Test Connection</h3>
        <p className="text-sm text-muted-foreground">
          Verify the connection to your data source and preview sample data.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Connection Status</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {!testResult ? (
            <div className="text-center py-4">
              <Shield className="mx-auto h-12 w-12 text-muted-foreground" />
              <p className="mt-4 text-muted-foreground">
                Click the button below to test your connection
              </p>
              <Button className="mt-4" onClick={onTest} disabled={isTesting}>
                {isTesting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Testing Connection...
                  </>
                ) : (
                  <>
                    <Zap className="mr-2 h-4 w-4" />
                    Test Connection
                  </>
                )}
              </Button>
            </div>
          ) : (
            <div
              className={`flex items-center gap-3 rounded-lg p-4 ${
                testResult.success
                  ? "bg-green-500/10 text-green-700 dark:text-green-400"
                  : "bg-red-500/10 text-red-700 dark:text-red-400"
              }`}
            >
              {testResult.success ? (
                <CheckCircle className="h-6 w-6 flex-shrink-0" />
              ) : (
                <Shield className="h-6 w-6 flex-shrink-0" />
              )}
              <div className="flex-1">
                <p className="font-semibold">
                  {testResult.success ? "Connection Successful" : "Connection Failed"}
                </p>
                <p className="text-sm opacity-80">
                  {testResult.message}
                  {testResult.latency && ` (${testResult.latency}ms)`}
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={onTest}
                disabled={isTesting}
              >
                {isTesting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  "Retest"
                )}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {testResult?.success && sampleData && sampleData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Sample Data Preview</CardTitle>
            <CardDescription>
              First {sampleData.length} records from the source
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    {Object.keys(sampleData[0]).map((key) => (
                      <TableHead key={key} className="whitespace-nowrap">
                        {key}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sampleData.map((row, idx) => (
                    <TableRow key={idx}>
                      {Object.values(row).map((value, cellIdx) => (
                        <TableCell key={cellIdx} className="max-w-[200px] truncate">
                          {String(value ?? "-")}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// =============================================================================
// Step 4: Field Mapping Preview
// =============================================================================

interface FieldMapping {
  source: string;
  target: string | null;
  omopTable: string | null;
  confidence: number;
  status: "mapped" | "needs_review" | "suggested" | "unmapped";
}

interface FieldMappingStepProps {
  mappings: FieldMapping[];
  onMappingChange: (index: number, mapping: Partial<FieldMapping>) => void;
}

function FieldMappingStep({ mappings, onMappingChange }: FieldMappingStepProps) {
  const getMappingStatusBadge = (status: FieldMapping["status"]) => {
    switch (status) {
      case "mapped":
        return <Badge variant="outline" className="text-green-600 border-green-600">Mapped</Badge>;
      case "needs_review":
        return <Badge variant="outline" className="text-yellow-600 border-yellow-600">Needs Review</Badge>;
      case "suggested":
        return <Badge variant="outline" className="text-blue-600 border-blue-600">Suggested</Badge>;
      case "unmapped":
        return <Badge variant="destructive">Unmapped</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold">Review Field Mappings</h3>
        <p className="text-sm text-muted-foreground">
          Auto-detected source fields with suggested OMOP CDM mappings. Review and adjust as needed.
        </p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">Field Mappings</CardTitle>
              <CardDescription>
                {mappings.filter((m) => m.status === "mapped").length} of {mappings.length} fields mapped
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Badge variant="secondary">
                {mappings.filter((m) => m.status === "needs_review").length} need review
              </Badge>
              <Badge variant="destructive">
                {mappings.filter((m) => m.status === "unmapped").length} unmapped
              </Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Source Field</TableHead>
                  <TableHead>Target Field</TableHead>
                  <TableHead>OMOP Table</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {mappings.map((mapping, idx) => (
                  <TableRow key={idx}>
                    <TableCell className="font-mono text-sm">
                      {mapping.source}
                    </TableCell>
                    <TableCell>
                      {mapping.target ? (
                        <span className="font-mono text-sm">{mapping.target}</span>
                      ) : (
                        <span className="text-muted-foreground italic">Not mapped</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {mapping.omopTable ? (
                        <Badge variant="secondary">{mapping.omopTable}</Badge>
                      ) : (
                        "-"
                      )}
                    </TableCell>
                    <TableCell>
                      {mapping.confidence > 0 ? (
                        <div className="flex items-center gap-2">
                          <Progress value={mapping.confidence} className="w-16 h-2" />
                          <span className="text-sm text-muted-foreground">
                            {mapping.confidence}%
                          </span>
                        </div>
                      ) : (
                        "-"
                      )}
                    </TableCell>
                    <TableCell>
                      {getMappingStatusBadge(mapping.status)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
        <CardFooter className="border-t pt-4">
          <div className="flex w-full items-center justify-between">
            <p className="text-sm text-muted-foreground">
              You can adjust mappings in detail after saving the configuration.
            </p>
            <Link href="/etl/mapping">
              <Button variant="outline" size="sm">
                Open Mapping Editor
              </Button>
            </Link>
          </div>
        </CardFooter>
      </Card>
    </div>
  );
}

// =============================================================================
// Step 5: Schedule & Save
// =============================================================================

interface ScheduleConfig {
  name: string;
  description: string;
  frequency: ScheduleFrequency;
  time: string;
  dayOfWeek: string;
}

interface ScheduleStepProps {
  schedule: ScheduleConfig;
  onScheduleChange: (schedule: ScheduleConfig) => void;
}

function ScheduleStep({ schedule, onScheduleChange }: ScheduleStepProps) {
  const updateSchedule = (key: keyof ScheduleConfig, value: string) => {
    onScheduleChange({ ...schedule, [key]: value });
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold">Schedule &amp; Save</h3>
        <p className="text-sm text-muted-foreground">
          Name your configuration and set up the ETL schedule.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Configuration Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="configName">
              Configuration Name <span className="text-destructive">*</span>
            </Label>
            <Input
              id="configName"
              placeholder="e.g., Hospital EHR FHIR Sync"
              value={schedule.name}
              onChange={(e) => updateSchedule("name", e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="configDescription">Description</Label>
            <Textarea
              id="configDescription"
              placeholder="Optional description of this ETL configuration"
              value={schedule.description}
              onChange={(e) => updateSchedule("description", e.target.value)}
              rows={3}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Schedule
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Run Frequency</Label>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {[
                { value: "once", label: "One-time", icon: Clock },
                { value: "hourly", label: "Hourly", icon: Clock },
                { value: "daily", label: "Daily", icon: Calendar },
                { value: "weekly", label: "Weekly", icon: Calendar },
              ].map(({ value, label, icon: Icon }) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => updateSchedule("frequency", value as ScheduleFrequency)}
                  className={`flex items-center gap-2 rounded-lg border p-3 transition-colors ${
                    schedule.frequency === value
                      ? "border-primary bg-primary/5"
                      : "border-border hover:bg-muted/50"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span className="text-sm font-medium">{label}</span>
                </button>
              ))}
            </div>
          </div>

          {schedule.frequency !== "once" && (
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="time">Time of Day</Label>
                <Input
                  id="time"
                  type="time"
                  value={schedule.time}
                  onChange={(e) => updateSchedule("time", e.target.value)}
                />
              </div>
              {schedule.frequency === "weekly" && (
                <div className="space-y-2">
                  <Label>Day of Week</Label>
                  <Select
                    value={schedule.dayOfWeek}
                    onValueChange={(value) => updateSchedule("dayOfWeek", value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select day" />
                    </SelectTrigger>
                    <SelectContent>
                      {["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map(
                        (day, idx) => (
                          <SelectItem key={day} value={idx.toString()}>
                            {day}
                          </SelectItem>
                        )
                      )}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
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
              className={`flex h-10 w-10 items-center justify-center rounded-full border-2 transition-colors ${
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
                className={`mx-1 h-0.5 w-8 sm:w-12 md:w-16 lg:w-24 ${
                  currentStep > step.id ? "bg-primary" : "bg-muted"
                }`}
              />
            )}
          </div>
        ))}
      </div>
      <div className="mt-3 flex justify-between">
        {steps.map((step) => (
          <div
            key={step.id}
            className={`text-center flex-1 ${
              currentStep === step.id ? "text-primary" : "text-muted-foreground"
            }`}
          >
            <p className="text-xs font-medium sm:text-sm">{step.title}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// Main Wizard Component
// =============================================================================

export default function ETLWizardPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);

  // Step 1: Source Type
  const [selectedType, setSelectedType] = useState<SourceType | null>(null);

  // Step 2: Connection Config
  const [connectionConfig, setConnectionConfig] = useState<ConnectionConfig>({
    sslEnabled: true,
    dbType: "postgresql",
    dbPort: "5432",
  });

  // Step 3: Test Results
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
    latency?: number;
  } | null>(null);
  const [sampleData, setSampleData] = useState<Record<string, unknown>[] | null>(null);

  // Step 4: Field Mappings
  const [fieldMappings, setFieldMappings] = useState<FieldMapping[]>(MOCK_FIELD_MAPPINGS as FieldMapping[]);

  // Step 5: Schedule
  const [scheduleConfig, setScheduleConfig] = useState<ScheduleConfig>({
    name: "",
    description: "",
    frequency: "daily",
    time: "02:00",
    dayOfWeek: "0",
  });

  // Saving state
  const [isSaving, setIsSaving] = useState(false);

  // Handle connection test
  const handleTest = async () => {
    setIsTesting(true);
    setTestResult(null);
    setSampleData(null);

    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 2000));

    // Mock successful result
    setTestResult({
      success: true,
      message: "Successfully connected to the data source",
      latency: 145,
    });
    setSampleData(MOCK_SAMPLE_DATA);
    setIsTesting(false);
  };

  // Handle mapping change
  const handleMappingChange = (index: number, mapping: Partial<FieldMapping>) => {
    setFieldMappings((prev) =>
      prev.map((m, i) => (i === index ? { ...m, ...mapping } : m))
    );
  };

  // Handle save
  const handleSave = async () => {
    if (!scheduleConfig.name.trim()) {
      toast.error("Please enter a configuration name");
      return;
    }

    setIsSaving(true);

    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 1500));

    toast.success("ETL configuration saved successfully");
    setIsSaving(false);
    router.push("/etl/sources");
  };

  // Navigation
  const handleNext = () => {
    if (currentStep < 5) {
      setCurrentStep((prev) => prev + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep((prev) => prev - 1);
    }
  };

  // Validation
  const canProceed = () => {
    switch (currentStep) {
      case 1:
        return selectedType !== null;
      case 2:
        // Basic validation based on source type
        if (!selectedType) return false;
        switch (selectedType) {
          case "fhir":
            return !!connectionConfig.fhirUrl;
          case "hl7v2":
            return !!connectionConfig.hl7Host && !!connectionConfig.hl7Port;
          case "ccda":
            return !!connectionConfig.ccdaPath;
          case "csv":
            return !!(connectionConfig.csvPath || connectionConfig.sftpHost);
          case "database":
            return !!(
              connectionConfig.dbHost &&
              connectionConfig.dbPort &&
              connectionConfig.dbName &&
              connectionConfig.dbUsername
            );
          default:
            return false;
        }
      case 3:
        return testResult?.success || false;
      case 4:
        return true; // Can always proceed from mapping review
      case 5:
        return !!scheduleConfig.name.trim();
      default:
        return false;
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Page Header */}
      <div className="mb-6">
        <Link
          href="/etl/sources"
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Data Sources
        </Link>
        <h1 className="mt-4 text-2xl font-bold tracking-tight">Data Source Configuration Wizard</h1>
        <p className="text-muted-foreground">
          Set up a new data source for ETL processing in 5 easy steps.
        </p>
      </div>

      {/* Progress Bar */}
      <WizardProgress currentStep={currentStep} steps={WIZARD_STEPS} />

      {/* Wizard Content */}
      <Card>
        <CardContent className="pt-6">
          {currentStep === 1 && (
            <SourceTypeStep
              selectedType={selectedType}
              onSelectType={setSelectedType}
            />
          )}

          {currentStep === 2 && selectedType && (
            <ConnectionConfigStep
              sourceType={selectedType}
              config={connectionConfig}
              onConfigChange={setConnectionConfig}
            />
          )}

          {currentStep === 3 && selectedType && (
            <ConnectionTestStep
              sourceType={selectedType}
              onTest={handleTest}
              isTesting={isTesting}
              testResult={testResult}
              sampleData={sampleData}
            />
          )}

          {currentStep === 4 && (
            <FieldMappingStep
              mappings={fieldMappings}
              onMappingChange={handleMappingChange}
            />
          )}

          {currentStep === 5 && (
            <ScheduleStep
              schedule={scheduleConfig}
              onScheduleChange={setScheduleConfig}
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
            {currentStep === 5 ? (
              <Button onClick={handleSave} disabled={!canProceed() || isSaving}>
                {isSaving ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Save className="mr-2 h-4 w-4" />
                    Save Configuration
                  </>
                )}
              </Button>
            ) : (
              <Button onClick={handleNext} disabled={!canProceed()}>
                Next
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            )}
          </div>
        </CardFooter>
      </Card>
    </div>
  );
}
