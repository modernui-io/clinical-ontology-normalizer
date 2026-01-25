"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
import { Textarea } from "@/components/ui/textarea";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  AlertCircle,
  CheckCircle,
  Clock,
  Settings,
  Shield,
  Server,
  Database,
  RefreshCw,
  Download,
  Upload,
  Link2,
  Key,
  Activity,
  FileText,
  Users,
  Heart,
  Pill,
  TestTube,
  Stethoscope,
} from "lucide-react";

// Types
interface EpicEndpoint {
  id: string;
  name: string;
  type: "FHIR R4" | "MyChart" | "CDS Hooks" | "SMART";
  status: "active" | "inactive" | "error";
  lastSync?: string;
  syncCount?: number;
}

interface ResourceMapping {
  epicResource: string;
  omopTable: string;
  mappingStatus: "complete" | "partial" | "unmapped";
  fieldCount: number;
  mappedFields: number;
}

interface SyncJob {
  id: string;
  type: string;
  status: "running" | "completed" | "failed" | "queued";
  progress: number;
  startTime: string;
  endTime?: string;
  recordsProcessed: number;
  errors: number;
}

// Mock data
const mockEndpoints: EpicEndpoint[] = [
  { id: "ep-1", name: "FHIR R4 Production", type: "FHIR R4", status: "active", lastSync: "2026-01-24T10:30:00Z", syncCount: 45230 },
  { id: "ep-2", name: "MyChart Patient Portal", type: "MyChart", status: "active", lastSync: "2026-01-24T09:15:00Z", syncCount: 12450 },
  { id: "ep-3", name: "CDS Hooks Integration", type: "CDS Hooks", status: "active", lastSync: "2026-01-24T10:45:00Z", syncCount: 8920 },
  { id: "ep-4", name: "SMART on FHIR Apps", type: "SMART", status: "inactive" },
];

const mockResourceMappings: ResourceMapping[] = [
  { epicResource: "Patient", omopTable: "person", mappingStatus: "complete", fieldCount: 24, mappedFields: 24 },
  { epicResource: "Encounter", omopTable: "visit_occurrence", mappingStatus: "complete", fieldCount: 32, mappedFields: 32 },
  { epicResource: "Condition", omopTable: "condition_occurrence", mappingStatus: "complete", fieldCount: 18, mappedFields: 18 },
  { epicResource: "MedicationRequest", omopTable: "drug_exposure", mappingStatus: "partial", fieldCount: 28, mappedFields: 22 },
  { epicResource: "Observation", omopTable: "measurement", mappingStatus: "partial", fieldCount: 35, mappedFields: 30 },
  { epicResource: "Procedure", omopTable: "procedure_occurrence", mappingStatus: "complete", fieldCount: 16, mappedFields: 16 },
  { epicResource: "DiagnosticReport", omopTable: "measurement", mappingStatus: "partial", fieldCount: 22, mappedFields: 18 },
  { epicResource: "AllergyIntolerance", omopTable: "observation", mappingStatus: "unmapped", fieldCount: 14, mappedFields: 0 },
];

const mockSyncJobs: SyncJob[] = [
  { id: "job-1", type: "Patient Demographics", status: "completed", progress: 100, startTime: "2026-01-24T10:00:00Z", endTime: "2026-01-24T10:15:00Z", recordsProcessed: 5230, errors: 12 },
  { id: "job-2", type: "Encounters", status: "running", progress: 68, startTime: "2026-01-24T10:30:00Z", recordsProcessed: 12450, errors: 5 },
  { id: "job-3", type: "Medications", status: "queued", progress: 0, startTime: "", recordsProcessed: 0, errors: 0 },
  { id: "job-4", type: "Lab Results", status: "failed", progress: 45, startTime: "2026-01-24T09:00:00Z", endTime: "2026-01-24T09:22:00Z", recordsProcessed: 8920, errors: 156 },
];

