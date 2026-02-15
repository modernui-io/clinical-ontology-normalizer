"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ThumbsUp,
  ThumbsDown,
  Star,
  Send,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type CorrectionType = "agree" | "disagree" | "partial" | "irrelevant";

interface FeedbackWidgetProps {
  queryId: string;
  responseId: string;
  className?: string;
  onSubmitted?: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FeedbackWidget({
  queryId,
  responseId,
  className,
  onSubmitted,
}: FeedbackWidgetProps) {
  const [rating, setRating] = useState<number>(0);
  const [hoverRating, setHoverRating] = useState<number>(0);
  const [correctionType, setCorrectionType] = useState<CorrectionType | null>(null);
  const [feedbackText, setFeedbackText] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async () => {
    if (rating === 0 || !correctionType) {
      toast.warning("Please provide a rating and assessment before submitting.");
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await fetch("/api/v1/clinician-feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query_id: queryId,
          response_id: responseId,
          rating,
          feedback_text: feedbackText || null,
          correction_type: correctionType,
        }),
      });

      if (!res.ok) {
        throw new Error(`Feedback submission failed: ${res.status}`);
      }

      setSubmitted(true);
      toast.success("Feedback submitted. Thank you for improving clinical accuracy.");
      onSubmitted?.();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to submit feedback";
      toast.error(msg);
      console.error("[FeedbackWidget] submit error:", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <Card className={cn("border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950", className)}>
        <CardContent className="py-3 text-center">
          <p className="text-sm font-medium text-green-700 dark:text-green-300">
            Feedback recorded. Thank you.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn("border-muted", className)}>
      <CardContent className="py-3 space-y-3">
        {/* Quick assessment row */}
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-xs text-muted-foreground font-medium">Rate this response:</span>

          {/* Thumbs up / down quick actions */}
          <div className="flex gap-1">
            <Button
              variant={correctionType === "agree" ? "default" : "ghost"}
              size="sm"
              className="h-7 w-7 p-0"
              onClick={() => {
                setCorrectionType("agree");
                if (rating === 0) setRating(5);
              }}
            >
              <ThumbsUp className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant={correctionType === "disagree" ? "destructive" : "ghost"}
              size="sm"
              className="h-7 w-7 p-0"
              onClick={() => {
                setCorrectionType("disagree");
                if (rating === 0) setRating(1);
              }}
            >
              <ThumbsDown className="h-3.5 w-3.5" />
            </Button>
          </div>

          {/* Star rating */}
          <div className="flex items-center gap-0.5">
            {[1, 2, 3, 4, 5].map((s) => (
              <button
                key={s}
                type="button"
                className="p-0.5"
                onMouseEnter={() => setHoverRating(s)}
                onMouseLeave={() => setHoverRating(0)}
                onClick={() => setRating(s)}
              >
                <Star
                  className={cn(
                    "h-4 w-4 transition-colors",
                    (hoverRating || rating) >= s
                      ? "text-amber-500 fill-amber-500"
                      : "text-muted-foreground"
                  )}
                />
              </button>
            ))}
          </div>

          {/* Correction type badges */}
          <div className="flex gap-1">
            {(
              [
                { type: "partial" as const, label: "Partial" },
                { type: "irrelevant" as const, label: "Irrelevant" },
              ] as const
            ).map(({ type, label }) => (
              <Badge
                key={type}
                variant={correctionType === type ? "default" : "outline"}
                className={cn(
                  "cursor-pointer text-xs",
                  correctionType === type && "bg-amber-500 hover:bg-amber-600"
                )}
                onClick={() => setCorrectionType(type)}
              >
                {label}
              </Badge>
            ))}
          </div>
        </div>

        {/* Optional text + submit */}
        <div className="flex items-end gap-2">
          <textarea
            value={feedbackText}
            onChange={(e) => setFeedbackText(e.target.value)}
            placeholder="Optional correction details..."
            className="flex-1 min-h-[36px] max-h-[80px] resize-y rounded-md border border-input bg-background px-3 py-1.5 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            rows={1}
          />
          <Button
            size="sm"
            onClick={handleSubmit}
            disabled={isSubmitting || rating === 0 || !correctionType}
          >
            {isSubmitting ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Send className="mr-1.5 h-3.5 w-3.5" />
            )}
            Submit
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
