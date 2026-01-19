"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Activity,
  AlertCircle,
  ArrowRight,
  Building2,
  Calendar,
  CheckCircle,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Clock,
  Download,
  ExternalLink,
  Eye,
  FileText,
  Globe,
  History,
  Lock,
  Mail,
  MapPin,
  Network,
  RefreshCw,
  Search,
  Send,
  Server,
  Settings,
  Shield,
  User,
  Users,
  XCircle,
  Zap,
} from "lucide-react";

// Types
interface QHIN {
  id: string;
  name: string;
  description: string;
  status: "active" | "degraded" | "maintenance" | "offline";
  endpoint_url: string;
  supports_patient_discovery: boolean;
  supports_document_query: boolean;
  supports_document_retrieve: boolean;
  supports_direct_messaging: boolean;
  participant_count: number;
  coverage_states: string[];
  organization_types: string[];
  fhir_version: string;
  ihe_profiles: string[];
  average_response_time_ms: number;
}

interface PatientMatch {
  id: string;
  source_qhin: string;
  source_organization: string;
  confidence: "exact" | "high" | "probable" | "possible" | "low";
  confidence_score: number;
  family_name: string;
  given_name: string;
  birth_date: string | null;
  gender: string | null;
  address: string | null;
  mrn: string | null;
  document_count: number;
  last_updated: string | null;
}

interface DocumentReference {
  id: string;
  source_qhin: string;
  source_organization: string;
  document_type_display: string;
  document_class: string;
  title: string;
  author: string | null;
  facility: string | null;
  creation_date: string;
  size_bytes: number | null;
  status: string;
}

interface AuditLogEntry {
  id: string;
  timestamp: string;
  event_type: string;
  user_id: string;
  action: string;
  outcome: string;
  purpose_of_use: string;
  patient_id: string | null;
  qhins_queried: string[];
  documents_accessed: string[];
}

interface PatientConsent {
  id: string;
  patient_id: string;
  status: "active" | "denied" | "not_asked" | "expired" | "pending";
  scope: string[];
  includes_sensitive: boolean;
  effective_date: string | null;
  expiration_date: string | null;
  excluded_organizations: string[];
}

