import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

interface Question {
  question_id: string;
  task: string;
  subtype: string;
  question: string;
  expected_answer: string;
  clinical_context: string;
  difficulty: string;
  mimic_subject_id?: number;
  metadata: {
    assertion?: string;
    domain?: string;
    section?: string;
    confidence?: number;
    hadm_1?: string;
    hadm_2?: string;
  };
}

interface CheckpointEntry {
  condition: string;
  question_id: string;
  predicted_answer: string;
  expected_answer: string;
  correct: boolean;
  score: number;
  category: string;
  latency_ms: number;
  error: string | null;
}

interface TaskFile {
  questions: Question[];
}

export interface ReviewItem {
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

interface ValidationEntry {
  reviewer: string;
  question_id: string;
  condition: string;
  model: string;
}

const BENCHMARKS_DIR = path.join(
  process.cwd(),
  "..",
  "backend",
  "data",
  "benchmarks"
);

function loadQuestions(): Map<string, Question> {
  const map = new Map<string, Question>();
  for (const taskFile of ["task_a.json", "task_b.json"]) {
    const filePath = path.join(BENCHMARKS_DIR, taskFile);
    if (!fs.existsSync(filePath)) continue;
    const data: TaskFile = JSON.parse(fs.readFileSync(filePath, "utf-8"));
    for (const q of data.questions) {
      map.set(q.question_id, q);
    }
  }
  return map;
}

function loadCheckpoint(filePath: string): CheckpointEntry[] {
  if (!fs.existsSync(filePath)) return [];
  const lines = fs
    .readFileSync(filePath, "utf-8")
    .trim()
    .split("\n")
    .filter(Boolean);
  return lines.map((line) => JSON.parse(line) as CheckpointEntry);
}

function loadExistingValidations(): ValidationEntry[] {
  const filePath = path.join(
    BENCHMARKS_DIR,
    "results",
    "human_validations.jsonl"
  );
  if (!fs.existsSync(filePath)) return [];
  const lines = fs
    .readFileSync(filePath, "utf-8")
    .trim()
    .split("\n")
    .filter(Boolean);
  return lines.map((line) => JSON.parse(line) as ValidationEntry);
}

export async function GET() {
  try {
    const questions = loadQuestions();

    const medgemmaCheckpoint = loadCheckpoint(
      path.join(BENCHMARKS_DIR, "results", "clinicalbench_checkpoint.jsonl")
    );
    const opusCheckpoint = loadCheckpoint(
      path.join(
        BENCHMARKS_DIR,
        "results",
        "opus_4_6",
        "clinicalbench_checkpoint.jsonl"
      )
    );

    const items: ReviewItem[] = [];

    for (const entry of medgemmaCheckpoint) {
      const q = questions.get(entry.question_id);
      if (!q) continue;
      const hadmIds: string[] = [];
      if (q.metadata?.hadm_1) hadmIds.push(q.metadata.hadm_1);
      if (q.metadata?.hadm_2) hadmIds.push(q.metadata.hadm_2);
      items.push({
        id: `medgemma__${entry.condition}__${entry.question_id}`,
        question_id: entry.question_id,
        condition: entry.condition,
        model: "MedGemma 27B",
        task: q.task,
        subtype: q.subtype,
        category: entry.category,
        difficulty: q.difficulty,
        question: q.question,
        clinical_context: q.clinical_context,
        expected_answer: entry.expected_answer,
        predicted_answer: entry.predicted_answer,
        auto_score: entry.score,
        auto_correct: entry.correct,
        assertion: q.metadata?.assertion || "",
        domain: q.metadata?.domain || "",
        section: q.metadata?.section || "",
        patient_id: q.mimic_subject_id ? String(q.mimic_subject_id) : "",
        hadm_ids: hadmIds,
      });
    }

    for (const entry of opusCheckpoint) {
      const q = questions.get(entry.question_id);
      if (!q) continue;
      const hadmIds: string[] = [];
      if (q.metadata?.hadm_1) hadmIds.push(q.metadata.hadm_1);
      if (q.metadata?.hadm_2) hadmIds.push(q.metadata.hadm_2);
      items.push({
        id: `opus__${entry.condition}__${entry.question_id}`,
        question_id: entry.question_id,
        condition: entry.condition,
        model: "Claude Opus 4.6",
        task: q.task,
        subtype: q.subtype,
        category: entry.category,
        difficulty: q.difficulty,
        question: q.question,
        clinical_context: q.clinical_context,
        expected_answer: entry.expected_answer,
        predicted_answer: entry.predicted_answer,
        auto_score: entry.score,
        auto_correct: entry.correct,
        assertion: q.metadata?.assertion || "",
        domain: q.metadata?.domain || "",
        section: q.metadata?.section || "",
        patient_id: q.mimic_subject_id ? String(q.mimic_subject_id) : "",
        hadm_ids: hadmIds,
      });
    }

    // Sort: score=0 first, then score=1, then partials
    items.sort((a, b) => {
      const aPriority = a.auto_score === 0 ? 0 : a.auto_score === 1 ? 1 : 2;
      const bPriority = b.auto_score === 0 ? 0 : b.auto_score === 1 ? 1 : 2;
      return aPriority - bPriority;
    });

    const validations = loadExistingValidations();

    return NextResponse.json({
      items,
      total: items.length,
      validations_count: validations.length,
    });
  } catch (error) {
    console.error("Failed to load validation data:", error);
    return NextResponse.json(
      { error: "Failed to load validation data" },
      { status: 500 }
    );
  }
}
