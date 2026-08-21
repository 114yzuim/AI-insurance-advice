import { NextResponse } from "next/server";
import { BACKEND } from "@/app/api/_lib/backend";

export async function GET() {
  const res = await fetch(`${BACKEND}/products/inventory-summary`, { cache: "no-store" });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