// Mock Data
const mockQHINs: QHIN[] = [
  {
    id: "epic-carequality",
    name: "Epic via Carequality",
    description: "Epic's nationwide health information network connecting Epic-based organizations through Carequality",
    status: "active",
    endpoint_url: "https://carequality.epic.com/fhir",
    supports_patient_discovery: true,
    supports_document_query: true,
    supports_document_retrieve: true,
    supports_direct_messaging: true,
    participant_count: 4500,
    coverage_states: ["ALL"],
    organization_types: ["Hospital", "Health System", "Physician Practice"],
    fhir_version: "R4",
    ihe_profiles: ["PDQm", "MHD", "XCA", "XDS.b"],
    average_response_time_ms: 250,
  },
  {
    id: "commonwell",
    name: "CommonWell Health Alliance",
    description: "National health data exchange network connecting diverse EHR systems",
    status: "active",
    endpoint_url: "https://api.commonwellalliance.org",
    supports_patient_discovery: true,
    supports_document_query: true,
    supports_document_retrieve: true,
    supports_direct_messaging: true,
    participant_count: 35000,
    coverage_states: ["ALL"],
    organization_types: ["Hospital", "Ambulatory", "Post-Acute", "Labs"],
    fhir_version: "R4",
    ihe_profiles: ["PDQm", "MHD", "XCA", "XDS.b"],
    average_response_time_ms: 300,
  },
  {
    id: "carequality",
    name: "Carequality",
    description: "Interoperability framework enabling nationwide exchange across organizations",
    status: "active",
    endpoint_url: "https://hub.carequality.org",
    supports_patient_discovery: true,
    supports_document_query: true,
    supports_document_retrieve: true,
    supports_direct_messaging: true,
    participant_count: 70000,
    coverage_states: ["ALL"],
    organization_types: ["Hospital", "Health System", "HIE", "Payer"],
    fhir_version: "R4",
    ihe_profiles: ["PDQm", "MHD", "XCA", "XDS.b", "XCPD"],
    average_response_time_ms: 350,
  },
  {
    id: "ehealth-exchange",
    name: "eHealth Exchange",
    description: "Largest health information network serving federal, state, and private organizations",
    status: "active",
    endpoint_url: "https://gateway.ehealthexchange.org",
    supports_patient_discovery: true,
    supports_document_query: true,
    supports_document_retrieve: true,
    supports_direct_messaging: true,
    participant_count: 180,
    coverage_states: ["ALL"],
    organization_types: ["Federal", "State", "VA", "DoD", "SSA", "CMS"],
    fhir_version: "R4",
    ihe_profiles: ["PDQm", "MHD", "XCA", "XDS.b", "XCPD"],
    average_response_time_ms: 400,
  },
  {
    id: "healthgorilla",
    name: "Health Gorilla",
    description: "Clinical data network connecting labs, imaging centers, and healthcare facilities",
    status: "active",
    endpoint_url: "https://api.healthgorilla.com",
    supports_patient_discovery: true,
    supports_document_query: true,
    supports_document_retrieve: true,
    supports_direct_messaging: true,
    participant_count: 5000,
    coverage_states: ["ALL"],
    organization_types: ["Labs", "Imaging", "Specialty", "Primary Care"],
    fhir_version: "R4",
    ihe_profiles: ["PDQm", "MHD"],
    average_response_time_ms: 200,
  },
  {
    id: "surescripts",
    name: "Surescripts",
    description: "National network for medication history and e-prescribing information",
    status: "active",
    endpoint_url: "https://api.surescripts.net",
    supports_patient_discovery: false,
    supports_document_query: true,
    supports_document_retrieve: true,
    supports_direct_messaging: false,
    participant_count: 1500000,
    coverage_states: ["ALL"],
    organization_types: ["Pharmacy", "PBM", "Hospital", "Prescriber"],
    fhir_version: "R4",
    ihe_profiles: ["MHD"],
    average_response_time_ms: 150,
  },
  {
    id: "konza-hie",
    name: "Konza National Network (KHIN)",
    description: "Regional QHIN serving Kansas and surrounding areas",
    status: "degraded",
    endpoint_url: "https://gateway.konzanetwork.org",
    supports_patient_discovery: true,
    supports_document_query: true,
    supports_document_retrieve: true,
    supports_direct_messaging: true,
    participant_count: 450,
    coverage_states: ["KS", "MO", "NE", "OK"],
    organization_types: ["Hospital", "Rural Health", "Federally Qualified"],
    fhir_version: "R4",
    ihe_profiles: ["PDQm", "MHD", "XDS.b"],
    average_response_time_ms: 500,
  },
  {
    id: "medicity",
    name: "Medicity (Aetna/CVS)",
    description: "Health information exchange network connecting payer and provider data",
    status: "active",
    endpoint_url: "https://api.medicity.com",
    supports_patient_discovery: true,
    supports_document_query: true,
    supports_document_retrieve: true,
    supports_direct_messaging: true,
    participant_count: 2500,
    coverage_states: ["ALL"],
    organization_types: ["Payer", "Hospital", "Ambulatory"],
    fhir_version: "R4",
    ihe_profiles: ["PDQm", "MHD", "XCA"],
    average_response_time_ms: 280,
  },
];

const mockPatientMatches: PatientMatch[] = [
  {
    id: "pt-a1b2c3d4",
    source_qhin: "epic-carequality",
    source_organization: "Massachusetts General Hospital",
    confidence: "exact",
    confidence_score: 0.98,
    family_name: "Smith",
    given_name: "John",
    birth_date: "1965-03-15",
    gender: "male",
    address: "Boston, MA",
    mrn: "MRN0012345",
    document_count: 42,
    last_updated: "2026-01-15T10:30:00Z",
  },
  {
    id: "pt-e5f6g7h8",
    source_qhin: "commonwell",
    source_organization: "Cleveland Clinic",
    confidence: "high",
    confidence_score: 0.89,
    family_name: "Smith",
    given_name: "John",
    birth_date: "1965-03-15",
    gender: "male",
    address: "Cleveland, OH",
    mrn: "MRN0098765",
    document_count: 28,
    last_updated: "2026-01-10T14:22:00Z",
  },
  {
    id: "pt-i9j0k1l2",
    source_qhin: "carequality",
    source_organization: "Mayo Clinic - Rochester",
    confidence: "probable",
    confidence_score: 0.75,
    family_name: "Smith",
    given_name: "John R",
    birth_date: "1965-03-15",
    gender: "male",
    address: "Rochester, MN",
    mrn: "MRN0054321",
    document_count: 15,
    last_updated: "2025-12-20T08:45:00Z",
  },
];

