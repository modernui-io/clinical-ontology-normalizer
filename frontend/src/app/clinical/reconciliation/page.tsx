"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  AlertTriangle,
  AlertCircle,
  Info,
  ArrowLeft,
  Plus,
  X,
  CheckCircle,
  ArrowRight,
  ArrowLeftRight,
  Minus,
  Shield,
  FileText,
  Check,
  XCircle,
  Clock,
  Pill,
  RefreshCw,
  Download,
} from "lucide-react";

// Types
interface Medication {
  id: string;
  drugName: string;
  dose: string;
  frequency: string;
  route: string;
  prescriber?: string;
  indication?: string;
  isPrn?: boolean;
  notes?: string;
}

interface DiscrepancyAlert {
  id: string;
  discrepancyType: "addition" | "discontinuation" | "dose_change" | "frequency_change" | "route_change" | "brand_generic_substitution";
  severity: "high" | "moderate" | "low" | "info";
  description: string;
  recommendation: string;
  medicationsInvolved: Medication[];
  sourceMedication?: Medication;
  targetMedication?: Medication;
  resolved?: boolean;
  resolution?: {
    action: string;
    reason: string;
    resolvedBy: string;
  };
}

interface DrugInteractionWarning {
  drug1: string;
  drug2: string;
  severity: "contraindicated" | "major" | "moderate" | "minor";
  description: string;
  management: string;
}

interface DrugSafetyWarning {
  drugName: string;
  warningType: "black_box" | "allergy" | "high_risk";
  severity: string;
  description: string;
  recommendedAction: string;
}

// Resolution options
const resolutionActions = [
  { value: "accept", label: "Accept Change" },
  { value: "reject", label: "Reject Change" },
  { value: "modify", label: "Modify" },
  { value: "defer", label: "Defer Decision" },
];

const resolutionReasons = [
  { value: "intended_change", label: "Intended Change" },
  { value: "dosing_adjustment", label: "Dosing Adjustment" },
  { value: "therapeutic_substitution", label: "Therapeutic Substitution" },
  { value: "discontinue_duplicate", label: "Discontinue Duplicate" },
  { value: "adverse_reaction", label: "Adverse Reaction" },
  { value: "cost_substitution", label: "Cost/Generic Substitution" },
  { value: "formulary_change", label: "Formulary Change" },
  { value: "patient_preference", label: "Patient Preference" },
  { value: "clinical_indication", label: "Clinical Indication" },
  { value: "documentation_error", label: "Documentation Error" },
  { value: "other", label: "Other" },
];

// Severity styling
const severityStyles = {
  high: {
    badge: "bg-red-500 text-white",
    border: "border-red-500",
    bg: "bg-red-50 dark:bg-red-950",
    icon: <AlertCircle className="h-4 w-4 text-red-600" />,
    label: "High Risk",
  },
  moderate: {
    badge: "bg-amber-500 text-white",
    border: "border-amber-400",
    bg: "bg-amber-50 dark:bg-amber-950",
    icon: <AlertTriangle className="h-4 w-4 text-amber-500" />,
    label: "Moderate",
  },
  low: {
    badge: "bg-blue-500 text-white",
    border: "border-blue-400",
    bg: "bg-blue-50 dark:bg-blue-950",
    icon: <Info className="h-4 w-4 text-blue-500" />,
    label: "Low",
  },
  info: {
    badge: "bg-gray-500 text-white",
    border: "border-gray-400",
    bg: "bg-gray-50 dark:bg-gray-950",
    icon: <Info className="h-4 w-4 text-gray-500" />,
    label: "Info",
  },
};

const interactionSeverityStyles = {
  contraindicated: {
    badge: "bg-red-600 text-white",
    icon: <AlertCircle className="h-4 w-4 text-red-600" />,
    label: "Contraindicated",
  },
  major: {
    badge: "bg-red-500 text-white",
    icon: <AlertTriangle className="h-4 w-4 text-red-500" />,
    label: "Major",
  },
  moderate: {
    badge: "bg-amber-500 text-white",
    icon: <AlertTriangle className="h-4 w-4 text-amber-500" />,
    label: "Moderate",
  },
  minor: {
    badge: "bg-blue-500 text-white",
    icon: <Info className="h-4 w-4 text-blue-500" />,
    label: "Minor",
  },
};

