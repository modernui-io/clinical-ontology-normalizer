"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  Stethoscope,
  HelpCircle,
} from "lucide-react";

// ============================================================================
// Types
// ============================================================================

interface ReviewItem {
  id: string;
  question_id: string;
  condition: string;
  model: string;
  task: string;
  subtype: string;
  category: string;
  difficulty: string;
  question: string;
  clinical_context: string;
  expected_answer: string;
  predicted_answer: string;
  auto_score: number;
  auto_correct: boolean;
  assertion: string;
  domain: string;
  section: string;
}

interface Validation {
  reviewer: string;
  item_id: string;
  question_id: string;
  condition: string;
  model: string;
  gold_standard_correct: string;
  model_answer_rating: string;
  auto_score_fair: string;
  notes: string;
  timestamp: string;
}

type GoldStandard = "yes" | "no" | "partially" | "needs_revision" | "";
type ModelRating = "correct" | "incorrect" | "partially_correct" | "";
type ScoreFairness = "yes" | "too_high" | "too_low" | "";

// ============================================================================
// Constants
// ============================================================================

const CONDITION_LABELS: Record<string, string> = {
  C1_llm_alone: "C1: LLM Alone",
  C2_vanilla_rag: "C2: Vanilla RAG",
  C3_kg_rag: "C3: KG-RAG",
  C4_epistemic_kg_rag: "C4: Epistemic KG-RAG",
  C5_full_system: "C5: Full System",
};

const CONDITION_COLORS: Record<string, string> = {
  C1_llm_alone: "bg-gray-100 text-gray-800",
  C2_vanilla_rag: "bg-blue-100 text-blue-800",
  C3_kg_rag: "bg-purple-100 text-purple-800",
  C4_epistemic_kg_rag: "bg-green-100 text-green-800",
  C5_full_system: "bg-amber-100 text-amber-800",
};

// ============================================================================
// Component
// ============================================================================