const mockDocuments: DocumentReference[] = [
  {
    id: "doc-001",
    source_qhin: "epic-carequality",
    source_organization: "Massachusetts General Hospital",
    document_type_display: "Continuity of Care Document",
    document_class: "CCD",
    title: "CCD - 2026-01-15",
    author: "Dr. Sarah Johnson",
    facility: "MGH Primary Care",
    creation_date: "2026-01-15T10:30:00Z",
    size_bytes: 245678,
    status: "current",
  },
  {
    id: "doc-002",
    source_qhin: "epic-carequality",
    source_organization: "Massachusetts General Hospital",
    document_type_display: "Discharge Summary",
    document_class: "DISCHARGE",
    title: "Discharge Summary - Cardiac Care Unit",
    author: "Dr. Michael Chen",
    facility: "MGH Cardiac Care",
    creation_date: "2025-12-20T16:45:00Z",
    size_bytes: 128456,
    status: "current",
  },
  {
    id: "doc-003",
    source_qhin: "epic-carequality",
    source_organization: "Massachusetts General Hospital",
    document_type_display: "Progress Note",
    document_class: "PROGRESS",
    title: "Cardiology Follow-up Visit",
    author: "Dr. Emily Martinez",
    facility: "MGH Cardiology",
    creation_date: "2026-01-08T09:15:00Z",
    size_bytes: 45230,
    status: "current",
  },
  {
    id: "doc-004",
    source_qhin: "epic-carequality",
    source_organization: "Massachusetts General Hospital",
    document_type_display: "Laboratory Report",
    document_class: "LAB",
    title: "Comprehensive Metabolic Panel",
    author: "Lab Services",
    facility: "MGH Laboratory",
    creation_date: "2026-01-14T07:30:00Z",
    size_bytes: 32100,
    status: "current",
  },
  {
    id: "doc-005",
    source_qhin: "epic-carequality",
    source_organization: "Massachusetts General Hospital",
    document_type_display: "Diagnostic Imaging",
    document_class: "IMAGING",
    title: "Chest X-Ray PA and Lateral",
    author: "Dr. Robert Williams",
    facility: "MGH Radiology",
    creation_date: "2025-11-30T11:20:00Z",
    size_bytes: 89450,
    status: "current",
  },
];

const mockAuditLogs: AuditLogEntry[] = [
  {
    id: "audit-001",
    timestamp: "2026-01-19T14:32:15Z",
    event_type: "patient_record_query",
    user_id: "user-001",
    action: "Patient Discovery Query",
    outcome: "success",
    purpose_of_use: "treatment",
    patient_id: null,
    qhins_queried: ["epic-carequality", "commonwell", "carequality"],
    documents_accessed: [],
  },
  {
    id: "audit-002",
    timestamp: "2026-01-19T14:30:45Z",
    event_type: "document_query",
    user_id: "user-001",
    action: "Document Query",
    outcome: "success",
    purpose_of_use: "treatment",
    patient_id: "pt-a1b2c3d4",
    qhins_queried: ["epic-carequality"],
    documents_accessed: [],
  },
  {
    id: "audit-003",
    timestamp: "2026-01-19T14:28:10Z",
    event_type: "document_retrieve",
    user_id: "user-001",
    action: "Document Retrieve",
    outcome: "success",
    purpose_of_use: "treatment",
    patient_id: "pt-a1b2c3d4",
    qhins_queried: ["epic-carequality"],
    documents_accessed: ["doc-001", "doc-002"],
  },
];

const mockConsent: PatientConsent = {
  id: "consent-pt-a1b2c3d4",
  patient_id: "pt-a1b2c3d4",
  status: "active",
  scope: ["treatment", "payment", "healthcare_operations"],
  includes_sensitive: false,
  effective_date: "2025-01-01T00:00:00Z",
  expiration_date: "2027-01-01T00:00:00Z",
  excluded_organizations: [],
};

// Helper Functions
const getStatusColor = (status: string) => {
  switch (status) {
    case "active":
      return "bg-green-500 text-white";
    case "degraded":
      return "bg-amber-500 text-white";
    case "maintenance":
      return "bg-blue-500 text-white";
    case "offline":
      return "bg-red-500 text-white";
    default:
      return "bg-gray-500 text-white";
  }
};

const getConfidenceColor = (confidence: string) => {
  switch (confidence) {
    case "exact":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
    case "high":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
    case "probable":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
    case "possible":
      return "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200";
    case "low":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
    default:
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
  }
};

const getConsentStatusColor = (status: string) => {
  switch (status) {
    case "active":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
    case "denied":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
    case "not_asked":
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
    case "expired":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
    case "pending":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
    default:
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
  }
};

