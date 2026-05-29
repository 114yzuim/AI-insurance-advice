import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export async function POST(req: NextRequest) {
  const formData = await req.formData();
  const res = await fetch(`${BACKEND}/chat/with-file`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) return NextResponse.json({ error: "failed" }, { status: 500 });
  return NextResponse.json(await res.json());
}
