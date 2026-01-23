"use client";

import { useState } from "react";
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
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ArrowRightLeft,
  Pill,
} from "lucide-react";

type ReconciliationAction = "keep" | "discontinue" | "modify" | "add" | "pending";

interface Medication {
  id: string;
  name: string;
  generic_name: string;
  dose: string;
  route: string;
  frequency: string;
  indication: string;
  prescriber: string;
  start_date: string;
  rxnorm_code: string;
}

interface ReconciliationItem {
  id: string;
  current_med: Medication | null;
  proposed_med: Medication | null;
  action: ReconciliationAction;
  interaction_warnings: string[];
  notes: string;
}

const mockCurrentMeds: Medication[] = [
  { id: "m1", name: "Lisinopril", generic_name: "lisinopril", dose: "10mg", route: "PO", frequency: "QD", indication: "Hypertension", prescriber: "Dr. Smith", start_date: "2024-03-15", rxnorm_code: "314076" },
  { id: "m2", name: "Metformin", generic_name: "metformin", dose: "500mg", route: "PO", frequency: "BID", indication: "Type 2 Diabetes", prescriber: "Dr. Smith", start_date: "2024-01-10", rxnorm_code: "861004" },
  { id: "m3", name: "Atorvastatin", generic_name: "atorvastatin", dose: "20mg", route: "PO", frequency: "QHS", indication: "Hyperlipidemia", prescriber: "Dr. Jones", start_date: "2023-11-22", rxnorm_code: "259255" },
  { id: "m4", name: "Aspirin", generic_name: "aspirin", dose: "81mg", route: "PO", frequency: "QD", indication: "Cardioprotective", prescriber: "Dr. Jones", start_date: "2023-11-22", rxnorm_code: "243670" },
  { id: "m5", name: "Omeprazole", generic_name: "omeprazole", dose: "20mg", route: "PO", frequency: "QD", indication: "GERD", prescriber: "Dr. Smith", start_date: "2024-06-01", rxnorm_code: "316162" },
  { id: "m6", name: "Amlodipine", generic_name: "amlodipine", dose: "5mg", route: "PO", frequency: "QD", indication: "Hypertension", prescriber: "Dr. Smith", start_date: "2024-08-10", rxnorm_code: "308135" },
];

const mockProposedMeds: Medication[] = [
  { id: "p1", name: "Lisinopril", generic_name: "lisinopril", dose: "20mg", route: "PO", frequency: "QD", indication: "Hypertension", prescriber: "Dr. Smith", start_date: "2025-01-14", rxnorm_code: "314077" },
  { id: "p2", name: "Metformin ER", generic_name: "metformin", dose: "1000mg", route: "PO", frequency: "QD", indication: "Type 2 Diabetes", prescriber: "Dr. Smith", start_date: "2025-01-14", rxnorm_code: "861007" },
  { id: "p3", name: "Empagliflozin", generic_name: "empagliflozin", dose: "10mg", route: "PO", frequency: "QD", indication: "Type 2 Diabetes / Heart Failure", prescriber: "Dr. Smith", start_date: "2025-01-14", rxnorm_code: "1545653" },
  { id: "p4", name: "Warfarin", generic_name: "warfarin", dose: "5mg", route: "PO", frequency: "QD", indication: "Atrial Fibrillation", prescriber: "Dr. Jones", start_date: "2025-01-14", rxnorm_code: "855332" },
];

const initialReconciliation: ReconciliationItem[] = [
  { id: "r1", current_med: mockCurrentMeds[0], proposed_med: mockProposedMeds[0], action: "modify", interaction_warnings: [], notes: "Dose increase from 10mg to 20mg for better BP control" },
  { id: "r2", current_med: mockCurrentMeds[1], proposed_med: mockProposedMeds[1], action: "modify", interaction_warnings: [], notes: "Switch to extended-release formulation, consolidate to QD dosing" },
  { id: "r3", current_med: mockCurrentMeds[2], proposed_med: null, action: "keep", interaction_warnings: [], notes: "" },
  { id: "r4", current_med: mockCurrentMeds[3], proposed_med: null, action: "discontinue", interaction_warnings: ["Concurrent use of aspirin and warfarin increases bleeding risk"], notes: "Discontinue due to new warfarin therapy" },
  { id: "r5", current_med: mockCurrentMeds[4], proposed_med: null, action: "keep", interaction_warnings: [], notes: "" },
  { id: "r6", current_med: mockCurrentMeds[5], proposed_med: null, action: "discontinue", interaction_warnings: [], notes: "BP adequately controlled with increased lisinopril" },
  { id: "r7", current_med: null, proposed_med: mockProposedMeds[2], action: "add", interaction_warnings: [], notes: "Add SGLT2 inhibitor for cardiorenal benefit" },
  { id: "r8", current_med: null, proposed_med: mockProposedMeds[3], action: "add", interaction_warnings: ["Major interaction: warfarin + aspirin increases bleeding risk", "Monitor INR closely with atorvastatin co-administration"], notes: "New anticoagulation for atrial fibrillation" },
];

const actionConfig: Record<ReconciliationAction, { label: string; color: string; icon: React.ReactNode }> = {
  keep: { label: "Keep", color: "bg-green-100 text-green-800", icon: <CheckCircle2 className="h-3 w-3" /> },
  discontinue: { label: "Discontinue", color: "bg-red-100 text-red-800", icon: <XCircle className="h-3 w-3" /> },
  modify: { label: "Modify", color: "bg-blue-100 text-blue-800", icon: <ArrowRightLeft className="h-3 w-3" /> },
  add: { label: "Add New", color: "bg-purple-100 text-purple-800", icon: <Pill className="h-3 w-3" /> },
  pending: { label: "Pending", color: "bg-gray-100 text-gray-800", icon: null },
};

