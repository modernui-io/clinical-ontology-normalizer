import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL =
  process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

export async function GET(request: NextRequest) {
  const patientId = request.nextUrl.searchParams.get("patient_id");
  if (!patientId) {
    return NextResponse.json(
      { error: "patient_id is required" },
      { status: 400 }
    );
  }

  try {
    const url = `${BACKEND_URL}/api/v1/documents?patient_id=${encodeURIComponent(patientId)}&page=1&page_size=100`;
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) {
      return NextResponse.json(
        { error: `Backend returned ${res.status}` },
        { status: res.status }
      );
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Failed to fetch patient notes:", error);
    return NextResponse.json(
      { error: "Failed to fetch patient notes from backend" },
      { status: 502 }
    );
  }
}
