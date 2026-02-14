"use client";

import { useState, useEffect, useCallback } from "react";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Shield,
  FileWarning,
  Search,
  RefreshCw,
  Loader2,
  AlertCircle,
  Activity,
} from "lucide-react";

interface ICSR {
  id: string;
  case_number: string;
  patient_age: number;
  patient_sex: string;
  reporter_type: string;
  drug_name: string;
  indication: string;
  event_terms: string[];
  onset_date: string;
  outcome: string;
  seriousness_criteria: string[];
  causality: string;
  status: string;
  received_date: string;
  source: string;
  country: string;
  narrative: string;
}

interface Signal {
  id: string;
  title: string;
  drug_name: string;
  event_term: string;
  classification: string;
  prr: number;
  ror: number;
  case_count: number;
  evidence_strength: string;
  action_taken: string;
  regulatory_action_type: string;
}

interface ICSRResponse {
  items: ICSR[];
  total: number;
  limit: number;
  offset: number;
}

interface SignalResponse {
  items: Signal[];
  total: number;
}

const causalityColors: Record<string, string> = {
  CERTAIN: "bg-red-600 text-white",
  PROBABLE: "bg-orange-500 text-white",
  POSSIBLE: "bg-yellow-500 text-white",
  UNLIKELY: "bg-gray-400 text-white",
  UNASSESSABLE: "bg-gray-400 text-white",
};

const statusColors: Record<string, string> = {
  INITIAL: "bg-blue-500 text-white",
  FOLLOW_UP: "bg-yellow-500 text-white",
  FINAL: "bg-green-600 text-white",
};

const classificationColors: Record<string, string> = {
  VALIDATED: "bg-green-600 text-white",
  UNDER_REVIEW: "bg-yellow-500 text-white",
  REFUTED: "bg-red-600 text-white",
  NEW: "bg-blue-500 text-white",
};

const evidenceColors: Record<string, string> = {
  strong: "bg-emerald-600 text-white",
  moderate: "bg-amber-500 text-white",
  weak: "bg-gray-400 text-white",
};