const formatBytes = (bytes: number | null): string => {
  if (bytes === null) return "Unknown";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const formatDate = (dateStr: string | null): string => {
  if (!dateStr) return "Unknown";
  return new Date(dateStr).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
};

const formatDateTime = (dateStr: string): string => {
  return new Date(dateStr).toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

export default function ExchangePage() {
  const [activeTab, setActiveTab] = useState("networks");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedQHIN, setSelectedQHIN] = useState<QHIN | null>(null);
  const [showQHINDetails, setShowQHINDetails] = useState(false);

  // Patient Search State
  const [searchFamilyName, setSearchFamilyName] = useState("");
  const [searchGivenName, setSearchGivenName] = useState("");
  const [searchDOB, setSearchDOB] = useState("");
  const [searchGender, setSearchGender] = useState("");
  const [searchState, setSearchState] = useState("");
  const [searchZip, setSearchZip] = useState("");
  const [patientMatches, setPatientMatches] = useState<PatientMatch[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState<PatientMatch | null>(null);

  // Documents State
  const [documents, setDocuments] = useState<DocumentReference[]>([]);
  const [selectedDocuments, setSelectedDocuments] = useState<Set<string>>(new Set());
  const [showDocumentPreview, setShowDocumentPreview] = useState(false);
  const [previewDocument, setPreviewDocument] = useState<DocumentReference | null>(null);

  // Messaging State
  const [messageRecipient, setMessageRecipient] = useState("");
  const [messageSubject, setMessageSubject] = useState("");
  const [messageBody, setMessageBody] = useState("");
  const [selectedQHINForMessage, setSelectedQHINForMessage] = useState("");

  // Audit Logs State
  const [auditLogs] = useState<AuditLogEntry[]>(mockAuditLogs);

  // Consent State
  const [consent, setConsent] = useState<PatientConsent | null>(null);

  // Stats
  const activeQHINs = mockQHINs.filter((q) => q.status === "active").length;
  const totalParticipants = mockQHINs.reduce((sum, q) => sum + q.participant_count, 0);

  const handlePatientSearch = async () => {
    if (!searchFamilyName) return;

    setIsLoading(true);
    setHasSearched(true);

    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 1500));

    setPatientMatches(mockPatientMatches);
    setIsLoading(false);
  };

  const handleSelectPatient = async (patient: PatientMatch) => {
    setSelectedPatient(patient);
    setIsLoading(true);

    // Simulate document query
    await new Promise((resolve) => setTimeout(resolve, 1000));

    setDocuments(mockDocuments);
    setConsent(mockConsent);
    setIsLoading(false);
    setActiveTab("documents");
  };

  const handleToggleDocument = (docId: string) => {
    const newSelected = new Set(selectedDocuments);
    if (newSelected.has(docId)) {
      newSelected.delete(docId);
    } else {
      newSelected.add(docId);
    }
    setSelectedDocuments(newSelected);
  };

  const handleRetrieveDocuments = async () => {
    if (selectedDocuments.size === 0) return;

    setIsLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 1500));
    setIsLoading(false);

    alert(`Retrieved ${selectedDocuments.size} documents successfully!`);
  };

  const handleSendMessage = async () => {
    if (!messageRecipient || !messageSubject || !messageBody || !selectedQHINForMessage) {
      alert("Please fill in all required fields");
      return;
    }

    setIsLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setIsLoading(false);

    alert("Message sent successfully!");
    setMessageRecipient("");
    setMessageSubject("");
    setMessageBody("");
    setSelectedQHINForMessage("");
  };

  const handleRefresh = async () => {
    setIsLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setIsLoading(false);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Network className="h-6 w-6" />
            Health Information Exchange
          </h1>
          <p className="text-muted-foreground">
            TEFCA-enabled exchange with Qualified Health Information Networks (QHINs)
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={isLoading}
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Active QHINs</CardTitle>
            <Server className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{activeQHINs}</div>
            <p className="text-xs text-muted-foreground">
              of {mockQHINs.length} networks
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Connected Organizations</CardTitle>
            <Building2 className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {totalParticipants.toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">Participating facilities</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Patient Matches</CardTitle>
            <Users className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{patientMatches.length}</div>
            <p className="text-xs text-muted-foreground">
              {hasSearched ? "From last search" : "No search yet"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Documents Available</CardTitle>
            <FileText className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{documents.length}</div>
            <p className="text-xs text-muted-foreground">
              {selectedPatient ? "For selected patient" : "Select a patient"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-6">
          <TabsTrigger value="networks" className="flex items-center gap-1">
            <Globe className="h-4 w-4" />
            <span className="hidden sm:inline">Networks</span>
          </TabsTrigger>
          <TabsTrigger value="search" className="flex items-center gap-1">
            <Search className="h-4 w-4" />
            <span className="hidden sm:inline">Patient Search</span>
          </TabsTrigger>
          <TabsTrigger value="documents" className="flex items-center gap-1">
            <FileText className="h-4 w-4" />
            <span className="hidden sm:inline">Documents</span>
          </TabsTrigger>
          <TabsTrigger value="messaging" className="flex items-center gap-1">
            <Mail className="h-4 w-4" />
            <span className="hidden sm:inline">Messaging</span>
          </TabsTrigger>
          <TabsTrigger value="audit" className="flex items-center gap-1">
            <History className="h-4 w-4" />
            <span className="hidden sm:inline">Audit Log</span>
          </TabsTrigger>
          <TabsTrigger value="consent" className="flex items-center gap-1">
            <Shield className="h-4 w-4" />
            <span className="hidden sm:inline">Consent</span>
          </TabsTrigger>
        </TabsList>

        {/* Networks Tab */}
        <TabsContent value="networks" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Qualified Health Information Networks</CardTitle>
              <CardDescription>
                Connected QHINs for nationwide health information exchange
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {mockQHINs.map((qhin) => (
                  <Card
                    key={qhin.id}
                    className="cursor-pointer hover:shadow-md transition-shadow"
                    onClick={() => {
                      setSelectedQHIN(qhin);
                      setShowQHINDetails(true);
                    }}
                  >
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <Badge className={getStatusColor(qhin.status)}>
                          {qhin.status}
                        </Badge>
                        <div className="flex items-center gap-1 text-muted-foreground">
                          <Zap className="h-3 w-3" />
                          <span className="text-xs">{qhin.average_response_time_ms}ms</span>
                        </div>
                      </div>
                      <CardTitle className="text-base mt-2">{qhin.name}</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      <p className="text-xs text-muted-foreground line-clamp-2">
                        {qhin.description}
                      </p>
                      <div className="flex items-center gap-2 text-xs">
                        <Building2 className="h-3 w-3" />
                        <span>{qhin.participant_count.toLocaleString()} participants</span>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {qhin.supports_patient_discovery && (
                          <Badge variant="outline" className="text-xs px-1 py-0">
                            PDQm
                          </Badge>
                        )}
                        {qhin.supports_document_query && (
                          <Badge variant="outline" className="text-xs px-1 py-0">
                            MHD
                          </Badge>
                        )}
                        {qhin.supports_direct_messaging && (
                          <Badge variant="outline" className="text-xs px-1 py-0">
                            Direct
                          </Badge>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Patient Search Tab */}
        <TabsContent value="search" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Search className="h-5 w-5" />
                Patient Discovery
              </CardTitle>
              <CardDescription>
                Search for patient records across all connected QHINs (IHE PDQm)
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="family-name">Family Name *</Label>
                  <Input
                    id="family-name"
                    placeholder="Smith"
                    value={searchFamilyName}
                    onChange={(e) => setSearchFamilyName(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="given-name">Given Name</Label>
                  <Input
                    id="given-name"
                    placeholder="John"
                    value={searchGivenName}
                    onChange={(e) => setSearchGivenName(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="dob">Date of Birth</Label>
                  <Input
                    id="dob"
                    type="date"
                    value={searchDOB}
                    onChange={(e) => setSearchDOB(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="gender">Gender</Label>
                  <select
                    id="gender"
                    value={searchGender}
                    onChange={(e) => setSearchGender(e.target.value)}
                    className="w-full h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                  >
                    <option value="">Any</option>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="state">State</Label>
                  <Input
                    id="state"
                    placeholder="MA"
                    maxLength={2}
                    value={searchState}
                    onChange={(e) => setSearchState(e.target.value.toUpperCase())}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="zip">ZIP Code</Label>
                  <Input
                    id="zip"
                    placeholder="02114"
                    value={searchZip}
                    onChange={(e) => setSearchZip(e.target.value)}
                  />
                </div>
              </div>
              <div className="flex justify-end">
                <Button
                  onClick={handlePatientSearch}
                  disabled={!searchFamilyName || isLoading}
                >
                  {isLoading ? (
                    <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Search className="mr-2 h-4 w-4" />
                  )}
                  Search QHINs
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Search Results */}
          {hasSearched && (
            <Card>
              <CardHeader>
                <CardTitle>Search Results</CardTitle>
                <CardDescription>
                  {patientMatches.length} patient matches found across QHINs
                </CardDescription>
              </CardHeader>
              <CardContent>
                {patientMatches.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <Users className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>No patient matches found</p>
                    <p className="text-sm">Try adjusting your search criteria</p>
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Patient</TableHead>
                        <TableHead>Source</TableHead>
                        <TableHead>Confidence</TableHead>
                        <TableHead>Documents</TableHead>
                        <TableHead>Last Updated</TableHead>
                        <TableHead></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {patientMatches.map((match) => (
                        <TableRow key={match.id}>
                          <TableCell>
                            <div>
                              <div className="font-medium">
                                {match.given_name} {match.family_name}
                              </div>
                              <div className="text-xs text-muted-foreground">
                                DOB: {formatDate(match.birth_date)} | {match.gender}
                              </div>
                              {match.address && (
                                <div className="text-xs text-muted-foreground flex items-center gap-1">
                                  <MapPin className="h-3 w-3" />
                                  {match.address}
                                </div>
                              )}
                            </div>
                          </TableCell>
                          <TableCell>
                            <div>
                              <div className="font-medium text-sm">{match.source_organization}</div>
                              <div className="text-xs text-muted-foreground">
                                via {mockQHINs.find((q) => q.id === match.source_qhin)?.name}
                              </div>
                              {match.mrn && (
                                <div className="text-xs text-muted-foreground">
                                  MRN: {match.mrn}
                                </div>
                              )}
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex flex-col gap-1">
                              <Badge className={getConfidenceColor(match.confidence)}>
                                {match.confidence}
                              </Badge>
                              <span className="text-xs text-muted-foreground">
                                {(match.confidence_score * 100).toFixed(0)}%
                              </span>
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-1">
                              <FileText className="h-4 w-4 text-muted-foreground" />
                              <span>{match.document_count}</span>
                            </div>
                          </TableCell>
                          <TableCell>
                            <span className="text-sm">
                              {formatDate(match.last_updated)}
                            </span>
                          </TableCell>
                          <TableCell>
                            <Button
                              size="sm"
                              onClick={() => handleSelectPatient(match)}
                            >
                              <Eye className="h-4 w-4 mr-1" />
                              View
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Documents Tab */}
        <TabsContent value="documents" className="space-y-4">
          {selectedPatient ? (
            <>
              {/* Selected Patient Info */}
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        <User className="h-5 w-5" />
                        {selectedPatient.given_name} {selectedPatient.family_name}
                      </CardTitle>
                      <CardDescription>
                        {selectedPatient.source_organization} | MRN: {selectedPatient.mrn}
                      </CardDescription>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setSelectedPatient(null);
                        setDocuments([]);
                        setActiveTab("search");
                      }}
                    >
                      <ChevronLeft className="h-4 w-4 mr-1" />
                      Back to Search
                    </Button>
                  </div>
                </CardHeader>
              </Card>

              {/* Document List */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle>Available Documents</CardTitle>
                      <CardDescription>
                        {documents.length} documents from {selectedPatient.source_organization}
                      </CardDescription>
                    </div>
                    <Button
                      onClick={handleRetrieveDocuments}
                      disabled={selectedDocuments.size === 0 || isLoading}
                    >
                      {isLoading ? (
                        <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <Download className="mr-2 h-4 w-4" />
                      )}
                      Retrieve Selected ({selectedDocuments.size})
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[50px]">
                          <input
                            type="checkbox"
                            checked={selectedDocuments.size === documents.length}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedDocuments(new Set(documents.map((d) => d.id)));
                              } else {
                                setSelectedDocuments(new Set());
                              }
                            }}
                            className="h-4 w-4"
                          />
                        </TableHead>
                        <TableHead>Document</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Author</TableHead>
                        <TableHead>Date</TableHead>
                        <TableHead>Size</TableHead>
                        <TableHead></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {documents.map((doc) => (
                        <TableRow key={doc.id}>
                          <TableCell>
                            <input
                              type="checkbox"
                              checked={selectedDocuments.has(doc.id)}
                              onChange={() => handleToggleDocument(doc.id)}
                              className="h-4 w-4"
                            />
                          </TableCell>
                          <TableCell>
                            <div>
                              <div className="font-medium">{doc.title}</div>
                              <div className="text-xs text-muted-foreground">
                                {doc.facility}
                              </div>
                            </div>
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">{doc.document_type_display}</Badge>
                          </TableCell>
                          <TableCell>
                            <span className="text-sm">{doc.author || "Unknown"}</span>
                          </TableCell>
                          <TableCell>
                            <span className="text-sm">{formatDate(doc.creation_date)}</span>
                          </TableCell>
                          <TableCell>
                            <span className="text-sm">{formatBytes(doc.size_bytes)}</span>
                          </TableCell>
                          <TableCell>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                setPreviewDocument(doc);
                                setShowDocumentPreview(true);
                              }}
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </>
          ) : (
            <Card>
              <CardContent className="py-12">
                <div className="text-center text-muted-foreground">
                  <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>No patient selected</p>
                  <p className="text-sm">Search for a patient first to view documents</p>
                  <Button
                    className="mt-4"
                    variant="outline"
                    onClick={() => setActiveTab("search")}
                  >
                    <Search className="h-4 w-4 mr-2" />
                    Go to Patient Search
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Messaging Tab */}
        <TabsContent value="messaging" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Mail className="h-5 w-5" />
                Direct Secure Message
              </CardTitle>
              <CardDescription>
                Send secure messages to providers through Direct messaging protocol
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="recipient-qhin">Target QHIN *</Label>
                  <select
                    id="recipient-qhin"
                    value={selectedQHINForMessage}
                    onChange={(e) => setSelectedQHINForMessage(e.target.value)}
                    className="w-full h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                  >
                    <option value="">Select QHIN...</option>
                    {mockQHINs
                      .filter((q) => q.supports_direct_messaging && q.status === "active")
                      .map((q) => (
                        <option key={q.id} value={q.id}>
                          {q.name}
                        </option>
                      ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="recipient">Recipient Direct Address *</Label>
                  <Input
                    id="recipient"
                    type="email"
                    placeholder="provider@direct.healthcare.org"
                    value={messageRecipient}
                    onChange={(e) => setMessageRecipient(e.target.value)}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="subject">Subject *</Label>
                <Input
                  id="subject"
                  placeholder="Patient referral for John Smith"
                  value={messageSubject}
                  onChange={(e) => setMessageSubject(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="body">Message Body *</Label>
                <Textarea
                  id="body"
                  placeholder="Enter your secure message..."
                  rows={6}
                  value={messageBody}
                  onChange={(e) => setMessageBody(e.target.value)}
                />
              </div>
              <div className="flex justify-end">
                <Button
                  onClick={handleSendMessage}
                  disabled={!messageRecipient || !messageSubject || !messageBody || !selectedQHINForMessage || isLoading}
                >
                  {isLoading ? (
                    <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="mr-2 h-4 w-4" />
                  )}
                  Send Message
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Audit Log Tab */}
        <TabsContent value="audit" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <History className="h-5 w-5" />
                Exchange Audit Log
              </CardTitle>
              <CardDescription>
                ATNA-compliant audit trail for all TEFCA exchange activities
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Timestamp</TableHead>
                    <TableHead>Event</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Purpose</TableHead>
                    <TableHead>Patient</TableHead>
                    <TableHead>QHINs</TableHead>
                    <TableHead>Outcome</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {auditLogs.map((log) => (
                    <TableRow key={log.id}>
                      <TableCell>
                        <span className="text-sm">{formatDateTime(log.timestamp)}</span>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{log.event_type.replace("_", " ")}</Badge>
                      </TableCell>
                      <TableCell>
                        <span className="text-sm">{log.action}</span>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary">{log.purpose_of_use}</Badge>
                      </TableCell>
                      <TableCell>
                        <span className="text-sm font-mono">
                          {log.patient_id || "-"}
                        </span>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {log.qhins_queried.slice(0, 2).map((qhin) => (
                            <Badge key={qhin} variant="outline" className="text-xs">
                              {qhin.split("-")[0]}
                            </Badge>
                          ))}
                          {log.qhins_queried.length > 2 && (
                            <Badge variant="outline" className="text-xs">
                              +{log.qhins_queried.length - 2}
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        {log.outcome === "success" ? (
                          <CheckCircle className="h-4 w-4 text-green-500" />
                        ) : (
                          <XCircle className="h-4 w-4 text-red-500" />
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Consent Tab */}
        <TabsContent value="consent" className="space-y-4">
          {selectedPatient && consent ? (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Shield className="h-5 w-5" />
                      Patient Consent
                    </CardTitle>
                    <CardDescription>
                      Health information exchange consent for {selectedPatient.given_name}{" "}
                      {selectedPatient.family_name}
                    </CardDescription>
                  </div>
                  <Badge className={getConsentStatusColor(consent.status)}>
                    {consent.status}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label className="text-sm font-medium">Patient ID</Label>
                    <p className="text-sm font-mono">{consent.patient_id}</p>
                  </div>
                  <div className="space-y-2">
                    <Label className="text-sm font-medium">Consent ID</Label>
                    <p className="text-sm font-mono">{consent.id}</p>
                  </div>
                  <div className="space-y-2">
                    <Label className="text-sm font-medium">Effective Date</Label>
                    <p className="text-sm">{formatDate(consent.effective_date)}</p>
                  </div>
                  <div className="space-y-2">
                    <Label className="text-sm font-medium">Expiration Date</Label>
                    <p className="text-sm">{formatDate(consent.expiration_date)}</p>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-sm font-medium">Permitted Purposes</Label>
                  <div className="flex flex-wrap gap-2">
                    {consent.scope.map((purpose) => (
                      <Badge key={purpose} variant="secondary">
                        {purpose.replace("_", " ")}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Lock className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm">
                    Sensitive records: {consent.includes_sensitive ? "Included" : "Excluded"}
                  </span>
                </div>

                {consent.excluded_organizations.length > 0 && (
                  <div className="space-y-2">
                    <Label className="text-sm font-medium">Excluded Organizations</Label>
                    <div className="flex flex-wrap gap-2">
                      {consent.excluded_organizations.map((org) => (
                        <Badge key={org} variant="destructive">
                          {org}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="py-12">
                <div className="text-center text-muted-foreground">
                  <Shield className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>No patient selected</p>
                  <p className="text-sm">Search for a patient first to view consent status</p>
                  <Button
                    className="mt-4"
                    variant="outline"
                    onClick={() => setActiveTab("search")}
                  >
                    <Search className="h-4 w-4 mr-2" />
                    Go to Patient Search
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      {/* QHIN Details Dialog */}
      <Dialog open={showQHINDetails} onOpenChange={setShowQHINDetails}>
        <DialogContent className="max-w-2xl">
          {selectedQHIN && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  {selectedQHIN.name}
                  <Badge className={getStatusColor(selectedQHIN.status)}>
                    {selectedQHIN.status}
                  </Badge>
                </DialogTitle>
                <DialogDescription>{selectedQHIN.description}</DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Endpoint URL</Label>
                    <p className="text-sm font-mono">{selectedQHIN.endpoint_url}</p>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">FHIR Version</Label>
                    <p className="text-sm">{selectedQHIN.fhir_version}</p>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Participants</Label>
                    <p className="text-sm">{selectedQHIN.participant_count.toLocaleString()}</p>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Avg Response Time</Label>
                    <p className="text-sm">{selectedQHIN.average_response_time_ms}ms</p>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">Capabilities</Label>
                  <div className="flex flex-wrap gap-2">
                    {selectedQHIN.supports_patient_discovery && (
                      <Badge variant="outline">
                        <Users className="h-3 w-3 mr-1" />
                        Patient Discovery
                      </Badge>
                    )}
                    {selectedQHIN.supports_document_query && (
                      <Badge variant="outline">
                        <Search className="h-3 w-3 mr-1" />
                        Document Query
                      </Badge>
                    )}
                    {selectedQHIN.supports_document_retrieve && (
                      <Badge variant="outline">
                        <Download className="h-3 w-3 mr-1" />
                        Document Retrieve
                      </Badge>
                    )}
                    {selectedQHIN.supports_direct_messaging && (
                      <Badge variant="outline">
                        <Mail className="h-3 w-3 mr-1" />
                        Direct Messaging
                      </Badge>
                    )}
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">IHE Profiles</Label>
                  <div className="flex flex-wrap gap-1">
                    {selectedQHIN.ihe_profiles.map((profile) => (
                      <Badge key={profile} variant="secondary" className="text-xs">
                        {profile}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">Organization Types</Label>
                  <div className="flex flex-wrap gap-1">
                    {selectedQHIN.organization_types.map((type) => (
                      <Badge key={type} variant="outline" className="text-xs">
                        {type}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">Coverage</Label>
                  <p className="text-sm">
                    {selectedQHIN.coverage_states.includes("ALL")
                      ? "Nationwide (All 50 states)"
                      : selectedQHIN.coverage_states.join(", ")}
                  </p>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setShowQHINDetails(false)}>
                  Close
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* Document Preview Dialog */}
      <Dialog open={showDocumentPreview} onOpenChange={setShowDocumentPreview}>
        <DialogContent className="max-w-2xl">
          {previewDocument && (
            <>
              <DialogHeader>
                <DialogTitle>{previewDocument.title}</DialogTitle>
                <DialogDescription>
                  {previewDocument.document_type_display} from {previewDocument.source_organization}
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Author</Label>
                    <p className="text-sm">{previewDocument.author || "Unknown"}</p>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Facility</Label>
                    <p className="text-sm">{previewDocument.facility || "Unknown"}</p>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Creation Date</Label>
                    <p className="text-sm">{formatDateTime(previewDocument.creation_date)}</p>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Size</Label>
                    <p className="text-sm">{formatBytes(previewDocument.size_bytes)}</p>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Document ID</Label>
                    <p className="text-sm font-mono">{previewDocument.id}</p>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Status</Label>
                    <Badge variant="outline">{previewDocument.status}</Badge>
                  </div>
                </div>

                <div className="bg-muted rounded-lg p-4">
                  <p className="text-sm text-muted-foreground text-center">
                    Document preview would be rendered here after retrieval.
                    <br />
                    C-CDA/FHIR document viewer integration required.
                  </p>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setShowDocumentPreview(false)}>
                  Close
                </Button>
                <Button onClick={() => {
                  setSelectedDocuments(new Set([previewDocument.id]));
                  setShowDocumentPreview(false);
                }}>
                  <Download className="h-4 w-4 mr-2" />
                  Select for Retrieval
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
