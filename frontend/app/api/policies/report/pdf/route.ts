import { NextRequest, NextResponse } from "next/server";
import { BACKEND } from "@/app/api/_lib/backend";

export async function GET(req: NextRequest) {
  const params = new URLSearchParams(req.nextUrl.searchParams);
  const res = await fetch(`${BACKEND}/policies/report/pdf?${params.toString()}`, {
    cache: "no-store",
  });
  const data = await res.arrayBuffer();
  return new NextResponse(data, {
    status: res.status,
    headers: {
      "Content-Type": res.headers.get("Content-Type") ?? "application/pdf",
      "Content-Disposition": res.headers.get("Content-Disposition") ?? 'attachment; filename="policy-review.pdf"',
    },
  });
}
