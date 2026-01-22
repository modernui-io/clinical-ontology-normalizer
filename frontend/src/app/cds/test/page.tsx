"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
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
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  Code,
  ExternalLink,
  Info,
  Loader2,
  Play,
  Plus,
  Shield,
  Trash2,
  X,
} from "lucide-react";

// =============================================================================
// Types
// =============================================================================

interface CDSService {
  hook: string;
  title: string;
  description: string;
  id: string;
  prefetch?: Record<string, string>;
}

interface CDSCard {
  uuid: string;
  summary: string;
  detail?: string;
  indicator: "info" | "warning" | "critical" | "hard-stop";
  source: {
    label: string;
    url?: string;
  };
  suggestions?: Array<{
    uuid: string;
    label: string;
    isRecommended?: boolean;
    actions: Array<{
      type: string;
      description: string;
    }>;
  }>;
  links?: Array<{
    label: string;
    url: string;
    type: string;
  }>;
  overrideReasons?: Array<{
    code: string;
    display: string;
  }>;
}

interface CDSResponse {
  cards: CDSCard[];
}

interface TestRequest {
  hook_type: string;
  patient_id: string;
  medications: string[];
  conditions: string[];
}

// =============================================================================
// Constants
// =============================================================================

const API_BASE = "/api";

const INDICATOR_CONFIG: Record<
  string,
  { label: string; color: string; icon: React.ReactNode; bgColor: string }
> = {
  info: {
    label: "Info",
    color: "text-blue-600",
    bgColor: "bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800",
    icon: <Info className="h-5 w-5 text-blue-500" />,
  },
  warning: {
    label: "Warning",
    color: "text-yellow-600",
    bgColor: "bg-yellow-50 dark:bg-yellow-950 border-yellow-200 dark:border-yellow-800",
    icon: <AlertTriangle className="h-5 w-5 text-yellow-500" />,
  },
  critical: {
    label: "Critical",
    color: "text-orange-600",
    bgColor: "bg-orange-50 dark:bg-orange-950 border-orange-200 dark:border-orange-800",
    icon: <AlertCircle className="h-5 w-5 text-orange-500" />,
  },
  "hard-stop": {
    label: "Hard Stop",
    color: "text-red-600",
    bgColor: "bg-red-50 dark:bg-red-950 border-red-200 dark:border-red-800",
    icon: <Shield className="h-5 w-5 text-red-500" />,
  },
};

const SAMPLE_MEDICATIONS = [
  "Warfarin",
  "Aspirin",
  "Lisinopril",
  "Metformin",
  "Simvastatin",
  "Amlodipine",
  "Omeprazole",
  "Sertraline",
  "Ibuprofen",
  "Atorvastatin",
];

const SAMPLE_CONDITIONS = [
  "Type 2 Diabetes Mellitus",
  "Essential Hypertension",
  "Hyperlipidemia",
  "Chronic Kidney Disease",
  "Heart Failure",
  "Atrial Fibrillation",
  "COPD",
  "Depression",
];

// =============================================================================
// API Functions
// =============================================================================

async function fetchServices(): Promise<CDSService[]> {
  const response = await fetch(`${API_BASE}/cds-services`);
  if (!response.ok) throw new Error("Failed to fetch CDS services");
  const data = await response.json();
  return data.services;
}

