import { NextRequest, NextResponse } from "next/server";
import { BACKEND } from "@/app/api/_lib/backend";

export async function GET(req: NextRequest) {
  const profileId = req.nextUrl.searchParams.get("profile_id") ?? "demo-user";
  const clientId = req.nextUrl.searchParams.get("client_id") ?? "";
  const params = new URLSearchParams({ profile_id: profileId });
  if (clientId) params.set("client_id", clientId);

  const res = await fetch(`${BACKEND}/claims/cases?${params.toString()}`, {
    cache: "no-store",
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const res = await fetch(`${BACKEND}/claims/cases`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