// Discrepancy type labels and icons
const discrepancyTypeInfo = {
  addition: { label: "New Medication", icon: <Plus className="h-4 w-4" />, color: "text-green-600" },
  discontinuation: { label: "Discontinued", icon: <Minus className="h-4 w-4" />, color: "text-red-600" },
  dose_change: { label: "Dose Change", icon: <ArrowLeftRight className="h-4 w-4" />, color: "text-amber-600" },
  frequency_change: { label: "Frequency Change", icon: <Clock className="h-4 w-4" />, color: "text-amber-600" },
  route_change: { label: "Route Change", icon: <ArrowRight className="h-4 w-4" />, color: "text-amber-600" },
  brand_generic_substitution: { label: "Brand/Generic Switch", icon: <RefreshCw className="h-4 w-4" />, color: "text-blue-600" },
};

// Mock data for source medications (e.g., home medications)
const mockSourceMedications: Medication[] = [
  { id: "s1", drugName: "Metformin", dose: "500mg", frequency: "twice daily", route: "oral", indication: "Diabetes" },
  { id: "s2", drugName: "Lisinopril", dose: "10mg", frequency: "daily", route: "oral", indication: "Hypertension" },
  { id: "s3", drugName: "Atorvastatin", dose: "20mg", frequency: "daily", route: "oral", indication: "Hyperlipidemia" },
  { id: "s4", drugName: "Aspirin", dose: "81mg", frequency: "daily", route: "oral", indication: "Cardiac protection" },
  { id: "s5", drugName: "Omeprazole", dose: "20mg", frequency: "daily", route: "oral", indication: "GERD" },
  { id: "s6", drugName: "Metoprolol Tartrate", dose: "25mg", frequency: "twice daily", route: "oral", indication: "Hypertension" },
  { id: "s7", drugName: "Simvastatin", dose: "40mg", frequency: "daily", route: "oral", indication: "Hyperlipidemia" },
];

// Mock data for target medications (e.g., discharge medications)
const mockTargetMedications: Medication[] = [
  { id: "t1", drugName: "Metformin", dose: "1000mg", frequency: "twice daily", route: "oral", indication: "Diabetes" }, // Dose changed
  { id: "t2", drugName: "Lisinopril", dose: "20mg", frequency: "daily", route: "oral", indication: "Hypertension" }, // Dose changed
  { id: "t3", drugName: "Atorvastatin", dose: "40mg", frequency: "daily", route: "oral", indication: "Hyperlipidemia" }, // Dose changed
  { id: "t4", drugName: "Aspirin", dose: "81mg", frequency: "daily", route: "oral", indication: "Cardiac protection" }, // Unchanged
  { id: "t5", drugName: "Pantoprazole", dose: "40mg", frequency: "daily", route: "oral", indication: "GERD" }, // Substituted
  { id: "t6", drugName: "Metoprolol Succinate", dose: "50mg", frequency: "daily", route: "oral", indication: "Hypertension" }, // Changed formulation & dose
  { id: "t7", drugName: "Warfarin", dose: "5mg", frequency: "daily", route: "oral", indication: "Atrial fibrillation", isPrn: false }, // New
  { id: "t8", drugName: "Furosemide", dose: "40mg", frequency: "daily", route: "oral", indication: "CHF", isPrn: false }, // New
  // Simvastatin discontinued
];