export default function PharmacovigilancePage() {
  const [icsrs, setIcsrs] = useState<ICSR[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [icsrRes, signalRes] = await Promise.all([
        fetch("/api/pharmacovigilance/icsrs").then((r) => r.json()),
        fetch("/api/pharmacovigilance/signals").then((r) => r.json()),
      ]);

      setIcsrs(icsrRes.items || []);
      setSignals(signalRes.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
      console.error("Failed to load pharmacovigilance data:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const totalICSRs = icsrs.length;
  const seriousCases = icsrs.filter(
    (icsr) => icsr.seriousness_criteria && icsr.seriousness_criteria.length > 0
  ).length;
  const activeSignals = signals.filter(
    (s) => s.classification === "UNDER_REVIEW" || s.classification === "NEW"
  ).length;
  const validatedSignals = signals.filter(
    (s) => s.classification === "VALIDATED"
  ).length;

  if (error) {
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center gap-3">
          <Shield className="h-8 w-8 text-muted-foreground" />
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Pharmacovigilance
            </h1>
            <p className="text-muted-foreground">
              Individual Case Safety Reports and Safety Signals
            </p>
          </div>
        </div>
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              Error Loading Data
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-4">{error}</p>
            <Button onClick={loadData} variant="outline" size="sm">
              <RefreshCw className="mr-2 h-4 w-4" />
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="h-8 w-8 text-muted-foreground" />
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Pharmacovigilance
            </h1>
            <p className="text-muted-foreground">
              Individual Case Safety Reports and Safety Signals
            </p>
          </div>
        </div>
        <Button
          onClick={loadData}
          variant="outline"
          size="sm"
          disabled={isLoading}
        >
          {isLoading ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          Refresh
        </Button>
      </div>

      {/* Summary Cards */}
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <div className="h-4 w-24 bg-muted animate-pulse rounded" />
              </CardHeader>
              <CardContent>
                <div className="h-8 w-16 bg-muted animate-pulse rounded" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                <FileWarning className="h-4 w-4" />
                Total ICSRs
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{totalICSRs}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                <AlertCircle className="h-4 w-4" />
                Serious Cases
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-orange-600">
                {seriousCases}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                <Activity className="h-4 w-4" />
                Active Signals
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-yellow-600">
                {activeSignals}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                <Shield className="h-4 w-4" />
                Validated Signals
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">
                {validatedSignals}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Tabs */}
      <Tabs defaultValue="icsrs" className="space-y-4">
        <TabsList>
          <TabsTrigger value="icsrs">ICSR Cases</TabsTrigger>
          <TabsTrigger value="signals">Safety Signals</TabsTrigger>
        </TabsList>

        {/* ICSR Cases Tab */}
        <TabsContent value="icsrs" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileWarning className="h-5 w-5" />
                Individual Case Safety Reports
              </CardTitle>
              <CardDescription>
                Clinical trial and post-market adverse event reports
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : icsrs.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Search className="h-12 w-12 mx-auto mb-2 opacity-50" />
                  <p>No ICSR cases found</p>
                </div>
              ) : (
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Case #</TableHead>
                        <TableHead>Drug</TableHead>
                        <TableHead>Event Terms</TableHead>
                        <TableHead>Causality</TableHead>
                        <TableHead>Outcome</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Country</TableHead>
                        <TableHead>Received Date</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {icsrs.map((icsr) => (
                        <TableRow key={icsr.id}>
                          <TableCell className="font-medium">
                            {icsr.case_number}
                          </TableCell>
                          <TableCell>{icsr.drug_name}</TableCell>
                          <TableCell>
                            <div className="flex flex-wrap gap-1">
                              {icsr.event_terms.map((term, idx) => (
                                <Badge
                                  key={idx}
                                  variant="outline"
                                  className="text-xs"
                                >
                                  {term}
                                </Badge>
                              ))}
                            </div>
                          </TableCell>
                          <TableCell>
                            <Badge
                              className={
                                causalityColors[icsr.causality] ||
                                "bg-gray-400 text-white"
                              }
                            >
                              {icsr.causality}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-sm">
                            {icsr.outcome}
                          </TableCell>
                          <TableCell>
                            <Badge
                              className={
                                statusColors[icsr.status] ||
                                "bg-gray-400 text-white"
                              }
                            >
                              {icsr.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-sm">
                            {icsr.country}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {new Date(icsr.received_date).toLocaleDateString()}
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

        {/* Safety Signals Tab */}
        <TabsContent value="signals" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-5 w-5" />
                Safety Signals
              </CardTitle>
              <CardDescription>
                Statistical signals from pharmacovigilance surveillance
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : signals.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Search className="h-12 w-12 mx-auto mb-2 opacity-50" />
                  <p>No safety signals found</p>
                </div>
              ) : (
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Title</TableHead>
                        <TableHead>Drug</TableHead>
                        <TableHead>Event</TableHead>
                        <TableHead>Classification</TableHead>
                        <TableHead className="text-right">PRR</TableHead>
                        <TableHead className="text-right">ROR</TableHead>
                        <TableHead className="text-right">Cases</TableHead>
                        <TableHead>Evidence</TableHead>
                        <TableHead>Action Taken</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {signals.map((signal) => (
                        <TableRow key={signal.id}>
                          <TableCell className="font-medium">
                            {signal.title}
                          </TableCell>
                          <TableCell>{signal.drug_name}</TableCell>
                          <TableCell>{signal.event_term}</TableCell>
                          <TableCell>
                            <Badge
                              className={
                                classificationColors[signal.classification] ||
                                "bg-gray-400 text-white"
                              }
                            >
                              {signal.classification.replace("_", " ")}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right font-mono">
                            {signal.prr.toFixed(1)}
                          </TableCell>
                          <TableCell className="text-right font-mono">
                            {signal.ror.toFixed(1)}
                          </TableCell>
                          <TableCell className="text-right">
                            {signal.case_count}
                          </TableCell>
                          <TableCell>
                            <Badge
                              className={
                                evidenceColors[signal.evidence_strength] ||
                                "bg-gray-400 text-white"
                              }
                            >
                              {signal.evidence_strength}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-sm">
                            {signal.action_taken}
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
    </div>
  );
}
