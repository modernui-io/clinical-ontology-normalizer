import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL =
  process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

async function fetchDocs(patientId: string) {
  const url = `${BACKEND_URL}/api/v1/documents?patient_id=${encodeURIComponent(patientId)}&page=1&page_size=100`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) return null;
  const data = await res.json();
  return data;
}

export async function GET(request: NextRequest) {
  const patientId = request.nextUrl.searchParams.get("patient_id");
  if (!patientId) {
    return NextResponse.json(
      { error: "patient_id is required" },
      { status: 400 }
    );
  }

  try {
    // Try the raw patient_id first, then with MIMIC- prefix
    let data = await fetchDocs(patientId);
    if (!data || data.total === 0) {
      const mimicId = patientId.startsWith("MIMIC-") ? patientId : `MIMIC-${patientId}`;
      if (mimicId !== patientId) {
        data = await fetchDocs(mimicId);
      }
    }

    if (!data) {
      return NextResponse.json(
        { error: "Failed to fetch documents" },
        { status: 502 }
      );
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error("Failed to fetch patient notes:", error);
    return NextResponse.json(
      { error: "Failed to fetch patient notes from backend" },
      { status: 502 }
    );
  }
}
