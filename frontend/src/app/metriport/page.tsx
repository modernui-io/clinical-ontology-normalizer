"use client";

import { useState } from "react";
import {
  useMetriportStatus,
  useMetriportPatients,
  useMetriportFacilities,
  useCreateMetriportPatient,
  useOnboardMetriportPatient,
  useStartDocumentQuery,
  useStartConsolidatedQuery,
} from "@/hooks/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Network,
  RefreshCw,
  CheckCircle,
  XCircle,
  Users,
  FileText,
  Building2,
  Plus,
  Zap,
  Activity,
  Globe,
} from "lucide-react";

export default function MetriportPage() {
  const [activeTab, setActiveTab] = useState("overview");
  const [showOnboardDialog, setShowOnboardDialog] = useState(false);
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null);

  // Queries
  const { data: status, isLoading: statusLoading, refetch: refetchStatus } = useMetriportStatus();
  const { data: patientsData, isLoading: patientsLoading, refetch: refetchPatients } = useMetriportPatients();
  const { data: facilitiesData, isLoading: facilitiesLoading } = useMetriportFacilities({
    enabled: !!status?.configured,
  });

  // Mutations
  const onboardMutation = useOnboardMetriportPatient();
  const docQueryMutation = useStartDocumentQuery();
  const consolidatedMutation = useStartConsolidatedQuery();

  const patients = (patientsData?.data?.patients as Record<string, unknown>[]) || [];
  const facilities = (facilitiesData?.data?.facilities as Record<string, unknown>[]) || [];

  // Form state for patient onboarding
  const [form, setForm] = useState({
    firstName: "",
    lastName: "",
    dob: "",
    genderAtBirth: "F",
    addressLine1: "",
    city: "",
    state: "",
    zip: "",
    phone: "",
    email: "",
    externalId: "",
  });

  const handleOnboard = () => {
    onboardMutation.mutate(
      {
        firstName: form.firstName,
        lastName: form.lastName,
        dob: form.dob,
        genderAtBirth: form.genderAtBirth,
        address: [
          {
            addressLine1: form.addressLine1,
            city: form.city,
            state: form.state,
            zip: form.zip,
          },
        ],
        contact: form.phone || form.email
          ? { phone: form.phone || undefined, email: form.email || undefined }
          : undefined,
        externalId: form.externalId || undefined,
      },
      {
        onSuccess: () => {
          setShowOnboardDialog(false);
          setForm({
            firstName: "",
            lastName: "",
            dob: "",
            genderAtBirth: "F",
            addressLine1: "",
            city: "",
            state: "",
            zip: "",
            phone: "",
            email: "",
            externalId: "",
          });
          refetchPatients();
        },
      }
    );
  };

  const handleDocQuery = (patientId: string) => {
    docQueryMutation.mutate({ patientId });
  };

  const handleConsolidatedQuery = (patientId: string) => {
    consolidatedMutation.mutate({ patientId });
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Network className="h-6 w-6" />
            HIE Integration
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Health Information Exchange via Metriport &mdash; Carequality, CommonWell, eHealth Exchange
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetchStatus()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Connection Status Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">API Connected</CardTitle>
            {status?.api_key_set ? (
              <CheckCircle className="h-4 w-4 text-green-500" />
            ) : (
              <XCircle className="h-4 w-4 text-red-500" />
            )}
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold">
              {statusLoading ? "..." : status?.api_key_set ? "Connected" : "Not Configured"}
            </div>
            <p className="text-xs text-muted-foreground mt-1">Metriport API Key</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Webhook</CardTitle>
            {status?.webhook_key_set ? (
              <CheckCircle className="h-4 w-4 text-green-500" />
            ) : (
              <XCircle className="h-4 w-4 text-yellow-500" />
            )}
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold">
              {statusLoading ? "..." : status?.webhook_key_set ? "Active" : "Not Set"}
            </div>
            <p className="text-xs text-muted-foreground mt-1">Signature verification</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Facility</CardTitle>
            <Building2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold">
              {statusLoading ? "..." : status?.facility_id_set ? "Configured" : "Not Set"}
            </div>
            <p className="text-xs text-muted-foreground mt-1">Default facility</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Environment</CardTitle>
            <Globe className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold">
              {statusLoading
                ? "..."
                : status?.base_url?.includes("sandbox")
                  ? "Sandbox"
                  : "Production"}
            </div>
            <p className="text-xs text-muted-foreground mt-1 truncate">
              {status?.base_url || "—"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="patients">Patients</TabsTrigger>
          <TabsTrigger value="facilities">Facilities</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            {/* How It Works */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">How HIE Integration Works</CardTitle>
                <CardDescription>
                  Metriport connects to nationwide Health Information Exchanges
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-start gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-600 font-semibold text-sm dark:bg-blue-900 dark:text-blue-300">
                    1
                  </div>
                  <div>
                    <p className="font-medium">Register Patient</p>
                    <p className="text-sm text-muted-foreground">
                      Create a patient in Metriport with demographics for identity matching
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-600 font-semibold text-sm dark:bg-blue-900 dark:text-blue-300">
                    2
                  </div>
                  <div>
                    <p className="font-medium">Query HIE Networks</p>
                    <p className="text-sm text-muted-foreground">
                      Automatically queries Carequality, CommonWell, and eHealth Exchange
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-600 font-semibold text-sm dark:bg-blue-900 dark:text-blue-300">
                    3
                  </div>
                  <div>
                    <p className="font-medium">Receive FHIR Data</p>
                    <p className="text-sm text-muted-foreground">
                      Documents and consolidated FHIR bundles arrive via webhooks
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-green-100 text-green-600 font-semibold text-sm dark:bg-green-900 dark:text-green-300">
                    4
                  </div>
                  <div>
                    <p className="font-medium">Automatic Import</p>
                    <p className="text-sm text-muted-foreground">
                      FHIR resources are automatically imported into the patient knowledge graph
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Quick Actions */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Quick Actions</CardTitle>
                <CardDescription>Common HIE operations</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Button
                  className="w-full justify-start"
                  variant="outline"
                  onClick={() => setShowOnboardDialog(true)}
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Onboard New Patient
                </Button>

                <Button
                  className="w-full justify-start"
                  variant="outline"
                  onClick={() => setActiveTab("patients")}
                >
                  <Users className="mr-2 h-4 w-4" />
                  View Registered Patients
                </Button>
                <Button
                  className="w-full justify-start"
                  variant="outline"
                  onClick={() => setActiveTab("facilities")}
                >
                  <Building2 className="mr-2 h-4 w-4" />
                  Manage Facilities
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* HIE Network Status */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Connected HIE Networks</CardTitle>
              <CardDescription>
                Networks queried when a patient document request is initiated
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-3">
                <div className="flex items-center gap-3 rounded-lg border p-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900">
                    <Network className="h-5 w-5 text-blue-600 dark:text-blue-300" />
                  </div>
                  <div>
                    <p className="font-medium">Carequality</p>
                    <p className="text-xs text-muted-foreground">
                      700+ participants including Epic, Cerner, Athena
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3 rounded-lg border p-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-purple-100 dark:bg-purple-900">
                    <Network className="h-5 w-5 text-purple-600 dark:text-purple-300" />
                  </div>
                  <div>
                    <p className="font-medium">CommonWell</p>
                    <p className="text-xs text-muted-foreground">
                      30,000+ provider sites, 200M+ patients
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3 rounded-lg border p-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-100 dark:bg-green-900">
                    <Network className="h-5 w-5 text-green-600 dark:text-green-300" />
                  </div>
                  <div>
                    <p className="font-medium">eHealth Exchange</p>
                    <p className="text-xs text-muted-foreground">
                      Federal agencies, VA, DoD, SSA
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Patients Tab */}
        <TabsContent value="patients" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Registered Patients</CardTitle>
                  <CardDescription>
                    Patients registered with Metriport for HIE queries
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => refetchPatients()}>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Refresh
                  </Button>
                  <Button size="sm" onClick={() => setShowOnboardDialog(true)}>
                    <Plus className="mr-2 h-4 w-4" />
                    Onboard Patient
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {!status?.configured ? (
                <div className="py-12 text-center">
                  <XCircle className="mx-auto h-12 w-12 text-muted-foreground/40" />
                  <p className="mt-4 text-muted-foreground">
                    Metriport is not configured. Set METRIPORT_API_KEY and METRIPORT_FACILITY_ID environment variables.
                  </p>
                </div>
              ) : patientsLoading ? (
                <div className="flex items-center justify-center py-12">
                  <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
                  <span className="ml-2 text-muted-foreground">Loading patients...</span>
                </div>
              ) : patients.length === 0 ? (
                <div className="py-12 text-center">
                  <Users className="mx-auto h-12 w-12 text-muted-foreground/40" />
                  <p className="mt-4 text-muted-foreground">
                    No patients registered yet. Onboard a patient to start querying HIE networks.
                  </p>
                </div>
              ) : (
                <div className="rounded-lg border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>DOB</TableHead>
                        <TableHead>Gender</TableHead>
                        <TableHead>Metriport ID</TableHead>
                        <TableHead>External ID</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {patients.map((patient) => (
                        <TableRow key={patient.id as string}>
                          <TableCell className="font-medium">
                            {patient.firstName as string} {patient.lastName as string}
                          </TableCell>
                          <TableCell>{patient.dob as string}</TableCell>
                          <TableCell>
                            <Badge variant="outline">
                              {patient.genderAtBirth as string}
                            </Badge>
                          </TableCell>
                          <TableCell className="font-mono text-xs">
                            {(patient.id as string)?.substring(0, 8)}...
                          </TableCell>
                          <TableCell className="text-muted-foreground">
                            {(patient.externalId as string) || "—"}
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end gap-1">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDocQuery(patient.id as string)}
                                disabled={docQueryMutation.isPending}
                                title="Query documents from HIE networks"
                              >
                                <FileText className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleConsolidatedQuery(patient.id as string)}
                                disabled={consolidatedMutation.isPending}
                                title="Query consolidated FHIR data"
                              >
                                <Activity className="h-4 w-4" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}

              {/* Mutation feedback */}
              {docQueryMutation.isSuccess && (
                <div className="mt-4 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200">
                  Document query started. Results will arrive via webhook.
                </div>
              )}
              {consolidatedMutation.isSuccess && (
                <div className="mt-4 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200">
                  Consolidated FHIR query started. Data will be imported automatically.
                </div>
              )}
              {(docQueryMutation.isError || consolidatedMutation.isError) && (
                <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
                  Query failed: {((docQueryMutation.error || consolidatedMutation.error) as Error)?.message}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Facilities Tab */}
        <TabsContent value="facilities" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Facilities</CardTitle>
              <CardDescription>
                Healthcare facilities registered with Metriport for data exchange
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!status?.configured ? (
                <div className="py-12 text-center">
                  <XCircle className="mx-auto h-12 w-12 text-muted-foreground/40" />
                  <p className="mt-4 text-muted-foreground">
                    Metriport is not configured.
                  </p>
                </div>
              ) : facilitiesLoading ? (
                <div className="flex items-center justify-center py-12">
                  <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
                  <span className="ml-2 text-muted-foreground">Loading facilities...</span>
                </div>
              ) : facilities.length === 0 ? (
                <div className="py-12 text-center">
                  <Building2 className="mx-auto h-12 w-12 text-muted-foreground/40" />
                  <p className="mt-4 text-muted-foreground">
                    No facilities found. Create a facility in the Metriport dashboard.
                  </p>
                </div>
              ) : (
                <div className="rounded-lg border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>NPI</TableHead>
                        <TableHead>Address</TableHead>
                        <TableHead>ID</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {facilities.map((facility, idx) => (
                        <TableRow key={(facility.id as string) || idx}>
                          <TableCell className="font-medium">
                            {(facility.name as string) || "Unnamed Facility"}
                          </TableCell>
                          <TableCell className="font-mono text-sm">
                            {(facility.npi as string) || "—"}
                          </TableCell>
                          <TableCell className="text-muted-foreground text-sm">
                            {facility.address
                              ? `${(facility.address as Record<string, string>).city}, ${(facility.address as Record<string, string>).state}`
                              : "—"}
                          </TableCell>
                          <TableCell className="font-mono text-xs">
                            {(facility.id as string)?.substring(0, 8)}...
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Onboard Patient Dialog — outside Tabs so it works from any tab */}
      <Dialog open={showOnboardDialog} onOpenChange={setShowOnboardDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Onboard Patient to HIE</DialogTitle>
            <DialogDescription>
              Register a patient and automatically query all HIE networks for their records.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="firstName">First Name</Label>
                <Input
                  id="firstName"
                  value={form.firstName}
                  onChange={(e) => setForm({ ...form, firstName: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="lastName">Last Name</Label>
                <Input
                  id="lastName"
                  value={form.lastName}
                  onChange={(e) => setForm({ ...form, lastName: e.target.value })}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="dob">Date of Birth</Label>
                <Input
                  id="dob"
                  type="date"
                  value={form.dob}
                  onChange={(e) => setForm({ ...form, dob: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="gender">Gender at Birth</Label>
                <select
                  id="gender"
                  value={form.genderAtBirth}
                  onChange={(e) => setForm({ ...form, genderAtBirth: e.target.value })}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="F">Female</option>
                  <option value="M">Male</option>
                </select>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="address">Address</Label>
              <Input
                id="address"
                placeholder="Street address"
                value={form.addressLine1}
                onChange={(e) => setForm({ ...form, addressLine1: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="city">City</Label>
                <Input
                  id="city"
                  value={form.city}
                  onChange={(e) => setForm({ ...form, city: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="state">State</Label>
                <Input
                  id="state"
                  maxLength={2}
                  placeholder="NY"
                  value={form.state}
                  onChange={(e) => setForm({ ...form, state: e.target.value.toUpperCase() })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="zip">ZIP</Label>
                <Input
                  id="zip"
                  maxLength={5}
                  value={form.zip}
                  onChange={(e) => setForm({ ...form, zip: e.target.value })}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="phone">Phone (optional)</Label>
                <Input
                  id="phone"
                  type="tel"
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="externalId">External ID (optional)</Label>
                <Input
                  id="externalId"
                  placeholder="Your internal patient ID"
                  value={form.externalId}
                  onChange={(e) => setForm({ ...form, externalId: e.target.value })}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowOnboardDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleOnboard}
              disabled={
                onboardMutation.isPending ||
                !form.firstName ||
                !form.lastName ||
                !form.dob ||
                !form.addressLine1 ||
                !form.city ||
                !form.state ||
                !form.zip
              }
            >
              {onboardMutation.isPending ? (
                <>
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  Onboarding...
                </>
              ) : (
                <>
                  <Zap className="mr-2 h-4 w-4" />
                  Onboard & Query
                </>
              )}
            </Button>
          </DialogFooter>
          {onboardMutation.isError && (
            <p className="text-sm text-red-500 mt-2">
              Error: {(onboardMutation.error as Error).message}
            </p>
          )}
          {onboardMutation.isSuccess && (
            <p className="text-sm text-green-600 mt-2">
              Patient onboarded successfully. HIE queries started.
            </p>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
