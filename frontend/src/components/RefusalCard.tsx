"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  XCircle,
  Phone,
  ShieldAlert,
  UserCheck,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import type { DegradedState } from "@/components/DegradedBanner";

// ---------------------------------------------------------------------------
// RefusalCard - shown when the backend declines a clinical response
// ---------------------------------------------------------------------------

interface RefusalCardProps {
  state: DegradedState;
  className?: string;
}

export function RefusalCard({ state, className }: RefusalCardProps) {
  const [isRequesting, setIsRequesting] = useState(false);

  if (!state.declined) return null;

  const handleRequestReview = () => {
    setIsRequesting(true);
    // Log the clinician review request (UI-only action)
    console.info("[RefusalCard] Clinician review requested", {
      decline_reason: state.decline_reason,
      escalation_path: state.escalation_path,
      timestamp: new Date().toISOString(),
    });
    toast.info("Clinician review requested. This has been logged for follow-up.");
    setTimeout(() => setIsRequesting(false), 1500);
  };

  return (
    <Card
      className={cn(
        "border-2 border-red-500 bg-red-50 dark:border-red-700 dark:bg-red-950",
        className
      )}
      // Block copy/paste of declined content
      onCopy={(e) => {
        e.preventDefault();
        toast.warning("Copying declined clinical content is not permitted.");
      }}
    >
      <CardContent className="py-5 space-y-4">
        {/* Header */}
        <div className="flex items-start gap-3">
          <ShieldAlert className="h-6 w-6 text-red-600 dark:text-red-400 mt-0.5 shrink-0" />
          <div className="flex-1 space-y-1">
            <div className="flex items-center gap-2">
              <p className="text-base font-bold text-red-800 dark:text-red-200">
                Response Declined
              </p>
              <Badge variant="destructive" className="text-xs">
                Blocked
              </Badge>
            </div>

            {/* Decline reason */}
            {state.decline_reason && (
              <p className="text-sm text-red-700 dark:text-red-300">
                {state.decline_reason}
              </p>
            )}

            {/* Action gate details */}
            {state.action_gate && !state.action_gate.allowed && (
              <div className="flex items-center gap-2 mt-2">
                <XCircle className="h-4 w-4 text-red-500 dark:text-red-400 shrink-0" />
                <span className="text-xs text-red-700 dark:text-red-300">
                  Risk tier &quot;{state.action_gate.risk_tier}&quot; requires{" "}
                  {Math.round(state.action_gate.required_confidence * 100)}%
                  confidence (actual:{" "}
                  {Math.round(state.action_gate.actual_confidence * 100)}%)
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Escalation path */}
        <div className="flex items-center gap-2 rounded-md px-3 py-2 bg-red-100 dark:bg-red-900/50">
          <Phone className="h-4 w-4 text-red-600 dark:text-red-400 shrink-0" />
          <span className="text-sm font-medium text-red-800 dark:text-red-200">
            {state.escalation_path || "Consult treating clinician"}
          </span>
        </div>

        {/* Request clinician review button */}
        <Button
          variant="outline"
          size="sm"
          className="border-red-400 text-red-700 hover:bg-red-100 dark:border-red-600 dark:text-red-300 dark:hover:bg-red-900/50"
          onClick={handleRequestReview}
          disabled={isRequesting}
        >
          {isRequesting ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <UserCheck className="mr-2 h-4 w-4" />
          )}
          Request Clinician Review
        </Button>
      </CardContent>
    </Card>
  );
}
