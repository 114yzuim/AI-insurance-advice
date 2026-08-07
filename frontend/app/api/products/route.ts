import { NextRequest, NextResponse } from "next/server";
import { BACKEND } from "@/app/api/_lib/backend";

export async function GET(req: NextRequest) {
  const params = req.nextUrl.searchParams.toString();
  const url = params ? `${BACKEND}/products?${params}` : `${BACKEND}/products`;
  const res = await fetch(url, { cache: "no-store" });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