// Mock discrepancies
const mockDiscrepancies: DiscrepancyAlert[] = [
  {
    id: "d1",
    discrepancyType: "dose_change",
    severity: "moderate",
    description: "Metformin dose increased from 500mg to 1000mg twice daily",
    recommendation: "Verify dose escalation is appropriate for patient's renal function and glucose control",
    medicationsInvolved: [],
    sourceMedication: mockSourceMedications[0],
    targetMedication: mockTargetMedications[0],
  },
  {
    id: "d2",
    discrepancyType: "dose_change",
    severity: "moderate",
    description: "Lisinopril dose increased from 10mg to 20mg daily",
    recommendation: "Monitor blood pressure and potassium levels",
    medicationsInvolved: [],
    sourceMedication: mockSourceMedications[1],
    targetMedication: mockTargetMedications[1],
  },
  {
    id: "d3",
    discrepancyType: "dose_change",
    severity: "low",
    description: "Atorvastatin dose increased from 20mg to 40mg daily",
    recommendation: "Consider LFT monitoring after dose increase",
    medicationsInvolved: [],
    sourceMedication: mockSourceMedications[2],
    targetMedication: mockTargetMedications[2],
  },
  {
    id: "d4",
    discrepancyType: "brand_generic_substitution",
    severity: "low",
    description: "Omeprazole 20mg changed to Pantoprazole 40mg",
    recommendation: "Therapeutic substitution - similar efficacy expected",
    medicationsInvolved: [],
    sourceMedication: mockSourceMedications[4],
    targetMedication: mockTargetMedications[4],
  },
  {
    id: "d5",
    discrepancyType: "dose_change",
    severity: "moderate",
    description: "Metoprolol changed from Tartrate 25mg BID to Succinate 50mg daily",
    recommendation: "Extended-release formulation conversion - verify equivalent dosing",
    medicationsInvolved: [],
    sourceMedication: mockSourceMedications[5],
    targetMedication: mockTargetMedications[5],
  },
  {
    id: "d6",
    discrepancyType: "addition",
    severity: "high",
    description: "New anticoagulant: Warfarin 5mg daily added",
    recommendation: "High-alert medication - requires INR monitoring, patient education, and interaction review",
    medicationsInvolved: [],
    targetMedication: mockTargetMedications[6],
  },
  {
    id: "d7",
    discrepancyType: "addition",
    severity: "moderate",
    description: "New diuretic: Furosemide 40mg daily added",
    recommendation: "Monitor electrolytes, renal function, and for signs of dehydration",
    medicationsInvolved: [],
    targetMedication: mockTargetMedications[7],
  },
  {
    id: "d8",
    discrepancyType: "discontinuation",
    severity: "high",
    description: "Simvastatin 40mg discontinued",
    recommendation: "High-risk change - verify intentional. Patient now on Atorvastatin (therapeutic duplication review)",
    medicationsInvolved: [],
    sourceMedication: mockSourceMedications[6],
  },
];

// Mock interaction warnings
const mockInteractionWarnings: DrugInteractionWarning[] = [
  {
    drug1: "Warfarin",
    drug2: "Aspirin",
    severity: "major",
    description: "Additive anticoagulant/antiplatelet effects",
    management: "Avoid unless specifically indicated; monitor INR closely",
  },
];

// Mock safety warnings
const mockSafetyWarnings: DrugSafetyWarning[] = [
  {
    drugName: "Warfarin",
    warningType: "high_risk",
    severity: "high",
    description: "Warfarin is a high-alert medication with narrow therapeutic index",
    recommendedAction: "Requires independent double-check and patient education",
  },
  {
    drugName: "Metformin",
    warningType: "black_box",
    severity: "moderate",
    description: "Risk of lactic acidosis - avoid in renal impairment",
    recommendedAction: "Check renal function before dose increase",
  },
];

