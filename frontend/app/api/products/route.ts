import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export async function GET(req: NextRequest) {
  const params = req.nextUrl.searchParams.toString();
  const url = params ? `${BACKEND}/products?${params}` : `${BACKEND}/products`;
  const res = await fetch(url, { cache: "no-store" });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
