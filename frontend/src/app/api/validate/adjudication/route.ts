import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

interface AdjudicationRawItem {
  item_id: string;
  question_id: string;
  category: string;
  question: string;
  expected_answer: string;
  condition_label: string;
  model_answer: string;
  _actual_condition: string;
  _auto_correct: boolean;
  _auto_score: number;
}

interface Question {
  question_id: string;
  task: string;
  subtype: string;
  question: string;
  expected_answer: string;
  clinical_context: string;
  difficulty: string;
  mimic_subject_id?: number;
  mimic_hadm_id?: number;
  metadata: {
    assertion?: string;
    domain?: string;
    section?: string;
    hadm_1?: string;
    hadm_2?: string;
  };
}

interface TaskFile {
  questions: Question[];
}

const BENCHMARKS_DIR = path.join(
  process.cwd(),
  "..",
  "backend",
  "data",
  "benchmarks"
);

const ADJUDICATION_PATH = path.join(
  BENCHMARKS_DIR,
  "results",
  "physician_adjudication",
  "adjudication_items.jsonl"
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

export async function GET() {
  try {
    if (!fs.existsSync(ADJUDICATION_PATH)) {
      return NextResponse.json(
        { error: "Adjudication items not found. Run export_physician_adjudication.py first." },
        { status: 404 }
      );
    }

    const questions = loadQuestions();
    const lines = fs
      .readFileSync(ADJUDICATION_PATH, "utf-8")
      .trim()
      .split("\n")
      .filter(Boolean);

    const items = lines.map((line) => {
      const raw: AdjudicationRawItem = JSON.parse(line);
      const q = questions.get(raw.question_id);
      const hadmIds: string[] = [];
      if (q?.metadata?.hadm_1) hadmIds.push(q.metadata.hadm_1);
      if (q?.metadata?.hadm_2) hadmIds.push(q.metadata.hadm_2);
      // Fallback: task_a questions have top-level mimic_hadm_id instead of hadm_1/hadm_2
      if (hadmIds.length === 0 && q?.mimic_hadm_id) {
        hadmIds.push(String(q.mimic_hadm_id));
      }

      return {
        id: raw.item_id,
        question_id: raw.question_id,
        // BLINDED: condition shown as A/B, not C1/C4g
        condition: `Condition_${raw.condition_label}`,
        model: "Claude Opus 4.6",
        task: q?.task || "",
        subtype: q?.subtype || "",
        category: raw.category,
        difficulty: q?.difficulty || "",
        question: raw.question,
        clinical_context: q?.clinical_context || "",
        expected_answer: raw.expected_answer,
        predicted_answer: raw.model_answer,
        // BLINDED: hide auto score from reviewers
        auto_score: -1,
        auto_correct: false,
        assertion: q?.metadata?.assertion || "",
        domain: q?.metadata?.domain || "",
        section: q?.metadata?.section || "",
        patient_id: q?.mimic_subject_id ? String(q.mimic_subject_id) : "",
        hadm_ids: hadmIds,
      };
    });

    return NextResponse.json({
      items,
      total: items.length,
      validations_count: 0,
    });
  } catch (error) {
    console.error("Failed to load adjudication data:", error);
    return NextResponse.json(
      { error: "Failed to load adjudication data" },
      { status: 500 }
    );
  }
}
