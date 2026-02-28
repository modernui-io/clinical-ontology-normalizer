import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const ADJUDICATION_VALIDATIONS_PATH = path.join(
  process.cwd(),
  "..",
  "backend",
  "data",
  "benchmarks",
  "results",
  "physician_adjudication",
  "adjudication_validations.jsonl"
);

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

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

    // Ensure directory exists
    const dir = path.dirname(ADJUDICATION_VALIDATIONS_PATH);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    fs.appendFileSync(
      ADJUDICATION_VALIDATIONS_PATH,
      JSON.stringify(entry) + "\n",
      "utf-8"
    );

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Failed to save adjudication validation:", error);
    return NextResponse.json(
      { error: "Failed to save validation" },
      { status: 500 }
    );
  }
}

export async function GET() {
  try {
    if (!fs.existsSync(ADJUDICATION_VALIDATIONS_PATH)) {
      return NextResponse.json({ validations: [] });
    }
    const lines = fs
      .readFileSync(ADJUDICATION_VALIDATIONS_PATH, "utf-8")
      .trim()
      .split("\n")
      .filter(Boolean);
    const validations = lines.map((line) => JSON.parse(line));
    return NextResponse.json({ validations });
  } catch (error) {
    console.error("Failed to read adjudication validations:", error);
    return NextResponse.json(
      { error: "Failed to read validations" },
      { status: 500 }
    );
  }
}
