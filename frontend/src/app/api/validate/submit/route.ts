import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

interface SubmitBody {
  reviewer: string;
  item_id: string;
  question_id: string;
  condition: string;
  model: string;
  gold_standard_correct: "yes" | "no" | "partially" | "needs_revision";
  model_answer_rating: "correct" | "incorrect" | "partially_correct";
  auto_score_fair: "yes" | "too_high" | "too_low";
  clinical_safety: "safe" | "minor_concern" | "potentially_harmful";
  clinical_utility: "helpful" | "neutral" | "not_useful" | "misleading";
  notes: string;
}

const VALIDATIONS_PATH = path.join(
  process.cwd(),
  "..",
  "backend",
  "data",
  "benchmarks",
  "results",
  "human_validations.jsonl"
);

export async function POST(request: NextRequest) {
  try {
    const body: SubmitBody = await request.json();

    if (!body.reviewer || !body.item_id) {
      return NextResponse.json(
        { error: "reviewer and item_id are required" },
        { status: 400 }
      );
    }

    const entry = {
      ...body,
      timestamp: new Date().toISOString(),
    };

    fs.appendFileSync(VALIDATIONS_PATH, JSON.stringify(entry) + "\n", "utf-8");

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Failed to save validation:", error);
    return NextResponse.json(
      { error: "Failed to save validation" },
      { status: 500 }
    );
  }
}

export async function GET() {
  try {
    if (!fs.existsSync(VALIDATIONS_PATH)) {
      return NextResponse.json({ validations: [] });
    }
    const lines = fs
      .readFileSync(VALIDATIONS_PATH, "utf-8")
      .trim()
      .split("\n")
      .filter(Boolean);
    const validations = lines.map((line) => JSON.parse(line));
    return NextResponse.json({ validations });
  } catch (error) {
    console.error("Failed to read validations:", error);
    return NextResponse.json(
      { error: "Failed to read validations" },
      { status: 500 }
    );
  }
}
