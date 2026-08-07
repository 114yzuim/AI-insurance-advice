import { NextRequest, NextResponse } from "next/server";
import { BACKEND } from "@/app/api/_lib/backend";

export async function POST(req: NextRequest) {
  const formData = await req.formData();
  const res = await fetch(`${BACKEND}/translate/by-file`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const text = await res.text();
    return NextResponse.json({ error: text }, { status: res.status });
  }
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