async function testHook(request: TestRequest): Promise<CDSResponse> {
  const response = await fetch(`${API_BASE}/cds-services/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to test hook");
  }
  return response.json();
}

// =============================================================================
// CDS Card Component
// =============================================================================

interface CDSCardViewProps {
  card: CDSCard;
}

function CDSCardView({ card }: CDSCardViewProps) {
  const [expanded, setExpanded] = useState(false);
  const config = INDICATOR_CONFIG[card.indicator] || INDICATOR_CONFIG.info;

  return (
    <div className={`rounded-lg border p-4 ${config.bgColor}`}>
      <div className="flex items-start gap-3">
        {config.icon}
        <div className="flex-1 space-y-2">
          <div className="flex items-start justify-between gap-2">
            <div>
              <h4 className="font-medium">{card.summary}</h4>
              <div className="flex items-center gap-2 mt-1">
                <Badge variant="outline" className={config.color}>
                  {config.label}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  Source: {card.source.label}
                </span>
              </div>
            </div>
            {card.detail && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setExpanded(!expanded)}
              >
                {expanded ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </Button>
            )}
          </div>

          {expanded && card.detail && (
            <div className="mt-3 pt-3 border-t border-current/10">
              <p className="text-sm whitespace-pre-wrap">{card.detail}</p>
            </div>
          )}

          {card.suggestions && card.suggestions.length > 0 && (
            <div className="mt-3 space-y-2">
              <p className="text-xs font-medium text-muted-foreground uppercase">
                Suggestions
              </p>
              <div className="flex flex-wrap gap-2">
                {card.suggestions.map((suggestion) => (
                  <Button
                    key={suggestion.uuid}
                    variant={suggestion.isRecommended ? "default" : "outline"}
                    size="sm"
                    className="text-xs"
                  >
                    {suggestion.label}
                    {suggestion.isRecommended && (
                      <Badge variant="secondary" className="ml-2 text-xs">
                        Recommended
                      </Badge>
                    )}
                  </Button>
                ))}
              </div>
            </div>
          )}

          {card.links && card.links.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-2">
              {card.links.map((link, index) => (
                <a
                  key={index}
                  href={link.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                >
                  {link.label}
                  <ExternalLink className="h-3 w-3" />
                </a>
              ))}
            </div>
          )}

          {card.overrideReasons && card.overrideReasons.length > 0 && (
            <div className="mt-3 pt-3 border-t border-current/10">
              <p className="text-xs font-medium text-muted-foreground uppercase mb-2">
                Override Reasons
              </p>
              <div className="flex flex-wrap gap-2">
                {card.overrideReasons.map((reason, index) => (
                  <Badge key={index} variant="outline" className="text-xs">
                    {reason.display}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Main Page Component
// =============================================================================

function CDSTestContent() {
  const searchParams = useSearchParams();
  const initialHook = searchParams.get("hook") || "patient-view";

  // State
  const [services, setServices] = useState<CDSService[]>([]);
  const [isLoadingServices, setIsLoadingServices] = useState(true);
  const [isTesting, setIsTesting] = useState(false);

  // Form state
  const [hookType, setHookType] = useState(initialHook);
  const [patientId, setPatientId] = useState("test-patient-001");
  const [medications, setMedications] = useState<string[]>(["Warfarin", "Aspirin"]);
  const [newMedication, setNewMedication] = useState("");
  const [conditions, setConditions] = useState<string[]>(["Essential Hypertension"]);
  const [newCondition, setNewCondition] = useState("");

  // Response state
  const [response, setResponse] = useState<CDSResponse | null>(null);
  const [requestJson, setRequestJson] = useState<string>("");
  const [responseJson, setResponseJson] = useState<string>("");
  const [activeTab, setActiveTab] = useState("cards");

  // Load services
  useEffect(() => {
    fetchServices()
      .then(setServices)
      .catch((error) => {
        console.error(error);
        toast.error("Failed to load CDS services");
      })
      .finally(() => setIsLoadingServices(false));
  }, []);

  // Add medication
  const addMedication = (med: string) => {
    if (med && !medications.includes(med)) {
      setMedications([...medications, med]);
      setNewMedication("");
    }
  };

  // Remove medication
  const removeMedication = (med: string) => {
    setMedications(medications.filter((m) => m !== med));
  };

  // Add condition
  const addCondition = (cond: string) => {
    if (cond && !conditions.includes(cond)) {
      setConditions([...conditions, cond]);
      setNewCondition("");
    }
  };

  // Remove condition
  const removeCondition = (cond: string) => {
    setConditions(conditions.filter((c) => c !== cond));
  };

  // Run test
  const runTest = async () => {
    setIsTesting(true);
    setResponse(null);

    const request: TestRequest = {
      hook_type: hookType,
      patient_id: patientId,
      medications,
      conditions,
    };

    setRequestJson(JSON.stringify(request, null, 2));

    try {
      const result = await testHook(request);
      setResponse(result);
      setResponseJson(JSON.stringify(result, null, 2));
      toast.success(`Test complete: ${result.cards.length} card(s) returned`);
    } catch (error: any) {
      console.error(error);
      toast.error(error.message || "Test failed");
      setResponseJson(JSON.stringify({ error: error.message }, null, 2));
    } finally {
      setIsTesting(false);
    }
  };

  // Get current service
  const currentService = services.find((s) => s.hook === hookType);

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex items-center gap-4">
        <Link href="/cds">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Test CDS Hook</h1>
          <p className="text-muted-foreground">
            Build test context and invoke CDS hooks
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Context Builder */}
        <Card>
          <CardHeader>
            <CardTitle>Context Builder</CardTitle>
            <CardDescription>
              Configure the test context for the CDS hook
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Hook Type */}
            <div className="space-y-2">
              <Label>Hook Type</Label>
              <Select value={hookType} onValueChange={setHookType}>
                <SelectTrigger>
                  <SelectValue placeholder="Select hook type" />
                </SelectTrigger>
                <SelectContent>
                  {isLoadingServices ? (
                    <div className="flex items-center justify-center py-4">
                      <Loader2 className="h-4 w-4 animate-spin" />
                    </div>
                  ) : (
                    services.map((service) => (
                      <SelectItem key={service.id} value={service.hook}>
                        <div className="flex flex-col">
                          <span>{service.title}</span>
                          <span className="text-xs text-muted-foreground">
                            {service.hook}
                          </span>
                        </div>
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
              {currentService && (
                <p className="text-xs text-muted-foreground">
                  {currentService.description}
                </p>
              )}
            </div>

            {/* Patient ID */}
            <div className="space-y-2">
              <Label>Patient ID</Label>
              <Input
                value={patientId}
                onChange={(e) => setPatientId(e.target.value)}
                placeholder="Enter patient ID"
              />
            </div>

            {/* Medications */}
            <div className="space-y-2">
              <Label>Medications</Label>
              <div className="flex flex-wrap gap-2 mb-2">
                {medications.map((med) => (
                  <Badge key={med} variant="secondary" className="gap-1">
                    {med}
                    <button
                      onClick={() => removeMedication(med)}
                      className="ml-1 hover:text-destructive"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
              <div className="flex gap-2">
                <Input
                  value={newMedication}
                  onChange={(e) => setNewMedication(e.target.value)}
                  placeholder="Add medication"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      addMedication(newMedication);
                    }
                  }}
                />
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => addMedication(newMedication)}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              <div className="flex flex-wrap gap-1 mt-2">
                {SAMPLE_MEDICATIONS.filter((m) => !medications.includes(m))
                  .slice(0, 5)
                  .map((med) => (
                    <Button
                      key={med}
                      variant="ghost"
                      size="sm"
                      className="text-xs h-6"
                      onClick={() => addMedication(med)}
                    >
                      + {med}
                    </Button>
                  ))}
              </div>
            </div>

            {/* Conditions */}
            <div className="space-y-2">
              <Label>Conditions</Label>
              <div className="flex flex-wrap gap-2 mb-2">
                {conditions.map((cond) => (
                  <Badge key={cond} variant="secondary" className="gap-1">
                    {cond}
                    <button
                      onClick={() => removeCondition(cond)}
                      className="ml-1 hover:text-destructive"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
              <div className="flex gap-2">
                <Input
                  value={newCondition}
                  onChange={(e) => setNewCondition(e.target.value)}
                  placeholder="Add condition"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      addCondition(newCondition);
                    }
                  }}
                />
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => addCondition(newCondition)}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              <div className="flex flex-wrap gap-1 mt-2">
                {SAMPLE_CONDITIONS.filter((c) => !conditions.includes(c))
                  .slice(0, 4)
                  .map((cond) => (
                    <Button
                      key={cond}
                      variant="ghost"
                      size="sm"
                      className="text-xs h-6"
                      onClick={() => addCondition(cond)}
                    >
                      + {cond}
                    </Button>
                  ))}
              </div>
            </div>

            {/* Run Test Button */}
            <Button
              className="w-full"
              onClick={runTest}
              disabled={isTesting || !hookType}
            >
              {isTesting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Testing...
                </>
              ) : (
                <>
                  <Play className="mr-2 h-4 w-4" />
                  Run Test
                </>
              )}
            </Button>
          </CardContent>
        </Card>

        {/* Response Viewer */}
        <Card>
          <CardHeader>
            <CardTitle>Response</CardTitle>
            <CardDescription>CDS Hooks response and cards</CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="w-full">
                <TabsTrigger value="cards" className="flex-1">
                  Cards ({response?.cards.length || 0})
                </TabsTrigger>
                <TabsTrigger value="request" className="flex-1">
                  Request
                </TabsTrigger>
                <TabsTrigger value="response" className="flex-1">
                  Response JSON
                </TabsTrigger>
              </TabsList>

              <TabsContent value="cards" className="mt-4">
                {!response ? (
                  <div className="text-center py-12 text-muted-foreground">
                    <Code className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>Run a test to see CDS cards</p>
                  </div>
                ) : response.cards.length === 0 ? (
                  <div className="text-center py-12 text-muted-foreground">
                    <Info className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>No cards returned</p>
                    <p className="text-sm mt-1">
                      The hook returned no alerts or recommendations
                    </p>
                  </div>
                ) : (
                  <ScrollArea className="h-[500px]">
                    <div className="space-y-4 pr-4">
                      {response.cards.map((card) => (
                        <CDSCardView key={card.uuid} card={card} />
                      ))}
                    </div>
                  </ScrollArea>
                )}
              </TabsContent>

              <TabsContent value="request" className="mt-4">
                <ScrollArea className="h-[500px]">
                  <pre className="text-xs bg-muted p-4 rounded-lg overflow-x-auto">
                    {requestJson || "// No request yet"}
                  </pre>
                </ScrollArea>
              </TabsContent>

              <TabsContent value="response" className="mt-4">
                <ScrollArea className="h-[500px]">
                  <pre className="text-xs bg-muted p-4 rounded-lg overflow-x-auto">
                    {responseJson || "// No response yet"}
                  </pre>
                </ScrollArea>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>

      {/* Quick Test Scenarios */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Test Scenarios</CardTitle>
          <CardDescription>
            Pre-configured scenarios to demonstrate CDS capabilities
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            <Button
              variant="outline"
              className="h-auto py-4 flex flex-col items-start text-left"
              onClick={() => {
                setHookType("order-select");
                setMedications(["Warfarin", "Aspirin"]);
                setConditions(["Atrial Fibrillation"]);
                runTest();
              }}
            >
              <span className="font-medium">Drug Interaction Test</span>
              <span className="text-xs text-muted-foreground mt-1">
                Warfarin + Aspirin interaction check
              </span>
            </Button>

            <Button
              variant="outline"
              className="h-auto py-4 flex flex-col items-start text-left"
              onClick={() => {
                setHookType("order-sign");
                setMedications(["Simvastatin", "Clarithromycin"]);
                setConditions([]);
                runTest();
              }}
            >
              <span className="font-medium">Contraindication Test</span>
              <span className="text-xs text-muted-foreground mt-1">
                Simvastatin + Clarithromycin (contraindicated)
              </span>
            </Button>

            <Button
              variant="outline"
              className="h-auto py-4 flex flex-col items-start text-left"
              onClick={() => {
                setHookType("patient-view");
                setMedications(["Lisinopril", "Metformin", "Atorvastatin"]);
                setConditions(["Type 2 Diabetes Mellitus", "Essential Hypertension"]);
                runTest();
              }}
            >
              <span className="font-medium">Complex Patient</span>
              <span className="text-xs text-muted-foreground mt-1">
                Multiple conditions and medications
              </span>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function CDSTestPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center">Loading CDS Test...</div>}>
      <CDSTestContent />
    </Suspense>
  );
}
