"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { ClipboardCheck, ArrowLeft, ArrowRight, CheckCircle } from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";

const API_BASE = typeof window !== "undefined"
  ? "/api/v1"
  : (process.env.BACKEND_URL || "http://localhost:8080/api/v1");

interface EvalSession {
  session_id: string;
  evaluator_id: string;
  num_questions: number;
  conditions: string[];
}

interface EvalQuestion {
  index: number;
  question_id: string;
  question_text: string;
  clinical_context: string;
  category: string;
  task: string;
  responses: Record<string, string>;
  labels: string[];
}

interface SessionSummary {
  session_id: string;
  evaluator_name: string;
  specialty: string;
  status: string;
  total_questions: number;
  evaluations_completed: number;
}

export default function PhysicianEvalPage() {
  const [mode, setMode] = useState<"setup" | "evaluate" | "sessions">("sessions");
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSession, setActiveSession] = useState<EvalSession | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [question, setQuestion] = useState<EvalQuestion | null>(null);
  const [loading, setLoading] = useState(false);

  // Setup form
  const [evalName, setEvalName] = useState("");
  const [specialty, setSpecialty] = useState("Emergency Medicine");
  const [yearsExp, setYearsExp] = useState(5);

  // Scoring state
  const [scores, setScores] = useState<Record<string, Record<string, number>>>({});
  const [ranking, setRanking] = useState<string[]>([]);
  const [notes, setNotes] = useState("");

  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/research/physician-eval/sessions`);
      if (res.ok) setSessions(await res.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchSessions(); }, [fetchSessions]);

  const createSession = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/research/physician-eval/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          evaluator_name: evalName,
          specialty,
          years_experience: yearsExp,
          num_questions: 100,
        }),
      });
      if (!res.ok) throw new Error("Failed to create session");
      const data: EvalSession = await res.json();
      setActiveSession(data);
      setCurrentIndex(0);
      setMode("evaluate");
      toast.success(`Session created: ${data.num_questions} questions`);
      fetchQuestion(data.session_id, 0);
    } catch (e) {
      toast.error("Failed to create evaluation session");
    } finally {
      setLoading(false);
    }
  };

  const fetchQuestion = async (sessionId: string, index: number) => {
    try {
      const res = await fetch(
        `${API_BASE}/research/physician-eval/sessions/${sessionId}/questions/${index}`
      );
      if (!res.ok) throw new Error("Failed to fetch question");
      const q: EvalQuestion = await res.json();
      setQuestion(q);

      // Initialize scores for each label
      const initScores: Record<string, Record<string, number>> = {};
      for (const label of q.labels) {
        initScores[label] = {
          factual_correctness: 2,
          clinical_safety: 2,
          assertion_handling: 1,
          temporal_handling: 1,
        };
      }
      setScores(initScores);
      setRanking(q.labels);
      setNotes("");
    } catch {
      toast.error("Failed to load question");
    }
  };

  const submitEvaluation = async () => {
    if (!activeSession || !question) return;
    setLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/research/physician-eval/sessions/${activeSession.session_id}/evaluate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question_id: question.question_id,
            scores,
            preference_ranking: ranking,
            notes,
          }),
        }
      );
      if (!res.ok) throw new Error("Failed to submit");
      toast.success("Evaluation submitted");

      // Move to next question
      const next = currentIndex + 1;
      if (next < (activeSession?.num_questions ?? 0)) {
        setCurrentIndex(next);
        fetchQuestion(activeSession.session_id, next);
      } else {
        toast.success("All questions evaluated!");
        setMode("sessions");
        fetchSessions();
      }
    } catch {
      toast.error("Failed to submit evaluation");
    } finally {
      setLoading(false);
    }
  };

  const updateScore = (label: string, dim: string, value: number) => {
    setScores((prev) => ({
      ...prev,
      [label]: { ...prev[label], [dim]: value },
    }));
  };

  const moveRank = (label: string, direction: -1 | 1) => {
    setRanking((prev) => {
      const idx = prev.indexOf(label);
      const newIdx = idx + direction;
      if (newIdx < 0 || newIdx >= prev.length) return prev;
      const arr = [...prev];
      [arr[idx], arr[newIdx]] = [arr[newIdx], arr[idx]];
      return arr;
    });
  };

  // Sessions list view
  if (mode === "sessions") {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
        <header className="border-b bg-white dark:bg-zinc-950">
          <div className="container mx-auto px-4 py-4">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold flex items-center gap-2">
                  <ClipboardCheck className="h-6 w-6" />
                  Physician Evaluation
                </h1>
                <p className="text-sm text-muted-foreground mt-1">
                  Blind evaluation of clinical QA responses across ablation conditions
                </p>
              </div>
              <div className="flex gap-2">
                <Link href="/research">
                  <Button variant="outline">Back to Research Lab</Button>
                </Link>
                <Button onClick={() => setMode("setup")}>New Evaluation</Button>
              </div>
            </div>
          </div>
        </header>

        <div className="container mx-auto px-4 py-6">
          <div className="grid gap-4">
            {sessions.length === 0 ? (
              <Card>
                <CardContent className="py-12 text-center text-muted-foreground">
                  No evaluation sessions yet. Click &ldquo;New Evaluation&rdquo; to start.
                </CardContent>
              </Card>
            ) : (
              sessions.map((s) => (
                <Card key={s.session_id}>
                  <CardContent className="py-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">{s.evaluator_name}</p>
                        <p className="text-sm text-muted-foreground">
                          {s.specialty} &middot; {s.evaluations_completed}/{s.total_questions} questions
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs px-2 py-1 rounded ${
                          s.status === "completed"
                            ? "bg-green-100 text-green-700"
                            : "bg-yellow-100 text-yellow-700"
                        }`}>
                          {s.status}
                        </span>
                        {s.status !== "completed" && (
                          <Button
                            size="sm"
                            onClick={() => {
                              setActiveSession({
                                session_id: s.session_id,
                                evaluator_id: "",
                                num_questions: s.total_questions,
                                conditions: [],
                              });
                              setCurrentIndex(s.evaluations_completed);
                              fetchQuestion(s.session_id, s.evaluations_completed);
                              setMode("evaluate");
                            }}
                          >
                            Resume
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </div>
      </div>
    );
  }

  // Setup view
  if (mode === "setup") {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
        <header className="border-b bg-white dark:bg-zinc-950">
          <div className="container mx-auto px-4 py-4">
            <h1 className="text-2xl font-bold">New Evaluation Session</h1>
          </div>
        </header>
        <div className="container mx-auto px-4 py-6 max-w-lg">
          <Card>
            <CardHeader>
              <CardTitle>Evaluator Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>Name</Label>
                <Input value={evalName} onChange={(e) => setEvalName(e.target.value)} placeholder="Dr. Jane Smith" />
              </div>
              <div>
                <Label>Specialty</Label>
                <Select value={specialty} onValueChange={setSpecialty}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Emergency Medicine">Emergency Medicine</SelectItem>
                    <SelectItem value="Internal Medicine">Internal Medicine</SelectItem>
                    <SelectItem value="Critical Care">Critical Care</SelectItem>
                    <SelectItem value="Cardiology">Cardiology</SelectItem>
                    <SelectItem value="Pulmonology">Pulmonology</SelectItem>
                    <SelectItem value="Other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Years of Experience</Label>
                <Input type="number" value={yearsExp} onChange={(e) => setYearsExp(parseInt(e.target.value) || 0)} />
              </div>
              <div className="flex gap-2 pt-4">
                <Button variant="outline" onClick={() => setMode("sessions")}>Cancel</Button>
                <Button onClick={createSession} disabled={!evalName || loading}>
                  {loading ? "Creating..." : "Start Evaluation"}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  // Evaluation view
  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-lg font-bold">
              Question {currentIndex + 1} of {activeSession?.num_questions ?? "?"}
            </h1>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                {question?.category} ({question?.task})
              </span>
              <Button variant="outline" size="sm" onClick={() => { setMode("sessions"); fetchSessions(); }}>
                Exit
              </Button>
            </div>
          </div>
          <div className="w-full bg-zinc-200 rounded-full h-2 mt-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all"
              style={{ width: `${((currentIndex + 1) / (activeSession?.num_questions ?? 1)) * 100}%` }}
            />
          </div>
        </div>
      </header>

      {question && (
        <div className="container mx-auto px-4 py-6 space-y-6">
          {/* Question */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Clinical Question</CardTitle>
            </CardHeader>
            <CardContent>
              {question.clinical_context && (
                <p className="text-sm text-muted-foreground mb-3">{question.clinical_context}</p>
              )}
              <p className="font-medium">{question.question_text}</p>
            </CardContent>
          </Card>

          {/* Responses (blind) */}
          <div className="grid gap-4 md:grid-cols-3">
            {question.labels.map((label) => (
              <Card key={label} className="border-2">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">Response {label}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm whitespace-pre-wrap">
                    {question.responses[label] || "(No response)"}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Scoring */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Score Each Response</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2 pr-4">Dimension</th>
                      {question.labels.map((l) => (
                        <th key={l} className="text-center py-2 px-2">Response {l}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { key: "factual_correctness", label: "Factual Correctness", max: 3 },
                      { key: "clinical_safety", label: "Clinical Safety", max: 3 },
                      { key: "assertion_handling", label: "Assertion Handling", max: 2 },
                      { key: "temporal_handling", label: "Temporal Handling", max: 2 },
                    ].map((dim) => (
                      <tr key={dim.key} className="border-b">
                        <td className="py-3 pr-4">
                          {dim.label} <span className="text-muted-foreground">(0-{dim.max})</span>
                        </td>
                        {question.labels.map((label) => (
                          <td key={label} className="text-center py-3 px-2">
                            <div className="flex items-center justify-center gap-2">
                              <Slider
                                min={0}
                                max={dim.max}
                                step={1}
                                value={[scores[label]?.[dim.key] ?? 0]}
                                onValueChange={([v]) => updateScore(label, dim.key, v)}
                                className="w-20"
                              />
                              <span className="w-4 text-center font-mono">
                                {scores[label]?.[dim.key] ?? 0}
                              </span>
                            </div>
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Preference Ranking */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Preference Ranking (best first)</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2 items-center">
                {ranking.map((label, idx) => (
                  <div key={label} className="flex items-center gap-1">
                    <span className="font-mono bg-zinc-100 dark:bg-zinc-800 px-3 py-1 rounded">
                      #{idx + 1}: {label}
                    </span>
                    <div className="flex flex-col">
                      <Button size="sm" variant="ghost" className="h-5 px-1" onClick={() => moveRank(label, -1)} disabled={idx === 0}>
                        <ArrowLeft className="h-3 w-3" />
                      </Button>
                      <Button size="sm" variant="ghost" className="h-5 px-1" onClick={() => moveRank(label, 1)} disabled={idx === ranking.length - 1}>
                        <ArrowRight className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Notes */}
          <div>
            <Label>Notes (optional)</Label>
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Any observations..." />
          </div>

          {/* Submit */}
          <div className="flex justify-end gap-2">
            <Button
              onClick={submitEvaluation}
              disabled={loading}
              className="gap-2"
            >
              <CheckCircle className="h-4 w-4" />
              {loading ? "Submitting..." : "Submit & Next"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