export default function MedReconciliationPage() {
  const [items, setItems] = useState<ReconciliationItem[]>(initialReconciliation);
  const [filterAction, setFilterAction] = useState<string>("all");

  const filteredItems = filterAction === "all"
    ? items
    : items.filter((i) => i.action === filterAction);

  const actionCounts = items.reduce(
    (acc, item) => {
      acc[item.action] = (acc[item.action] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  const totalWarnings = items.reduce((sum, i) => sum + i.interaction_warnings.length, 0);

  const updateAction = (id: string, action: ReconciliationAction) => {
    setItems((prev) => prev.map((i) => (i.id === id ? { ...i, action } : i)));
  };

  return (
    <div className="container mx-auto p-6 max-w-7xl">
      <div className="flex items-center gap-4 mb-6">
        <Link href="/clinical">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-1" /> Clinical
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">Medication Reconciliation</h1>
          <p className="text-muted-foreground">
            Compare and reconcile current vs. proposed medications
          </p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Items</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{items.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Keep</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{actionCounts.keep || 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Modify</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">{actionCounts.modify || 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Discontinue</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{actionCounts.discontinue || 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Warnings</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600">{totalWarnings}</div>
          </CardContent>
        </Card>
      </div>

      {/* Filter Bar */}
      <div className="flex items-center gap-2 mb-4">
        <span className="text-sm font-medium text-muted-foreground">Filter:</span>
        {["all", "keep", "modify", "discontinue", "add"].map((f) => (
          <Button
            key={f}
            variant={filterAction === f ? "default" : "outline"}
            size="sm"
            onClick={() => setFilterAction(f)}
            className="text-xs"
          >
            {f === "all" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
            {f !== "all" && actionCounts[f] ? ` (${actionCounts[f]})` : ""}
          </Button>
        ))}
      </div>

      {/* Reconciliation Table */}
      <Card>
        <CardHeader>
          <CardTitle>Reconciliation Items</CardTitle>
          <CardDescription>
            Review each medication and confirm the reconciliation action
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {filteredItems.map((item) => {
              const config = actionConfig[item.action];
              const med = item.current_med || item.proposed_med;
              return (
                <div key={item.id} className="border rounded-lg p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <Badge className={config.color}>
                          <span className="flex items-center gap-1">
                            {config.icon} {config.label}
                          </span>
                        </Badge>
                        <span className="font-semibold">
                          {item.action === "modify" && item.proposed_med
                            ? item.proposed_med.name
                            : med?.name}
                        </span>
                        {item.interaction_warnings.length > 0 && (
                          <Badge variant="destructive" className="text-xs">
                            <AlertTriangle className="h-3 w-3 mr-1" />
                            {item.interaction_warnings.length} warning{item.interaction_warnings.length > 1 ? "s" : ""}
                          </Badge>
                        )}
                      </div>

                      {/* Current vs Proposed comparison */}
                      {item.action === "modify" && item.current_med && item.proposed_med && (
                        <div className="grid grid-cols-2 gap-4 text-sm mb-2">
                          <div className="bg-red-50 dark:bg-red-950/20 rounded p-2">
                            <div className="text-xs font-medium text-red-600 mb-1">Current</div>
                            <div>{item.current_med.name} {item.current_med.dose}</div>
                            <div className="text-muted-foreground">{item.current_med.route} {item.current_med.frequency}</div>
                          </div>
                          <div className="bg-green-50 dark:bg-green-950/20 rounded p-2">
                            <div className="text-xs font-medium text-green-600 mb-1">Proposed</div>
                            <div>{item.proposed_med.name} {item.proposed_med.dose}</div>
                            <div className="text-muted-foreground">{item.proposed_med.route} {item.proposed_med.frequency}</div>
                          </div>
                        </div>
                      )}

                      {/* Single medication details */}
                      {item.action !== "modify" && med && (
                        <div className="text-sm text-muted-foreground mb-1">
                          {med.dose} {med.route} {med.frequency} — {med.indication}
                        </div>
                      )}

                      {/* Warnings */}
                      {item.interaction_warnings.length > 0 && (
                        <div className="mt-2 space-y-1">
                          {item.interaction_warnings.map((w, i) => (
                            <div key={i} className="flex items-start gap-2 text-xs text-amber-700 bg-amber-50 dark:bg-amber-950/20 rounded p-2">
                              <AlertTriangle className="h-3 w-3 mt-0.5 shrink-0" />
                              <span>{w}</span>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Notes */}
                      {item.notes && (
                        <div className="text-xs text-muted-foreground mt-2 italic">
                          {item.notes}
                        </div>
                      )}
                    </div>

                    {/* Action buttons */}
                    <div className="flex flex-col gap-1">
                      {(["keep", "modify", "discontinue"] as ReconciliationAction[]).map((action) => (
                        <Button
                          key={action}
                          variant={item.action === action ? "default" : "outline"}
                          size="sm"
                          className="text-xs w-24"
                          onClick={() => updateAction(item.id, action)}
                          disabled={item.action === "add" && action !== "discontinue"}
                        >
                          {action.charAt(0).toUpperCase() + action.slice(1)}
                        </Button>
                      ))}
                    </div>
                  </div>

                  {/* Metadata row */}
                  <div className="flex items-center gap-4 mt-3 pt-2 border-t text-xs text-muted-foreground">
                    {med && (
                      <>
                        <span>RxNorm: {med.rxnorm_code}</span>
                        <span>Prescriber: {med.prescriber}</span>
                        <span>Started: {med.start_date}</span>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
