"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  CheckCircle,
  XCircle,
  ArrowRight,
  ArrowLeft,
  Download,
  SkipForward,
} from "lucide-react";
import { toast } from "sonner";

interface AdjudicationItem {
  item_id: string;
  question_id: string;
  category: string;
  question: string;
  expected_answer: string;
  condition_label: string;
  model_answer: string;
}

interface ScoredItem {
  item_id: string;
  physician_score: "correct" | "incorrect";
  physician_notes: string;
  scored_at: string;
}

const STORAGE_PREFIX = "adjudication_";

function getStorageKey(reviewer: string) {
  return `${STORAGE_PREFIX}${reviewer}`;
}

function loadScores(reviewer: string): Record<string, ScoredItem> {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(getStorageKey(reviewer));
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveScores(reviewer: string, scores: Record<string, ScoredItem>) {
  localStorage.setItem(getStorageKey(reviewer), JSON.stringify(scores));
}

export default function AdjudicatePage() {
  const [items, setItems] = useState<AdjudicationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [reviewer, setReviewer] = useState<string>("");
  const [currentIndex, setCurrentIndex] = useState(0);
  const [scores, setScores] = useState<Record<string, ScoredItem>>({});
  const [notes, setNotes] = useState("");
  const [filterMode, setFilterMode] = useState<"all" | "unscored" | "scored">("all");

  // Load items from public JSONL
  useEffect(() => {
    fetch("/adjudication_items.jsonl")
      .then((res) => res.text())
      .then((text) => {
        const parsed = text
          .trim()
          .split("\n")
          .map((line) => {
            const obj = JSON.parse(line);
            return {
              item_id: obj.item_id,
              question_id: obj.question_id,
              category: obj.category,
              question: obj.question,
              expected_answer: obj.expected_answer,
              condition_label: obj.condition_label,
              model_answer: obj.model_answer,
            } as AdjudicationItem;
          });
        setItems(parsed);
        setLoading(false);
      })
      .catch(() => {
        toast.error("Failed to load adjudication items");
        setLoading(false);
      });
  }, []);

  // Load scores when reviewer changes
  useEffect(() => {
    if (reviewer) {
      const saved = loadScores(reviewer);
      setScores(saved);
    }
  }, [reviewer]);

  const filteredItems = useMemo(() => {
    if (filterMode === "unscored") return items.filter((i) => !scores[i.item_id]);
    if (filterMode === "scored") return items.filter((i) => !!scores[i.item_id]);
    return items;
  }, [items, scores, filterMode]);

  const currentItem = filteredItems[currentIndex] || null;
  const totalItems = items.length;
  const scoredCount = Object.keys(scores).length;
  const currentScore = currentItem ? scores[currentItem.item_id] : null;

  const scoreItem = useCallback(
    (verdict: "correct" | "incorrect") => {
      if (!currentItem || !reviewer) return;

      const entry: ScoredItem = {
        item_id: currentItem.item_id,
        physician_score: verdict,
        physician_notes: notes,
        scored_at: new Date().toISOString(),
      };

      const updated = { ...scores, [currentItem.item_id]: entry };
      setScores(updated);
      saveScores(reviewer, updated);
      setNotes("");

      // Auto-advance to next unscored
      if (currentIndex < filteredItems.length - 1) {
        setCurrentIndex((prev) => prev + 1);
      } else {
        toast.success(`All ${filterMode === "all" ? "visible" : filterMode} items scored!`);
      }
    },
    [currentItem, reviewer, notes, scores, currentIndex, filteredItems.length, filterMode]
  );

  const jumpToNextUnscored = useCallback(() => {
    const idx = filteredItems.findIndex(
      (item, i) => i > currentIndex && !scores[item.item_id]
    );
    if (idx >= 0) {
      setCurrentIndex(idx);
      setNotes("");
    } else {
      // Wrap around
      const wrapIdx = filteredItems.findIndex((item) => !scores[item.item_id]);
      if (wrapIdx >= 0) {
        setCurrentIndex(wrapIdx);
        setNotes("");
      } else {
        toast.success("All items have been scored!");
      }
    }
  }, [filteredItems, currentIndex, scores]);

  const exportCSV = useCallback(() => {
    if (!reviewer) return;
    const rows = [["item_id", "question_id", "category", "condition_label", "physician_score", "physician_notes", "scored_at"]];
    for (const item of items) {
      const s = scores[item.item_id];
      rows.push([
        item.item_id,
        item.question_id,
        item.category,
        item.condition_label,
        s?.physician_score || "",
        (s?.physician_notes || "").replace(/"/g, '""'),
        s?.scored_at || "",
      ]);
    }
    const csv = rows.map((r) => r.map((c) => `"${c}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `adjudication_${reviewer}_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("CSV exported");
  }, [reviewer, items, scores]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!reviewer || !currentItem) return;
      if (e.target instanceof HTMLTextAreaElement) return;

      if (e.key === "c" || e.key === "1") {
        e.preventDefault();
        scoreItem("correct");
      } else if (e.key === "i" || e.key === "2") {
        e.preventDefault();
        scoreItem("incorrect");
      } else if (e.key === "ArrowRight" || e.key === "j") {
        e.preventDefault();
        if (currentIndex < filteredItems.length - 1) {
          setCurrentIndex((prev) => prev + 1);
          setNotes("");
        }
      } else if (e.key === "ArrowLeft" || e.key === "k") {
        e.preventDefault();
        if (currentIndex > 0) {
          setCurrentIndex((prev) => prev - 1);
          setNotes("");
        }
      } else if (e.key === "n") {
        e.preventDefault();
        jumpToNextUnscored();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [reviewer, currentItem, scoreItem, currentIndex, filteredItems.length, jumpToNextUnscored]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-muted-foreground">Loading adjudication items...</p>
      </div>
    );
  }

  // Reviewer selection
  if (!reviewer) {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900 flex items-center justify-center">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Physician Adjudication</CardTitle>
            <p className="text-sm text-muted-foreground">
              {totalItems} blinded items (120 questions x 2 conditions).
              Score each model answer as correct or incorrect against the expected answer.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <Select onValueChange={setReviewer}>
              <SelectTrigger>
                <SelectValue placeholder="Select reviewer..." />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="reviewer_1">Reviewer 1</SelectItem>
                <SelectItem value="reviewer_2">Reviewer 2</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Progress is saved in your browser. You can close and resume anytime.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      {/* Header */}
      <header className="border-b bg-white dark:bg-zinc-950 sticky top-0 z-10">
        <div className="container mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-bold">Adjudication</h1>
              <Badge variant="outline">{reviewer.replace("_", " ")}</Badge>
              <span className="text-sm text-muted-foreground">
                {scoredCount}/{totalItems} scored
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Select value={filterMode} onValueChange={(v) => { setFilterMode(v as typeof filterMode); setCurrentIndex(0); }}>
                <SelectTrigger className="w-[130px] h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All ({totalItems})</SelectItem>
                  <SelectItem value="unscored">Unscored ({totalItems - scoredCount})</SelectItem>
                  <SelectItem value="scored">Scored ({scoredCount})</SelectItem>
                </SelectContent>
              </Select>
              <Button variant="outline" size="sm" onClick={exportCSV}>
                <Download className="h-4 w-4 mr-1" />
                Export
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setReviewer("")}>
                Switch
              </Button>
            </div>
          </div>
          {/* Progress bar */}
          <div className="w-full bg-zinc-200 dark:bg-zinc-800 rounded-full h-2 mt-2">
            <div
              className="bg-green-600 h-2 rounded-full transition-all"
              style={{ width: `${(scoredCount / totalItems) * 100}%` }}
            />
          </div>
        </div>
      </header>

      {filteredItems.length === 0 ? (
        <div className="container mx-auto px-4 py-12 text-center">
          <p className="text-muted-foreground">
            {filterMode === "unscored"
              ? "All items scored! Switch to 'All' or 'Scored' to review."
              : "No items match this filter."}
          </p>
        </div>
      ) : currentItem ? (
        <div className="container mx-auto px-4 py-4 max-w-4xl space-y-4">
          {/* Navigation */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => { setCurrentIndex((p) => Math.max(0, p - 1)); setNotes(""); }}
                disabled={currentIndex === 0}
              >
                <ArrowLeft className="h-4 w-4" />
              </Button>
              <span className="text-sm font-mono">
                {currentIndex + 1} / {filteredItems.length}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => { setCurrentIndex((p) => Math.min(filteredItems.length - 1, p + 1)); setNotes(""); }}
                disabled={currentIndex >= filteredItems.length - 1}
              >
                <ArrowRight className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="sm" onClick={jumpToNextUnscored} title="Jump to next unscored (n)">
                <SkipForward className="h-4 w-4" />
              </Button>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="secondary">{currentItem.category}</Badge>
              <Badge variant="outline">Condition {currentItem.condition_label}</Badge>
              <span className="text-xs font-mono text-muted-foreground">{currentItem.item_id}</span>
              {currentScore && (
                <Badge variant={currentScore.physician_score === "correct" ? "default" : "destructive"}>
                  {currentScore.physician_score}
                </Badge>
              )}
            </div>
          </div>

          {/* Question */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">Clinical Question</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="font-medium text-base">{currentItem.question}</p>
            </CardContent>
          </Card>

          {/* Expected vs Model */}
          <div className="grid gap-4 md:grid-cols-2">
            <Card className="border-green-200 dark:border-green-900">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-green-700 dark:text-green-400">Expected Answer (Gold Standard)</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm whitespace-pre-wrap">{currentItem.expected_answer}</p>
              </CardContent>
            </Card>
            <Card className="border-blue-200 dark:border-blue-900">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-blue-700 dark:text-blue-400">Model Answer</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm whitespace-pre-wrap">
                  {currentItem.model_answer || "(No response / abstained)"}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Notes */}
          <Textarea
            value={currentScore?.physician_notes || notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Optional notes (disagreements, partial credit observations, gold standard issues...)"
            className="h-16"
          />

          {/* Scoring buttons */}
          <div className="flex items-center justify-center gap-4">
            <Button
              size="lg"
              variant={currentScore?.physician_score === "incorrect" ? "destructive" : "outline"}
              onClick={() => scoreItem("incorrect")}
              className="gap-2 min-w-[160px]"
            >
              <XCircle className="h-5 w-5" />
              Incorrect (I)
            </Button>
            <Button
              size="lg"
              variant={currentScore?.physician_score === "correct" ? "default" : "outline"}
              onClick={() => scoreItem("correct")}
              className="gap-2 min-w-[160px]"
            >
              <CheckCircle className="h-5 w-5" />
              Correct (C)
            </Button>
          </div>

          {/* Keyboard hint */}
          <p className="text-center text-xs text-muted-foreground">
            Keys: <kbd className="px-1 py-0.5 bg-zinc-200 dark:bg-zinc-700 rounded text-xs">C</kbd> correct,{" "}
            <kbd className="px-1 py-0.5 bg-zinc-200 dark:bg-zinc-700 rounded text-xs">I</kbd> incorrect,{" "}
            <kbd className="px-1 py-0.5 bg-zinc-200 dark:bg-zinc-700 rounded text-xs">&larr;</kbd><kbd className="px-1 py-0.5 bg-zinc-200 dark:bg-zinc-700 rounded text-xs">&rarr;</kbd> navigate,{" "}
            <kbd className="px-1 py-0.5 bg-zinc-200 dark:bg-zinc-700 rounded text-xs">N</kbd> next unscored
          </p>
        </div>
      ) : null}
    </div>
  );
}
