import { NextRequest, NextResponse } from "next/server";
import { BACKEND } from "@/app/api/_lib/backend";

export async function POST(req: NextRequest) {
  const formData = await req.formData();
  const res = await fetch(`${BACKEND}/health-check`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) return NextResponse.json({ error: "failed" }, { status: 500 });
  return NextResponse.json(await res.json());
}