export default function ValidatePage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [validations, setValidations] = useState<Validation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isSaving, setIsSaving] = useState(false);
  const [showHelp, setShowHelp] = useState(false);

  // Reviewer — persist in localStorage
  const [reviewer, setReviewerState] = useState("");
  const setReviewer = useCallback((name: string) => {
    setReviewerState(name);
    if (name) {
      localStorage.setItem("validate_reviewer", name);
    }
  }, []);

  // Restore reviewer from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem("validate_reviewer");
    if (saved) setReviewerState(saved);
  }, []);

  // Filters
  const [filterModel, setFilterModel] = useState("all");
  const [filterCondition, setFilterCondition] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterScope, setFilterScope] = useState("priority");

  // Current ratings
  const [goldStandard, setGoldStandard] = useState<GoldStandard>("");
  const [modelRating, setModelRating] = useState<ModelRating>("");
  const [scoreFairness, setScoreFairness] = useState<ScoreFairness>("");
  const [notes, setNotes] = useState("");

  // Load data
  useEffect(() => {
    async function load() {
      try {
        const [itemsRes, valsRes] = await Promise.all([
          fetch("/api/validate"),
          fetch("/api/validate/submit"),
        ]);
        if (!itemsRes.ok) throw new Error("Failed to load items");
        const itemsData = await itemsRes.json();
        setItems(itemsData.items || []);

        if (valsRes.ok) {
          const valsData = await valsRes.json();
          setValidations(valsData.validations || []);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load data");
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, []);

  // Build priority set: ~100 items stratified across conditions, categories, scores
  const prioritySet = useMemo(() => {
    if (items.length === 0) return new Set<string>();
    // Group by condition+category+score bucket
    const buckets = new Map<string, ReviewItem[]>();
    for (const item of items) {
      const scoreBucket = item.auto_score === 0 ? "wrong" : item.auto_score === 1 ? "right" : "partial";
      const key = `${item.condition}|${item.category}|${scoreBucket}`;
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key)!.push(item);
    }
    // Take up to 2 items per bucket to get broad coverage
    const selected = new Set<string>();
    for (const [, bucket] of buckets) {
      for (let i = 0; i < Math.min(2, bucket.length); i++) {
        selected.add(bucket[i].id);
      }
    }
    return selected;
  }, [items]);

  // Filtered items
  const filteredItems = useMemo(() => {
    let list = items;
    // Priority set filter
    if (filterScope === "priority") {
      list = list.filter((item) => prioritySet.has(item.id));
    }
    if (filterModel !== "all") {
      list = list.filter((item) => item.model === filterModel);
    }
    if (filterCondition !== "all") {
      list = list.filter((item) => item.condition === filterCondition);
    }
    if (filterStatus !== "all" && reviewer) {
      const reviewedIds = new Set(
        validations
          .filter((v) => v.reviewer === reviewer)
          .map((v) => v.item_id)
      );
      if (filterStatus === "pending") {
        list = list.filter((item) => !reviewedIds.has(item.id));
      } else {
        list = list.filter((item) => reviewedIds.has(item.id));
      }
    }
    return list;
  }, [items, filterModel, filterCondition, filterStatus, filterScope, prioritySet, reviewer, validations]);

  const currentItem = filteredItems[currentIndex] || null;

  // Auto-jump to first unreviewed item when reviewer or filtered list changes
  const [hasAutoJumped, setHasAutoJumped] = useState(false);
  useEffect(() => {
    if (!reviewer || filteredItems.length === 0 || validations.length === 0) return;
    // Only auto-jump once per reviewer session (not on every filter change)
    if (hasAutoJumped) return;
    const reviewedIds = new Set(
      validations.filter((v) => v.reviewer === reviewer).map((v) => v.item_id)
    );
    const firstUnreviewed = filteredItems.findIndex(
      (item) => !reviewedIds.has(item.id)
    );
    if (firstUnreviewed > 0) {
      setCurrentIndex(firstUnreviewed);
    }
    setHasAutoJumped(true);
  }, [reviewer, filteredItems, validations, hasAutoJumped]);

  // Reset auto-jump when reviewer changes
  useEffect(() => {
    setHasAutoJumped(false);
  }, [reviewer]);

  // Check if current item is already reviewed by this reviewer
  const existingReview = useMemo(() => {
    if (!currentItem || !reviewer) return null;
    return (
      validations.find(
        (v) => v.item_id === currentItem.id && v.reviewer === reviewer
      ) || null
    );
  }, [currentItem, reviewer, validations]);

  // Load existing review into form when navigating
  useEffect(() => {
    if (existingReview) {
      setGoldStandard(existingReview.gold_standard_correct as GoldStandard);
      setModelRating(existingReview.model_answer_rating as ModelRating);
      setScoreFairness(existingReview.auto_score_fair as ScoreFairness);
      setNotes(existingReview.notes || "");
    } else {
      setGoldStandard("");
      setModelRating("");
      setScoreFairness("");
      setNotes("");
    }
  }, [existingReview, currentIndex]);

  // Stats
  const reviewedByMe = useMemo(() => {
    if (!reviewer) return 0;
    const myIds = new Set(
      validations.filter((v) => v.reviewer === reviewer).map((v) => v.item_id)
    );
    return filteredItems.filter((item) => myIds.has(item.id)).length;
  }, [reviewer, validations, filteredItems]);

  const progressPercent =
    filteredItems.length > 0
      ? Math.round((reviewedByMe / filteredItems.length) * 100)
      : 0;

  // Navigation
  const goNext = useCallback(() => {
    setCurrentIndex((i) => Math.min(i + 1, filteredItems.length - 1));
  }, [filteredItems.length]);

  const goPrev = useCallback(() => {
    setCurrentIndex((i) => Math.max(i - 1, 0));
  }, []);

  // Submit
  const handleSubmit = useCallback(async () => {
    if (!currentItem || !reviewer || !goldStandard || !modelRating || !scoreFairness)
      return;
    setIsSaving(true);
    try {
      const res = await fetch("/api/validate/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reviewer,
          item_id: currentItem.id,
          question_id: currentItem.question_id,
          condition: currentItem.condition,
          model: currentItem.model,
          gold_standard_correct: goldStandard,
          model_answer_rating: modelRating,
          auto_score_fair: scoreFairness,
          notes,
        }),
      });
      if (!res.ok) throw new Error("Save failed");

      // Update local state
      const newVal: Validation = {
        reviewer,
        item_id: currentItem.id,
        question_id: currentItem.question_id,
        condition: currentItem.condition,
        model: currentItem.model,
        gold_standard_correct: goldStandard,
        model_answer_rating: modelRating,
        auto_score_fair: scoreFairness,
        notes,
        timestamp: new Date().toISOString(),
      };
      setValidations((prev) => [
        ...prev.filter(
          (v) =>
            !(v.item_id === currentItem.id && v.reviewer === reviewer)
        ),
        newVal,
      ]);

      // Auto-advance
      if (currentIndex < filteredItems.length - 1) {
        goNext();
      }
    } catch {
      setError("Failed to save. Please try again.");
    } finally {
      setIsSaving(false);
    }
  }, [
    currentItem,
    reviewer,
    goldStandard,
    modelRating,
    scoreFairness,
    notes,
    currentIndex,
    filteredItems.length,
    goNext,
  ]);

  // Unique models and conditions for filters
  const models = useMemo(
    () => [...new Set(items.map((i) => i.model))],
    [items]
  );
  const conditions = useMemo(
    () => [...new Set(items.map((i) => i.condition))],
    [items]
  );

  // ========================================================================
  // Render
  // ========================================================================

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <span className="ml-3 text-muted-foreground">
          Loading validation data...
        </span>
      </div>
    );
  }

  if (error && items.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <XCircle className="h-12 w-12 mx-auto text-red-400 mb-4" />
          <p className="text-lg font-medium">{error}</p>
          <p className="text-sm text-muted-foreground mt-2">
            Make sure benchmark data exists in backend/data/benchmarks/
          </p>
        </div>
      </div>
    );
  }

  // Reviewer selection screen
  if (!reviewer) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <Stethoscope className="h-10 w-10 mx-auto text-primary mb-2" />
            <CardTitle>ClinicalBench Validation</CardTitle>
            <CardDescription>
              Review question/answer pairs from the ClinicalIntelligenceBench
              experiments. Your clinical expertise helps validate automated
              scoring accuracy.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Start with a priority set of ~{prioritySet.size} items
              (stratified from {items.length} total). Your progress saves
              automatically — close anytime and pick up where you left off.
            </p>
            <div className="grid gap-2">
              <Button
                variant="default"
                className="w-full"
                onClick={() => setReviewer("Alex Stinard, MD")}
              >
                Continue as Alex Stinard, MD
              </Button>
              <Button
                variant="default"
                className="w-full"
                onClick={() => setReviewer("Cindy Hird, MD")}
              >
                Continue as Cindy Hird, MD
              </Button>
              <Button
                variant="outline"
                className="w-full"
                onClick={() => {
                  const name = prompt("Enter your name:");
                  if (name?.trim()) setReviewer(name.trim());
                }}
              >
                Other reviewer...
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-4 md:p-6">
      <div className="max-w-5xl mx-auto space-y-4">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight flex items-center gap-2">
              <Stethoscope className="h-5 w-5" />
              ClinicalBench Validation
            </h1>
            <p className="text-sm text-muted-foreground">
              Reviewing as{" "}
              <span className="font-medium text-foreground">{reviewer}</span>
              {" | "}
              {reviewedByMe}/{filteredItems.length} reviewed
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setReviewer("")}
          >
            Switch reviewer
          </Button>
        </div>

        {/* Progress */}
        <Progress value={progressPercent} className="h-2" />

        {/* Filters */}
        <div className="flex flex-wrap gap-2">
          <Select value={filterScope} onValueChange={(v) => { setFilterScope(v); setCurrentIndex(0); }}>
            <SelectTrigger className="w-[200px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="priority">Priority Set ({prioritySet.size})</SelectItem>
              <SelectItem value="all">All Questions ({items.length})</SelectItem>
            </SelectContent>
          </Select>

          <Select value={filterModel} onValueChange={setFilterModel}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="All models" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All models</SelectItem>
              {models.map((m) => (
                <SelectItem key={m} value={m}>
                  {m}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={filterCondition} onValueChange={setFilterCondition}>
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="All conditions" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All conditions</SelectItem>
              {conditions.map((c) => (
                <SelectItem key={c} value={c}>
                  {CONDITION_LABELS[c] || c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={filterStatus} onValueChange={setFilterStatus}>
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder="All status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="reviewed">Reviewed</SelectItem>
            </SelectContent>
          </Select>

          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowHelp((v) => !v)}
              className="text-muted-foreground"
            >
              <HelpCircle className="h-4 w-4 mr-1" />
              Guide
            </Button>
            <span className="text-sm text-muted-foreground">
              {currentIndex + 1} / {filteredItems.length}
            </span>
          </div>
        </div>

        {showHelp && (
          <Card className="border-blue-200 bg-blue-50/50">
            <CardContent className="pt-4 pb-4 text-sm space-y-3">
              <div className="flex items-start justify-between">
                <p className="font-semibold text-base">How to Review</p>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowHelp(false)}
                  className="h-6 px-2 text-muted-foreground"
                >
                  Close
                </Button>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <p className="font-medium mb-1">What you see</p>
                  <ul className="space-y-1 text-muted-foreground">
                    <li><span className="font-medium text-foreground">Clinical Context</span> — the original patient note snippet</li>
                    <li><span className="font-medium text-foreground">Expected Answer</span> — what we defined as the correct answer (the &quot;gold standard&quot;)</li>
                    <li><span className="font-medium text-foreground">Model Answer</span> — what the AI model actually responded</li>
                    <li><span className="font-medium text-foreground">Score: 0.0 or 1.0</span> — the automated score from keyword matching (did the model&apos;s answer contain the right keywords?)</li>
                  </ul>
                </div>
                <div>
                  <p className="font-medium mb-1">What you rate</p>
                  <ul className="space-y-1 text-muted-foreground">
                    <li><span className="font-medium text-foreground">Gold standard correct?</span> — Is OUR expected answer actually right? (Yes / No / Partially / Needs Revision)</li>
                    <li><span className="font-medium text-foreground">Model answer correct?</span> — Did the AI get it right based on the clinical note? (Correct / Incorrect / Partially)</li>
                    <li><span className="font-medium text-foreground">Automated score fair?</span> — Was the 0.0 or 1.0 keyword score reasonable? (Yes / Too High / Too Low)</li>
                  </ul>
                </div>
              </div>
              <div className="bg-white/60 rounded p-2 text-xs text-muted-foreground">
                <span className="font-medium text-foreground">Tip:</span> Start with the &quot;Priority Set&quot; — a stratified sample of ~100 items covering all conditions and categories. You don&apos;t need to do all 2000+. Items with score=0 (marked wrong) appear first since they&apos;re most likely to reveal scoring problems. Your progress is saved automatically — close the browser anytime and pick up where you left off.
              </div>
            </CardContent>
          </Card>
        )}

        {!currentItem ? (
          <Card>
            <CardContent className="py-16 text-center text-muted-foreground">
              <CheckCircle2 className="h-12 w-12 mx-auto mb-4 text-green-400" />
              <p className="text-lg font-medium">No items to review</p>
              <p className="text-sm mt-1">
                Adjust filters or all items have been reviewed.
              </p>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Question Card */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <Badge
                    variant="outline"
                    className={
                      CONDITION_COLORS[currentItem.condition] ||
                      "bg-gray-100"
                    }
                  >
                    {CONDITION_LABELS[currentItem.condition] ||
                      currentItem.condition}
                  </Badge>
                  <Badge variant="secondary">{currentItem.model}</Badge>
                  <Badge variant="outline">{currentItem.category}</Badge>
                  <Badge variant="outline">{currentItem.difficulty}</Badge>
                  {currentItem.assertion && (
                    <Badge variant="outline" className="bg-yellow-50">
                      {currentItem.assertion}
                    </Badge>
                  )}
                  <div className="ml-auto flex items-center gap-1">
                    {currentItem.auto_correct ? (
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-500" />
                    )}
                    <span className="text-sm font-mono">
                      Score: {currentItem.auto_score.toFixed(1)}
                    </span>
                  </div>
                </div>
                <CardTitle className="text-lg">
                  {currentItem.question}
                </CardTitle>
                <CardDescription>
                  {currentItem.question_id} | {currentItem.section || "N/A"} |{" "}
                  {currentItem.domain || "N/A"}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Clinical Context */}
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                    Clinical Context
                  </p>
                  <div className="bg-slate-50 border rounded-lg p-3 text-sm leading-relaxed font-mono whitespace-pre-wrap">
                    {currentItem.clinical_context}
                  </div>
                </div>

                {/* Expected Answer */}
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                    Expected Answer (Gold Standard)
                  </p>
                  <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm leading-relaxed">
                    {currentItem.expected_answer}
                  </div>
                </div>

                {/* Model Answer */}
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                    Model Answer ({currentItem.model},{" "}
                    {CONDITION_LABELS[currentItem.condition] ||
                      currentItem.condition}
                    )
                  </p>
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm leading-relaxed">
                    {currentItem.predicted_answer}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Rating Card */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Your Rating</CardTitle>
                {existingReview && (
                  <CardDescription className="flex items-center gap-1 text-green-600">
                    <CheckCircle2 className="h-3 w-3" />
                    Previously reviewed — edit and resubmit to update
                  </CardDescription>
                )}
              </CardHeader>
              <CardContent className="space-y-5">
                {/* Gold Standard */}
                <div>
                  <p className="text-sm font-medium mb-2">
                    Is the expected answer clinically correct?
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {(
                      [
                        ["yes", "Yes"],
                        ["no", "No"],
                        ["partially", "Partially"],
                        ["needs_revision", "Needs Revision"],
                      ] as [GoldStandard, string][]
                    ).map(([value, label]) => (
                      <Button
                        key={value}
                        variant={
                          goldStandard === value ? "default" : "outline"
                        }
                        size="sm"
                        onClick={() => setGoldStandard(value)}
                      >
                        {label}
                      </Button>
                    ))}
                  </div>
                </div>

                {/* Model Answer Rating */}
                <div>
                  <p className="text-sm font-medium mb-2">
                    Is the model&apos;s answer correct?
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {(
                      [
                        ["correct", "Correct"],
                        ["incorrect", "Incorrect"],
                        ["partially_correct", "Partially Correct"],
                      ] as [ModelRating, string][]
                    ).map(([value, label]) => (
                      <Button
                        key={value}
                        variant={
                          modelRating === value ? "default" : "outline"
                        }
                        size="sm"
                        onClick={() => setModelRating(value)}
                      >
                        {label}
                      </Button>
                    ))}
                  </div>
                </div>

                {/* Auto Score Fairness */}
                <div>
                  <p className="text-sm font-medium mb-2">
                    Is the automated score fair?
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {(
                      [
                        ["yes", "Yes"],
                        ["too_high", "Too High"],
                        ["too_low", "Too Low"],
                      ] as [ScoreFairness, string][]
                    ).map(([value, label]) => (
                      <Button
                        key={value}
                        variant={
                          scoreFairness === value ? "default" : "outline"
                        }
                        size="sm"
                        onClick={() => setScoreFairness(value)}
                      >
                        {label}
                      </Button>
                    ))}
                  </div>
                </div>

                {/* Notes */}
                <div>
                  <p className="text-sm font-medium mb-2">
                    Notes (optional)
                  </p>
                  <Textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Any observations, corrections, or clinical reasoning notes..."
                    rows={2}
                  />
                </div>

                {/* Error display */}
                {error && (
                  <div className="flex items-center gap-2 text-sm text-red-600">
                    <AlertCircle className="h-4 w-4" />
                    {error}
                  </div>
                )}

                {/* Navigation + Submit */}
                <div className="flex items-center justify-between pt-2">
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={goPrev}
                      disabled={currentIndex === 0}
                    >
                      <ChevronLeft className="h-4 w-4 mr-1" />
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={goNext}
                      disabled={currentIndex >= filteredItems.length - 1}
                    >
                      Next
                      <ChevronRight className="h-4 w-4 ml-1" />
                    </Button>
                  </div>

                  <Button
                    onClick={handleSubmit}
                    disabled={
                      isSaving ||
                      !goldStandard ||
                      !modelRating ||
                      !scoreFairness
                    }
                  >
                    {isSaving ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      <>
                        {existingReview ? "Update & Next" : "Submit & Next"}
                      </>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