export default function EpicIntegrationPage() {
  const [endpoints] = useState<EpicEndpoint[]>(mockEndpoints);
  const [resourceMappings] = useState<ResourceMapping[]>(mockResourceMappings);
  const [syncJobs] = useState<SyncJob[]>(mockSyncJobs);
  const [config, setConfig] = useState({
    clientId: "epic-client-12345",
    environment: "production",
    fhirBaseUrl: "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4",
    authUrl: "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize",
    tokenUrl: "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token",
    scope: "patient/*.read user/*.read launch/patient",
    autoSync: true,
    syncInterval: "hourly",
    batchSize: 100,
  });

  const formatDate = (dateStr: string) => {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleString();
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "active":
      case "completed":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "inactive":
      case "queued":
        return <Clock className="h-4 w-4 text-gray-500" />;
      case "error":
      case "failed":
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      case "running":
        return <RefreshCw className="h-4 w-4 text-blue-500 animate-spin" />;
      default:
        return null;
    }
  };

  const getMappingColor = (status: string) => {
    switch (status) {
      case "complete":
        return "bg-green-100 text-green-800";
      case "partial":
        return "bg-yellow-100 text-yellow-800";
      case "unmapped":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const totalRecordsProcessed = syncJobs.reduce((sum, j) => sum + j.recordsProcessed, 0);
  const activeEndpoints = endpoints.filter((e) => e.status === "active").length;

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-gradient-to-br from-red-500 to-orange-500 rounded-lg flex items-center justify-center">
            <Heart className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold">Epic Integration</h1>
            <p className="text-muted-foreground">
              Configure FHIR R4, MyChart, and CDS Hooks connections
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline">
            <Download className="h-4 w-4 mr-2" />
            Export Config
          </Button>
          <Button>
            <RefreshCw className="h-4 w-4 mr-2" />
            Sync Now
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Server className="h-5 w-5 text-green-500" />
              <div>
                <p className="text-sm text-muted-foreground">Active Endpoints</p>
                <p className="text-2xl font-bold">{activeEndpoints}/{endpoints.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Database className="h-5 w-5 text-blue-500" />
              <div>
                <p className="text-sm text-muted-foreground">Records Synced</p>
                <p className="text-2xl font-bold">{totalRecordsProcessed.toLocaleString()}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Link2 className="h-5 w-5 text-purple-500" />
              <div>
                <p className="text-sm text-muted-foreground">Mapped Resources</p>
                <p className="text-2xl font-bold">
                  {resourceMappings.filter((r) => r.mappingStatus !== "unmapped").length}/{resourceMappings.length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-orange-500" />
              <div>
                <p className="text-sm text-muted-foreground">Last Sync</p>
                <p className="text-lg font-bold">10 min ago</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="connection">
        <TabsList>
          <TabsTrigger value="connection">
            <Shield className="h-4 w-4 mr-2" />
            Connection
          </TabsTrigger>
          <TabsTrigger value="endpoints">
            <Server className="h-4 w-4 mr-2" />
            Endpoints
          </TabsTrigger>
          <TabsTrigger value="mapping">
            <Link2 className="h-4 w-4 mr-2" />
            Resource Mapping
          </TabsTrigger>
          <TabsTrigger value="sync">
            <RefreshCw className="h-4 w-4 mr-2" />
            Sync Status
          </TabsTrigger>
        </TabsList>

        <TabsContent value="connection" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>OAuth 2.0 Configuration</CardTitle>
              <CardDescription>
                Configure SMART on FHIR authentication settings
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Client ID</Label>
                  <Input
                    value={config.clientId}
                    onChange={(e) => setConfig({ ...config, clientId: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Environment</Label>
                  <Select
                    value={config.environment}
                    onValueChange={(v) => setConfig({ ...config, environment: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="sandbox">Sandbox</SelectItem>
                      <SelectItem value="staging">Staging</SelectItem>
                      <SelectItem value="production">Production</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label>FHIR Base URL</Label>
                <Input
                  value={config.fhirBaseUrl}
                  onChange={(e) => setConfig({ ...config, fhirBaseUrl: e.target.value })}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Authorization URL</Label>
                  <Input
                    value={config.authUrl}
                    onChange={(e) => setConfig({ ...config, authUrl: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Token URL</Label>
                  <Input
                    value={config.tokenUrl}
                    onChange={(e) => setConfig({ ...config, tokenUrl: e.target.value })}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label>Scopes</Label>
                <Textarea
                  value={config.scope}
                  onChange={(e) => setConfig({ ...config, scope: e.target.value })}
                  rows={2}
                />
              </div>

              <div className="flex gap-4">
                <Button variant="outline">
                  <Key className="h-4 w-4 mr-2" />
                  Test Connection
                </Button>
                <Button>Save Configuration</Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Sync Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label>Automatic Sync</Label>
                  <p className="text-sm text-muted-foreground">
                    Enable automatic data synchronization
                  </p>
                </div>
                <Switch
                  checked={config.autoSync}
                  onCheckedChange={(c) => setConfig({ ...config, autoSync: c })}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Sync Interval</Label>
                  <Select
                    value={config.syncInterval}
                    onValueChange={(v) => setConfig({ ...config, syncInterval: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="realtime">Real-time</SelectItem>
                      <SelectItem value="hourly">Hourly</SelectItem>
                      <SelectItem value="daily">Daily</SelectItem>
                      <SelectItem value="weekly">Weekly</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Batch Size</Label>
                  <Input
                    type="number"
                    value={config.batchSize}
                    onChange={(e) =>
                      setConfig({ ...config, batchSize: parseInt(e.target.value) })
                    }
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="endpoints">
          <Card>
            <CardHeader>
              <CardTitle>Configured Endpoints</CardTitle>
              <CardDescription>
                Manage Epic integration endpoints and services
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Status</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Last Sync</TableHead>
                    <TableHead>Records</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {endpoints.map((endpoint) => (
                    <TableRow key={endpoint.id}>
                      <TableCell>{getStatusIcon(endpoint.status)}</TableCell>
                      <TableCell className="font-medium">{endpoint.name}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{endpoint.type}</Badge>
                      </TableCell>
                      <TableCell>{formatDate(endpoint.lastSync || "")}</TableCell>
                      <TableCell>{endpoint.syncCount?.toLocaleString() || "-"}</TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          <Button variant="ghost" size="sm">
                            <Settings className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm">
                            <RefreshCw className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="mapping">
          <Card>
            <CardHeader>
              <CardTitle>FHIR to OMOP Resource Mapping</CardTitle>
              <CardDescription>
                Configure how Epic FHIR resources map to OMOP CDM tables
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Accordion type="single" collapsible>
                {resourceMappings.map((mapping) => (
                  <AccordionItem key={mapping.epicResource} value={mapping.epicResource}>
                    <AccordionTrigger>
                      <div className="flex items-center gap-4 w-full">
                        <div className="flex items-center gap-2">
                          {mapping.epicResource === "Patient" && <Users className="h-4 w-4" />}
                          {mapping.epicResource === "MedicationRequest" && <Pill className="h-4 w-4" />}
                          {mapping.epicResource === "Observation" && <TestTube className="h-4 w-4" />}
                          {mapping.epicResource === "Condition" && <Stethoscope className="h-4 w-4" />}
                          {mapping.epicResource === "Procedure" && <Activity className="h-4 w-4" />}
                          {!["Patient", "MedicationRequest", "Observation", "Condition", "Procedure"].includes(mapping.epicResource) && <FileText className="h-4 w-4" />}
                          <span>{mapping.epicResource}</span>
                        </div>
                        <span className="text-muted-foreground">→</span>
                        <span className="text-muted-foreground">{mapping.omopTable}</span>
                        <Badge className={getMappingColor(mapping.mappingStatus)}>
                          {mapping.mappingStatus}
                        </Badge>
                        <span className="ml-auto text-sm text-muted-foreground">
                          {mapping.mappedFields}/{mapping.fieldCount} fields
                        </span>
                      </div>
                    </AccordionTrigger>
                    <AccordionContent>
                      <div className="p-4 space-y-4">
                        <Progress
                          value={(mapping.mappedFields / mapping.fieldCount) * 100}
                          className="h-2"
                        />
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <Label className="text-sm font-medium">Source Fields</Label>
                            <p className="text-sm text-muted-foreground">
                              {mapping.fieldCount} fields available in Epic FHIR
                            </p>
                          </div>
                          <div>
                            <Label className="text-sm font-medium">Mapped Fields</Label>
                            <p className="text-sm text-muted-foreground">
                              {mapping.mappedFields} fields mapped to OMOP
                            </p>
                          </div>
                        </div>
                        <Button variant="outline" size="sm">
                          Edit Mapping
                        </Button>
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="sync">
          <Card>
            <CardHeader>
              <CardTitle>Sync Jobs</CardTitle>
              <CardDescription>
                Monitor data synchronization progress
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Status</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Progress</TableHead>
                    <TableHead>Start Time</TableHead>
                    <TableHead>Records</TableHead>
                    <TableHead>Errors</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {syncJobs.map((job) => (
                    <TableRow key={job.id}>
                      <TableCell>{getStatusIcon(job.status)}</TableCell>
                      <TableCell className="font-medium">{job.type}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Progress value={job.progress} className="w-[100px] h-2" />
                          <span className="text-sm">{job.progress}%</span>
                        </div>
                      </TableCell>
                      <TableCell>{formatDate(job.startTime)}</TableCell>
                      <TableCell>{job.recordsProcessed.toLocaleString()}</TableCell>
                      <TableCell>
                        {job.errors > 0 ? (
                          <Badge variant="destructive">{job.errors}</Badge>
                        ) : (
                          <span className="text-muted-foreground">0</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {job.status === "running" && (
                          <Button variant="ghost" size="sm">
                            Pause
                          </Button>
                        )}
                        {job.status === "failed" && (
                          <Button variant="ghost" size="sm">
                            Retry
                          </Button>
                        )}
                        {job.status === "queued" && (
                          <Button variant="ghost" size="sm">
                            Start
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