export default function MedicationReconciliationPage() {
  const [sourceMedications] = useState<Medication[]>(mockSourceMedications);
  const [targetMedications] = useState<Medication[]>(mockTargetMedications);
  const [discrepancies, setDiscrepancies] = useState<DiscrepancyAlert[]>(mockDiscrepancies);
  const [interactionWarnings] = useState<DrugInteractionWarning[]>(mockInteractionWarnings);
  const [safetyWarnings] = useState<DrugSafetyWarning[]>(mockSafetyWarnings);
  const [selectedDiscrepancy, setSelectedDiscrepancy] = useState<DiscrepancyAlert | null>(null);
  const [isResolveDialogOpen, setIsResolveDialogOpen] = useState(false);
  const [resolveAction, setResolveAction] = useState("");
  const [resolveReason, setResolveReason] = useState("");
  const [resolveNotes, setResolveNotes] = useState("");
  const [showReconciledPreview, setShowReconciledPreview] = useState(false);

  // Computed values
  const unresolvedCount = discrepancies.filter((d) => !d.resolved).length;
  const resolvedCount = discrepancies.filter((d) => d.resolved).length;
  const highRiskCount = discrepancies.filter((d) => d.severity === "high" && !d.resolved).length;

  // Handle resolving a discrepancy
  const handleResolve = useCallback(() => {
    if (!selectedDiscrepancy || !resolveAction || !resolveReason) return;

    setDiscrepancies((prev) =>
      prev.map((d) =>
        d.id === selectedDiscrepancy.id
          ? {
              ...d,
              resolved: true,
              resolution: {
                action: resolveAction,
                reason: resolveReason,
                resolvedBy: "Current User",
              },
            }
          : d
      )
    );

    setIsResolveDialogOpen(false);
    setSelectedDiscrepancy(null);
    setResolveAction("");
    setResolveReason("");
    setResolveNotes("");
  }, [selectedDiscrepancy, resolveAction, resolveReason]);

  // Open resolve dialog
  const openResolveDialog = (discrepancy: DiscrepancyAlert) => {
    setSelectedDiscrepancy(discrepancy);
    setIsResolveDialogOpen(true);
  };

  // Build reconciled list based on resolutions
  const getReconciledList = useCallback((): Medication[] => {
    const reconciled: Medication[] = [];

    // Start with target medications
    for (const med of targetMedications) {
      // Find any related discrepancy that was rejected
      const relatedDiscrepancy = discrepancies.find(
        (d) =>
          d.targetMedication?.id === med.id &&
          d.resolved &&
          d.resolution?.action === "reject"
      );

      if (!relatedDiscrepancy) {
        // If not rejected, include the target medication
        reconciled.push(med);
      } else if (relatedDiscrepancy.sourceMedication) {
        // If rejected and has source, include source instead
        reconciled.push(relatedDiscrepancy.sourceMedication);
      }
    }

    // Check for discontinued medications that were rejected (should be kept)
    for (const d of discrepancies) {
      if (
        d.discrepancyType === "discontinuation" &&
        d.resolved &&
        d.resolution?.action === "reject" &&
        d.sourceMedication
      ) {
        // Add back the source medication that was intended to be discontinued
        if (!reconciled.find((m) => m.id === d.sourceMedication?.id)) {
          reconciled.push(d.sourceMedication);
        }
      }
    }

    return reconciled;
  }, [targetMedications, discrepancies]);

  const reconciledMedications = getReconciledList();

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Link href="/clinical">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Medication Reconciliation
            </h1>
            <p className="text-muted-foreground">
              Compare and reconcile medication lists for safe care transitions
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => setShowReconciledPreview(!showReconciledPreview)}
          >
            <FileText className="mr-2 h-4 w-4" />
            {showReconciledPreview ? "Hide Preview" : "Preview Reconciled List"}
          </Button>
          <Button disabled={unresolvedCount > 0}>
            <Download className="mr-2 h-4 w-4" />
            Export Report
          </Button>
        </div>
      </div>

      {/* Status Summary */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900">
                <Pill className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{discrepancies.length}</p>
                <p className="text-sm text-muted-foreground">Total Discrepancies</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-100 dark:bg-red-900">
                <AlertCircle className="h-6 w-6 text-red-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-red-600">{highRiskCount}</p>
                <p className="text-sm text-muted-foreground">High Risk Unresolved</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-amber-100 dark:bg-amber-900">
                <Clock className="h-6 w-6 text-amber-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-amber-600">{unresolvedCount}</p>
                <p className="text-sm text-muted-foreground">Pending Review</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-green-100 dark:bg-green-900">
                <CheckCircle className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-green-600">{resolvedCount}</p>
                <p className="text-sm text-muted-foreground">Resolved</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Drug Interaction and Safety Warnings */}
      {(interactionWarnings.length > 0 || safetyWarnings.length > 0) && (
        <Card className="border-red-300 dark:border-red-800">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-red-600">
              <Shield className="h-5 w-5" />
              Safety Alerts
            </CardTitle>
            <CardDescription>
              Drug interactions and safety warnings for the reconciled medication list
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Interaction Warnings */}
            {interactionWarnings.map((warning, idx) => {
              const style = interactionSeverityStyles[warning.severity];
              return (
                <div
                  key={idx}
                  className="flex items-start gap-3 p-3 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950"
                >
                  {style.icon}
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">
                        {warning.drug1} + {warning.drug2}
                      </span>
                      <Badge className={style.badge}>{style.label}</Badge>
                    </div>
                    <p className="text-sm text-muted-foreground mt-1">
                      {warning.description}
                    </p>
                    <p className="text-sm mt-1">
                      <span className="font-medium">Management: </span>
                      {warning.management}
                    </p>
                  </div>
                </div>
              );
            })}

            {/* Safety Warnings */}
            {safetyWarnings.map((warning, idx) => (
              <div
                key={idx}
                className="flex items-start gap-3 p-3 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950"
              >
                <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5" />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">{warning.drugName}</span>
                    <Badge variant="outline">{warning.warningType.replace("_", " ")}</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">
                    {warning.description}
                  </p>
                  <p className="text-sm mt-1">
                    <span className="font-medium">Action: </span>
                    {warning.recommendedAction}
                  </p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Side-by-side Medication Comparison */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Source Medications */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ArrowRight className="h-5 w-5 text-blue-600" />
              Home Medications
            </CardTitle>
            <CardDescription>
              {sourceMedications.length} medications prior to transition
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Medication</TableHead>
                  <TableHead>Dose</TableHead>
                  <TableHead>Frequency</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sourceMedications.map((med) => {
                  // Find related discrepancy
                  const relatedDiscrepancy = discrepancies.find(
                    (d) => d.sourceMedication?.id === med.id
                  );
                  const isDiscontinued = relatedDiscrepancy?.discrepancyType === "discontinuation";
                  const isChanged = relatedDiscrepancy && !isDiscontinued;

                  return (
                    <TableRow
                      key={med.id}
                      className={
                        isDiscontinued
                          ? "bg-red-50 dark:bg-red-950"
                          : isChanged
                          ? "bg-amber-50 dark:bg-amber-950"
                          : ""
                      }
                    >
                      <TableCell className="font-medium">
                        {med.drugName}
                        {med.indication && (
                          <p className="text-xs text-muted-foreground">
                            {med.indication}
                          </p>
                        )}
                      </TableCell>
                      <TableCell className={isChanged ? "text-amber-600 font-medium" : ""}>
                        {med.dose}
                      </TableCell>
                      <TableCell>{med.frequency}</TableCell>
                      <TableCell>
                        {isDiscontinued ? (
                          <Badge className="bg-red-500 text-white">
                            Discontinued
                          </Badge>
                        ) : isChanged ? (
                          <Badge className="bg-amber-500 text-white">
                            Changed
                          </Badge>
                        ) : (
                          <Badge variant="outline">Unchanged</Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Target Medications */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ArrowLeft className="h-5 w-5 text-green-600" />
              Discharge Medications
            </CardTitle>
            <CardDescription>
              {targetMedications.length} medications at discharge
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Medication</TableHead>
                  <TableHead>Dose</TableHead>
                  <TableHead>Frequency</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {targetMedications.map((med) => {
                  // Find related discrepancy
                  const relatedDiscrepancy = discrepancies.find(
                    (d) => d.targetMedication?.id === med.id
                  );
                  const isAddition = relatedDiscrepancy?.discrepancyType === "addition";
                  const isChanged = relatedDiscrepancy && !isAddition;

                  return (
                    <TableRow
                      key={med.id}
                      className={
                        isAddition
                          ? "bg-green-50 dark:bg-green-950"
                          : isChanged
                          ? "bg-amber-50 dark:bg-amber-950"
                          : ""
                      }
                    >
                      <TableCell className="font-medium">
                        {med.drugName}
                        {med.indication && (
                          <p className="text-xs text-muted-foreground">
                            {med.indication}
                          </p>
                        )}
                      </TableCell>
                      <TableCell className={isChanged ? "text-amber-600 font-medium" : ""}>
                        {med.dose}
                      </TableCell>
                      <TableCell>{med.frequency}</TableCell>
                      <TableCell>
                        {isAddition ? (
                          <Badge className="bg-green-500 text-white">New</Badge>
                        ) : isChanged ? (
                          <Badge className="bg-amber-500 text-white">
                            Changed
                          </Badge>
                        ) : (
                          <Badge variant="outline">Unchanged</Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      {/* Discrepancy Review Panel */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            Discrepancies to Review
          </CardTitle>
          <CardDescription>
            Review and resolve each discrepancy before completing reconciliation
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {discrepancies.map((discrepancy) => {
              const style = severityStyles[discrepancy.severity];
              const typeInfo = discrepancyTypeInfo[discrepancy.discrepancyType];

              return (
                <div
                  key={discrepancy.id}
                  className={`rounded-lg border ${style.border} ${style.bg} p-4 ${
                    discrepancy.resolved ? "opacity-60" : ""
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3 flex-1">
                      <div className="mt-0.5">{style.icon}</div>
                      <div className="flex-1 space-y-2">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`flex items-center gap-1 font-medium ${typeInfo.color}`}>
                            {typeInfo.icon}
                            {typeInfo.label}
                          </span>
                          <Badge className={style.badge}>{style.label}</Badge>
                          {discrepancy.resolved && (
                            <Badge className="bg-green-500 text-white">
                              <Check className="h-3 w-3 mr-1" />
                              Resolved
                            </Badge>
                          )}
                        </div>

                        <p className="text-sm font-medium">{discrepancy.description}</p>

                        <div className="p-2 rounded bg-background border">
                          <span className="text-sm font-medium text-blue-600 dark:text-blue-400">
                            Recommendation:{" "}
                          </span>
                          <span className="text-sm">{discrepancy.recommendation}</span>
                        </div>

                        {/* Show resolution if resolved */}
                        {discrepancy.resolved && discrepancy.resolution && (
                          <div className="text-sm text-muted-foreground">
                            <span className="font-medium">Resolution: </span>
                            {discrepancy.resolution.action} - {discrepancy.resolution.reason}
                            <span className="ml-2">by {discrepancy.resolution.resolvedBy}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex gap-2">
                      {!discrepancy.resolved ? (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => openResolveDialog(discrepancy)}
                          >
                            Review
                          </Button>
                        </>
                      ) : (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setDiscrepancies((prev) =>
                              prev.map((d) =>
                                d.id === discrepancy.id
                                  ? { ...d, resolved: false, resolution: undefined }
                                  : d
                              )
                            );
                          }}
                        >
                          Undo
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Reconciled List Preview */}
      {showReconciledPreview && (
        <Card className="border-green-300 dark:border-green-800">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-green-600">
              <CheckCircle className="h-5 w-5" />
              Reconciled Medication List (Preview)
            </CardTitle>
            <CardDescription>
              Final medication list based on current resolutions ({reconciledMedications.length} medications)
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Medication</TableHead>
                  <TableHead>Dose</TableHead>
                  <TableHead>Frequency</TableHead>
                  <TableHead>Route</TableHead>
                  <TableHead>Indication</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reconciledMedications.map((med) => (
                  <TableRow key={med.id}>
                    <TableCell className="font-medium">{med.drugName}</TableCell>
                    <TableCell>{med.dose}</TableCell>
                    <TableCell>{med.frequency}</TableCell>
                    <TableCell>{med.route}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {med.indication || "-"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Resolve Dialog */}
      <Dialog open={isResolveDialogOpen} onOpenChange={setIsResolveDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Resolve Discrepancy</DialogTitle>
            <DialogDescription>
              Review and document your decision for this medication change
            </DialogDescription>
          </DialogHeader>

          {selectedDiscrepancy && (
            <div className="space-y-4">
              {/* Discrepancy Details */}
              <div className={`rounded-lg p-3 ${severityStyles[selectedDiscrepancy.severity].bg} border ${severityStyles[selectedDiscrepancy.severity].border}`}>
                <div className="flex items-center gap-2 mb-2">
                  <span className={`flex items-center gap-1 font-medium ${discrepancyTypeInfo[selectedDiscrepancy.discrepancyType].color}`}>
                    {discrepancyTypeInfo[selectedDiscrepancy.discrepancyType].icon}
                    {discrepancyTypeInfo[selectedDiscrepancy.discrepancyType].label}
                  </span>
                </div>
                <p className="text-sm">{selectedDiscrepancy.description}</p>
              </div>

              {/* Action Selection */}
              <div className="space-y-2">
                <Label>Action</Label>
                <Select value={resolveAction} onValueChange={setResolveAction}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select action..." />
                  </SelectTrigger>
                  <SelectContent>
                    {resolutionActions.map((action) => (
                      <SelectItem key={action.value} value={action.value}>
                        {action.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Reason Selection */}
              <div className="space-y-2">
                <Label>Reason</Label>
                <Select value={resolveReason} onValueChange={setResolveReason}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select reason..." />
                  </SelectTrigger>
                  <SelectContent>
                    {resolutionReasons.map((reason) => (
                      <SelectItem key={reason.value} value={reason.value}>
                        {reason.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Notes */}
              <div className="space-y-2">
                <Label>Notes (Optional)</Label>
                <Textarea
                  placeholder="Add any additional notes..."
                  value={resolveNotes}
                  onChange={(e) => setResolveNotes(e.target.value)}
                  rows={3}
                />
              </div>
            </div>
          )}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsResolveDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleResolve}
              disabled={!resolveAction || !resolveReason}
            >
              <Check className="mr-2 h-4 w-4" />
              Resolve
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Clinical Disclaimer */}
      <Card>
        <CardContent className="py-4">
          <div className="flex items-start gap-3 text-xs text-muted-foreground">
            <Info className="h-4 w-4 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">Clinical Disclaimer</p>
              <p>
                This medication reconciliation tool is for informational purposes
                and should not replace clinical judgment. All medication changes
                should be verified by a licensed healthcare provider. Drug
                interaction checking may not include all possible interactions.
                Consult authoritative clinical references before making medication
                decisions.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
