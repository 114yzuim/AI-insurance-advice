import { NextRequest, NextResponse } from "next/server";
import { BACKEND } from "@/app/api/_lib/backend";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const res = await fetch(`${BACKEND}/claims`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) return NextResponse.json({ error: "failed" }, { status: 500 });
  return NextResponse.json(await res.json());
}
