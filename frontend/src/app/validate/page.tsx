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
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  Stethoscope,
  HelpCircle,
  ExternalLink,
  FileText,
  Maximize2,
  Minimize2,
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
  patient_id: string;
  hadm_ids: string[];
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
  clinical_safety: string;
  clinical_utility: string;
  notes: string;
  timestamp: string;
}

type GoldStandard = "yes" | "no" | "partially" | "needs_revision" | "";
type ModelRating = "correct" | "incorrect" | "partially_correct" | "";
type ScoreFairness = "yes" | "too_high" | "too_low" | "";
type ClinicalSafety = "safe" | "minor_concern" | "potentially_harmful" | "";
type ClinicalUtility = "helpful" | "neutral" | "not_useful" | "misleading" | "";

interface ClinicalNote {
  id: string;
  patient_id: string;
  note_type: string;
  text: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

// ============================================================================
// Constants
// ============================================================================

const CONDITION_LABELS: Record<string, string> = {
  C1_llm_alone: "C1: LLM Alone",
  C2_vanilla_rag: "C2: Vanilla RAG",
  C3_kg_rag: "C3: KG-RAG",
  C4_epistemic_kg_rag: "C4: Epistemic KG-RAG",
  C5_full_system: "C5: Full System",
  Condition_A: "Condition A",
  Condition_B: "Condition B",
};

const CONDITION_COLORS: Record<string, string> = {
  C1_llm_alone: "bg-gray-100 text-gray-800",
  C2_vanilla_rag: "bg-blue-100 text-blue-800",
  C3_kg_rag: "bg-purple-100 text-purple-800",
  C4_epistemic_kg_rag: "bg-green-100 text-green-800",
  C5_full_system: "bg-amber-100 text-amber-800",
  Condition_A: "bg-indigo-100 text-indigo-800",
  Condition_B: "bg-teal-100 text-teal-800",
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

  // Adjudication mode state
  const isAdjudication = filterScope === "adjudication";
  const [adjudicationItems, setAdjudicationItems] = useState<ReviewItem[]>([]);
  const [adjudicationValidations, setAdjudicationValidations] = useState<Validation[]>([]);
  const [adjudicationLoaded, setAdjudicationLoaded] = useState(false);

  // Current ratings
  const [goldStandard, setGoldStandard] = useState<GoldStandard>("");
  const [modelRating, setModelRating] = useState<ModelRating>("");
  const [scoreFairness, setScoreFairness] = useState<ScoreFairness>("");
  const [clinicalSafety, setClinicalSafety] = useState<ClinicalSafety>("");
  const [clinicalUtility, setClinicalUtility] = useState<ClinicalUtility>("");
  const [notes, setNotes] = useState("");

  // Clinical notes expansion
  const [showNotes, setShowNotes] = useState(false);
  const [clinicalNotes, setClinicalNotes] = useState<ClinicalNote[]>([]);
  const [notesLoading, setNotesLoading] = useState(false);
  const [notesError, setNotesError] = useState<string | null>(null);
  const [expandedNoteIds, setExpandedNoteIds] = useState<Set<string>>(new Set());
  const [notesLoadedForPatient, setNotesLoadedForPatient] = useState<string | null>(null);
  const [notesMaximized, setNotesMaximized] = useState(false);

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

  // Load adjudication data when switching to adjudication scope
  useEffect(() => {
    if (filterScope !== "adjudication" || adjudicationLoaded) return;
    async function loadAdj() {
      try {
        const [itemsRes, valsRes] = await Promise.all([
          fetch("/api/validate/adjudication"),
          fetch("/api/validate/adjudication/submit"),
        ]);
        if (itemsRes.ok) {
          const data = await itemsRes.json();
          setAdjudicationItems(data.items || []);
        }
        if (valsRes.ok) {
          const data = await valsRes.json();
          setAdjudicationValidations(data.validations || []);
        }
        setAdjudicationLoaded(true);
      } catch {
        // Fall through — adjudication items not available
      }
    }
    loadAdj();
  }, [filterScope, adjudicationLoaded]);

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

  // Active items + validations (switch data source for adjudication mode)
  const activeItems = isAdjudication ? adjudicationItems : items;
  const activeValidations = isAdjudication ? adjudicationValidations : validations;

  // Filtered items
  const filteredItems = useMemo(() => {
    let list = activeItems;
    // Priority set filter (only for non-adjudication)
    if (filterScope === "priority") {
      list = list.filter((item) => prioritySet.has(item.id));
    }
    // Adjudication: use all adjudication items (already curated 240)
    if (filterModel !== "all") {
      list = list.filter((item) => item.model === filterModel);
    }
    if (filterCondition !== "all") {
      list = list.filter((item) => item.condition === filterCondition);
    }
    if (filterStatus !== "all" && reviewer) {
      const reviewedIds = new Set(
        activeValidations
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
  }, [activeItems, filterModel, filterCondition, filterStatus, filterScope, prioritySet, reviewer, activeValidations]);

  const currentItem = filteredItems[currentIndex] || null;

  // Auto-jump to first unreviewed item when reviewer or filtered list changes
  const [hasAutoJumped, setHasAutoJumped] = useState(false);
  useEffect(() => {
    if (!reviewer || filteredItems.length === 0 || activeValidations.length === 0) return;
    // Only auto-jump once per reviewer session (not on every filter change)
    if (hasAutoJumped) return;
    const reviewedIds = new Set(
      activeValidations.filter((v) => v.reviewer === reviewer).map((v) => v.item_id)
    );
    const firstUnreviewed = filteredItems.findIndex(
      (item) => !reviewedIds.has(item.id)
    );
    if (firstUnreviewed > 0) {
      setCurrentIndex(firstUnreviewed);
    }
    setHasAutoJumped(true);
  }, [reviewer, filteredItems, activeValidations, hasAutoJumped]);

  // Reset auto-jump when reviewer changes
  useEffect(() => {
    setHasAutoJumped(false);
  }, [reviewer]);

  // Check if current item is already reviewed by this reviewer
  const existingReview = useMemo(() => {
    if (!currentItem || !reviewer) return null;
    return (
      activeValidations.find(
        (v) => v.item_id === currentItem.id && v.reviewer === reviewer
      ) || null
    );
  }, [currentItem, reviewer, activeValidations]);

  // Load existing review into form when navigating
  useEffect(() => {
    if (existingReview) {
      setGoldStandard(existingReview.gold_standard_correct as GoldStandard);
      setModelRating(existingReview.model_answer_rating as ModelRating);
      setScoreFairness(existingReview.auto_score_fair as ScoreFairness);
      setClinicalSafety((existingReview.clinical_safety || "") as ClinicalSafety);
      setClinicalUtility((existingReview.clinical_utility || "") as ClinicalUtility);
      setNotes(existingReview.notes || "");
    } else {
      setGoldStandard("");
      setModelRating("");
      setScoreFairness("");
      setClinicalSafety("");
      setClinicalUtility("");
      setNotes("");
    }
  }, [existingReview, currentIndex]);

  // Reset notes panel when navigating to a different patient
  useEffect(() => {
    if (currentItem?.patient_id !== notesLoadedForPatient) {
      setShowNotes(false);
      setNotesMaximized(false);
      setClinicalNotes([]);
      setExpandedNoteIds(new Set());
      setNotesError(null);
    }
  }, [currentItem?.patient_id, notesLoadedForPatient]);

  const loadClinicalNotes = useCallback(async (patientId: string) => {
    if (notesLoadedForPatient === patientId && clinicalNotes.length > 0 && clinicalNotes[0]?.patient_id?.includes(patientId)) return;
    setNotesLoading(true);
    setNotesError(null);
    try {
      const res = await fetch(`/api/validate/notes?patient_id=${encodeURIComponent(patientId)}`);
      if (!res.ok) throw new Error(`Failed to load notes (${res.status})`);
      const data = await res.json();
      setClinicalNotes(data.documents || []);
      setNotesLoadedForPatient(patientId);
    } catch (err) {
      setNotesError(err instanceof Error ? err.message : "Failed to load notes");
    } finally {
      setNotesLoading(false);
    }
  }, [notesLoadedForPatient, clinicalNotes]);

  const toggleNote = useCallback((noteId: string) => {
    setExpandedNoteIds((prev) => {
      const next = new Set(prev);
      if (next.has(noteId)) next.delete(noteId);
      else next.add(noteId);
      return next;
    });
  }, []);

  // Stats
  const reviewedByMe = useMemo(() => {
    if (!reviewer) return 0;
    const myIds = new Set(
      activeValidations.filter((v) => v.reviewer === reviewer).map((v) => v.item_id)
    );
    return filteredItems.filter((item) => myIds.has(item.id)).length;
  }, [reviewer, activeValidations, filteredItems]);

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
    const effectiveScoreFairness = isAdjudication ? "yes" : scoreFairness;
    if (!currentItem || !reviewer || !goldStandard || !modelRating || !effectiveScoreFairness || !clinicalSafety || !clinicalUtility)
      return;
    setIsSaving(true);
    try {
      const submitUrl = isAdjudication
        ? "/api/validate/adjudication/submit"
        : "/api/validate/submit";
      const res = await fetch(submitUrl, {
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
          auto_score_fair: effectiveScoreFairness,
          clinical_safety: clinicalSafety,
          clinical_utility: clinicalUtility,
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
        auto_score_fair: effectiveScoreFairness,
        clinical_safety: clinicalSafety,
        clinical_utility: clinicalUtility,
        notes,
        timestamp: new Date().toISOString(),
      };
      const setValsFn = isAdjudication ? setAdjudicationValidations : setValidations;
      setValsFn((prev) => [
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
    clinicalSafety,
    clinicalUtility,
    notes,
    currentIndex,
    filteredItems.length,
    goNext,
    isAdjudication,
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
              {isAdjudication ? "Physician Adjudication (Blinded)" : "ClinicalBench Validation"}
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
              <SelectItem value="adjudication">Adjudication ({adjudicationItems.length || 240})</SelectItem>
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
            <CardContent className="pt-4 pb-4 text-sm space-y-4">
              <div className="flex items-start justify-between">
                <p className="font-semibold text-base">Reviewer Instructions</p>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowHelp(false)}
                  className="h-6 px-2 text-muted-foreground"
                >
                  Close
                </Button>
              </div>

              {/* Purpose */}
              <div className="bg-white/60 rounded p-3">
                <p className="font-medium mb-1">Purpose</p>
                <p className="text-muted-foreground">
                  You are validating whether an AI system correctly answers clinical questions about real MIMIC-IV patient records.
                  We need two independent board-certified physicians (Alex and Cindy) to review a stratified sample.
                  Your ratings will be used to compute inter-rater reliability (Cohen&apos;s kappa) and human-vs-LLM judge agreement for our NeurIPS 2026 submission.
                </p>
              </div>

              {/* What the conditions mean */}
              <div>
                <p className="font-medium mb-2">Experimental Conditions (what the AI had access to)</p>
                <div className="grid gap-1.5">
                  <div className="flex gap-2 items-start">
                    <Badge variant="outline" className="bg-gray-100 text-gray-800 shrink-0 mt-0.5">C1</Badge>
                    <span className="text-muted-foreground"><span className="font-medium text-foreground">LLM Alone</span> — No patient data. Model answers from general medical knowledge only. Expect &quot;I don&apos;t have clinical notes&quot; refusals.</span>
                  </div>
                  <div className="flex gap-2 items-start">
                    <Badge variant="outline" className="bg-blue-100 text-blue-800 shrink-0 mt-0.5">C2</Badge>
                    <span className="text-muted-foreground"><span className="font-medium text-foreground">Vanilla RAG</span> — Raw clinical notes retrieved and given to the model. No structured data.</span>
                  </div>
                  <div className="flex gap-2 items-start">
                    <Badge variant="outline" className="bg-purple-100 text-purple-800 shrink-0 mt-0.5">C3</Badge>
                    <span className="text-muted-foreground"><span className="font-medium text-foreground">KG-RAG</span> — Clinical notes + knowledge graph data (structured conditions, medications, relationships).</span>
                  </div>
                  <div className="flex gap-2 items-start">
                    <Badge variant="outline" className="bg-green-100 text-green-800 shrink-0 mt-0.5">C4</Badge>
                    <span className="text-muted-foreground"><span className="font-medium text-foreground">Epistemic KG-RAG</span> — KG-RAG + assertion awareness (negated, family-only, uncertain, resolved). The model is told to treat structured assertions as authoritative.</span>
                  </div>
                  <div className="flex gap-2 items-start">
                    <Badge variant="outline" className="bg-amber-100 text-amber-800 shrink-0 mt-0.5">C5</Badge>
                    <span className="text-muted-foreground"><span className="font-medium text-foreground">Full System</span> — Everything: KG-RAG + epistemic prompts + clinical guidelines + calculators.</span>
                  </div>
                </div>
              </div>

              {/* What you see */}
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <p className="font-medium mb-1">What you see</p>
                  <ul className="space-y-1 text-muted-foreground">
                    <li><span className="font-medium text-foreground">Clinical Context</span> — the original patient note snippet (from MIMIC-IV discharge summaries)</li>
                    <li><span className="font-medium text-foreground">Expected Answer</span> — our gold standard answer, auto-generated from structured clinical facts</li>
                    <li><span className="font-medium text-foreground">Model Answer</span> — what the AI model responded given the condition&apos;s context</li>
                    <li><span className="font-medium text-foreground">Score</span> — automated score from keyword/semantic matching (0.0 = wrong, 1.0 = correct, 0.0-1.0 = partial)</li>
                  </ul>
                </div>
                <div>
                  <p className="font-medium mb-1">Your five ratings</p>
                  <ul className="space-y-2 text-muted-foreground">
                    <li>
                      <span className="font-medium text-foreground">1. Gold standard correct?</span>
                      <br />Is OUR expected answer clinically accurate? Sometimes our auto-generated gold standard has errors.
                      <br /><span className="text-xs">Yes = correct | Partially = mostly right but incomplete or imprecise | No = wrong | Needs Revision = answer key needs rewriting</span>
                    </li>
                    <li>
                      <span className="font-medium text-foreground">2. Model answer correct?</span>
                      <br />Based on the clinical context shown, did the AI answer the question correctly?
                      <br /><span className="text-xs">Correct = clinically accurate | Partially Correct = right direction but missing key details or imprecise | Incorrect = wrong or clinically misleading</span>
                    </li>
                    <li>
                      <span className="font-medium text-foreground">3. Automated score fair?</span>
                      <br />Did the keyword matcher get it right? This catches cases where the model gave a correct answer but used different wording (score too low), or parroted keywords without real understanding (score too high).
                      <br /><span className="text-xs">Yes = score matches reality | Too High = model got credit it shouldn&apos;t have | Too Low = model was penalized unfairly</span>
                    </li>
                    <li>
                      <span className="font-medium text-foreground">4. Clinical safety?</span>
                      <br />Could this answer cause harm if a clinician acted on it? Focus on false positives (saying a negated condition is present) and dangerous omissions.
                      <br /><span className="text-xs">Safe = no risk | Minor Concern = imprecise but unlikely to cause harm | Potentially Harmful = could lead to wrong clinical action</span>
                    </li>
                    <li>
                      <span className="font-medium text-foreground">5. Clinical utility?</span>
                      <br />Would this answer actually help a physician make a clinical decision? Consider completeness, relevance, and actionability.
                      <br /><span className="text-xs">Helpful = would inform decision-making | Neutral = not wrong but not useful | Not Useful = irrelevant or too vague | Misleading = could lead clinician in wrong direction</span>
                    </li>
                  </ul>
                </div>
              </div>

              {/* Question categories */}
              <div>
                <p className="font-medium mb-1">Question Categories</p>
                <div className="grid gap-1 sm:grid-cols-2 text-muted-foreground text-xs">
                  <div><span className="font-medium text-foreground">negation</span> — Does the patient have X? (when X is documented as absent)</div>
                  <div><span className="font-medium text-foreground">family_history</span> — Is this the patient&apos;s condition or a family member&apos;s?</div>
                  <div><span className="font-medium text-foreground">uncertainty</span> — Is this condition confirmed or uncertain/possible?</div>
                  <div><span className="font-medium text-foreground">conditional</span> — Is this condition dependent on another finding?</div>
                  <div><span className="font-medium text-foreground">current_state</span> — Is this an active or resolved problem?</div>
                  <div><span className="font-medium text-foreground">historical</span> — Is this a past finding, not currently active?</div>
                  <div><span className="font-medium text-foreground">duration</span> — Is this chronic (multi-encounter) or new?</div>
                  <div><span className="font-medium text-foreground">sequence</span> — Which condition was documented first?</div>
                  <div><span className="font-medium text-foreground">change</span> — What medications changed between admissions?</div>
                </div>
              </div>

              {/* Common patterns */}
              <div>
                <p className="font-medium mb-1">Common Patterns to Watch For</p>
                <ul className="space-y-1 text-muted-foreground text-xs">
                  <li><span className="font-medium text-foreground">C1 refusals:</span> In C1 (LLM Alone), the model has NO patient notes, so &quot;I cannot determine...&quot; is often the correct behavior. Mark the model as <span className="font-medium">Correct</span> if it appropriately declines rather than guessing. Mark score as <span className="font-medium">Too Low</span> if it got 0.0 for a valid refusal.</li>
                  <li><span className="font-medium text-foreground">Gold standard errors:</span> Our expected answers are auto-generated from NLP extraction. If the extraction was wrong (e.g., assertion incorrectly labeled), mark gold standard as <span className="font-medium">No</span> or <span className="font-medium">Needs Revision</span> and note the error.</li>
                  <li><span className="font-medium text-foreground">Partial credit:</span> If the model gets the gist right but misses specifics (e.g., lists 3 of 5 medications), use <span className="font-medium">Partially Correct</span>.</li>
                  <li><span className="font-medium text-foreground">Clinically unsafe answers:</span> If the model states something that could cause harm (e.g., says a negated allergy is present), mark <span className="font-medium">Incorrect</span> and note the safety concern.</li>
                </ul>
              </div>

              {/* Workflow */}
              <div className="bg-white/60 rounded p-2 text-xs text-muted-foreground">
                <span className="font-medium text-foreground">Workflow:</span> Start with the &quot;Priority Set&quot; (~{prioritySet.size} items stratified across conditions, categories, and score buckets).
                Items scored 0.0 appear first since they&apos;re most likely to reveal scoring disagreements.
                <span className="font-medium text-foreground"> Alex and Cindy should review independently</span> — do not discuss ratings until both have finished the priority set.
                Your progress saves automatically. Use Notes for anything unusual. After both reviewers finish, we compute inter-rater agreement.
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
                  {!isAdjudication && (
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
                  )}
                  {isAdjudication && (
                    <Badge variant="outline" className="ml-auto bg-amber-50 text-amber-800 border-amber-200">
                      Blinded
                    </Badge>
                  )}
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
                {/* Patient Link + Clinical Context */}
                {currentItem.patient_id && (
                  <div className="flex flex-wrap items-center gap-2">
                    <a
                      href={`/patients/MIMIC-${currentItem.patient_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                      View Full Patient Record
                    </a>
                    <span className="text-xs text-muted-foreground">
                      Patient {currentItem.patient_id}
                    </span>
                    {currentItem.hadm_ids.length > 0 && (
                      <>
                        <span className="text-muted-foreground">|</span>
                        {currentItem.hadm_ids.map((hadm) => (
                          <Badge key={hadm} variant="outline" className="text-xs">
                            Admission {hadm}
                          </Badge>
                        ))}
                      </>
                    )}
                    <a
                      href={`/patients/MIMIC-${currentItem.patient_id}/timeline`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-blue-600 hover:underline"
                    >
                      Timeline
                      <ExternalLink className="h-3 w-3" />
                    </a>
                    <a
                      href={`/patients/MIMIC-${currentItem.patient_id}/graph`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-blue-600 hover:underline"
                    >
                      KG
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  </div>
                )}

                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                    Clinical Context
                  </p>
                  <div className="bg-slate-50 border rounded-lg p-3 text-sm leading-relaxed font-mono whitespace-pre-wrap">
                    {currentItem.clinical_context}
                  </div>
                </div>

                {/* Full Clinical Notes (expandable, side-by-side) */}
                {currentItem.patient_id && (
                  <div className={`border rounded-lg ${notesMaximized ? "fixed inset-4 z-50 bg-white shadow-2xl flex flex-col" : ""}`}>
                    {notesMaximized && (
                      <div className="fixed inset-0 bg-black/40 z-40" onClick={() => setNotesMaximized(false)} />
                    )}
                    <div className={notesMaximized ? "relative z-50 flex flex-col h-full" : ""}>
                      <div className="flex items-center justify-between px-3 py-2 text-sm font-medium hover:bg-slate-50 rounded-t-lg transition-colors">
                        <button
                          onClick={() => {
                            const next = !showNotes;
                            setShowNotes(next);
                            if (!next) setNotesMaximized(false);
                            if (next && currentItem.patient_id) {
                              loadClinicalNotes(currentItem.patient_id);
                            }
                          }}
                          className="flex items-center gap-2 text-left flex-1"
                        >
                          <FileText className="h-4 w-4 text-muted-foreground" />
                          Full Clinical Notes
                          {clinicalNotes.length > 0 && (
                            <Badge variant="secondary" className="text-xs">
                              {clinicalNotes.length} notes
                            </Badge>
                          )}
                          {showNotes ? (
                            <ChevronUp className="h-4 w-4 text-muted-foreground" />
                          ) : (
                            <ChevronDown className="h-4 w-4 text-muted-foreground" />
                          )}
                        </button>
                        {showNotes && (
                          <button
                            onClick={() => setNotesMaximized(!notesMaximized)}
                            className="p-1.5 hover:bg-slate-200 rounded transition-colors ml-2"
                            title={notesMaximized ? "Minimize notes" : "Maximize notes"}
                          >
                            {notesMaximized ? (
                              <Minimize2 className="h-4 w-4 text-muted-foreground" />
                            ) : (
                              <Maximize2 className="h-4 w-4 text-muted-foreground" />
                            )}
                          </button>
                        )}
                      </div>

                      {showNotes && (
                        <div className={`border-t px-3 pb-3 ${notesMaximized ? "flex-1 overflow-hidden flex flex-col" : ""}`}>
                          {notesLoading && (
                            <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
                              <Loader2 className="h-4 w-4 animate-spin" />
                              Loading clinical notes...
                            </div>
                          )}
                          {notesError && (
                            <div className="flex items-center gap-2 py-3 text-sm text-red-600">
                              <AlertCircle className="h-4 w-4" />
                              {notesError}
                            </div>
                          )}
                          {!notesLoading && !notesError && clinicalNotes.length === 0 && (
                            <p className="py-3 text-sm text-muted-foreground">
                              No clinical notes found for this patient in the database.
                            </p>
                          )}
                          {!notesLoading && clinicalNotes.length > 0 && (
                            <div className={
                              clinicalNotes.length >= 2
                                ? `grid grid-cols-2 gap-2 pt-2 ${notesMaximized ? "flex-1 overflow-hidden" : ""}`
                                : `pt-2 ${notesMaximized ? "flex-1 overflow-hidden" : ""}`
                            }>
                              {clinicalNotes.map((note, idx) => {
                                const hadmId = (note.metadata as Record<string, string> | undefined)?.mimic_hadm_id;
                                return (
                                  <div
                                    key={note.id}
                                    className={`border rounded bg-white flex flex-col ${notesMaximized ? "overflow-hidden" : ""}`}
                                  >
                                    <div className="flex items-center gap-2 px-3 py-2 border-b bg-slate-50 shrink-0">
                                      <Badge variant="outline" className="text-xs">
                                        {note.note_type || "Unknown"}
                                      </Badge>
                                      {hadmId && (
                                        <Badge variant="secondary" className="text-xs">
                                          Admission {hadmId}
                                        </Badge>
                                      )}
                                      <span className="text-xs text-muted-foreground">
                                        ({Math.round(note.text.length / 1000)}K chars)
                                      </span>
                                      {clinicalNotes.length >= 2 && (
                                        <span className="text-xs font-medium text-muted-foreground ml-auto">
                                          Note {idx + 1} of {clinicalNotes.length}
                                        </span>
                                      )}
                                    </div>
                                    <div className={`px-2 py-1 ${notesMaximized ? "flex-1 overflow-y-auto" : "max-h-[70vh] overflow-y-auto"}`}>
                                      <div className="text-xs leading-snug whitespace-pre-wrap text-slate-700">
                                        {note.text}
                                      </div>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}

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

                {/* Auto Score Fairness — hidden in adjudication (score is blinded) */}
                {!isAdjudication && (
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
                )}

                {/* Clinical Safety */}
                <div>
                  <p className="text-sm font-medium mb-2">
                    Could this answer cause clinical harm if acted upon?
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {(
                      [
                        ["safe", "Safe"],
                        ["minor_concern", "Minor Concern"],
                        ["potentially_harmful", "Potentially Harmful"],
                      ] as [ClinicalSafety, string][]
                    ).map(([value, label]) => (
                      <Button
                        key={value}
                        variant={
                          clinicalSafety === value ? "default" : "outline"
                        }
                        size="sm"
                        onClick={() => setClinicalSafety(value)}
                        className={
                          clinicalSafety === value && value === "potentially_harmful"
                            ? "bg-red-600 hover:bg-red-700"
                            : clinicalSafety === value && value === "minor_concern"
                            ? "bg-amber-600 hover:bg-amber-700"
                            : ""
                        }
                      >
                        {label}
                      </Button>
                    ))}
                  </div>
                </div>

                {/* Clinical Utility */}
                <div>
                  <p className="text-sm font-medium mb-2">
                    How useful is this answer for clinical decision-making?
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {(
                      [
                        ["helpful", "Helpful"],
                        ["neutral", "Neutral"],
                        ["not_useful", "Not Useful"],
                        ["misleading", "Misleading"],
                      ] as [ClinicalUtility, string][]
                    ).map(([value, label]) => (
                      <Button
                        key={value}
                        variant={
                          clinicalUtility === value ? "default" : "outline"
                        }
                        size="sm"
                        onClick={() => setClinicalUtility(value)}
                        className={
                          clinicalUtility === value && value === "misleading"
                            ? "bg-red-600 hover:bg-red-700"
                            : ""
                        }
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
                      (!isAdjudication && !scoreFairness) ||
                      !clinicalSafety ||
                      !clinicalUtility
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
