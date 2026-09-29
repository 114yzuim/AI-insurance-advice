import { NextRequest, NextResponse } from "next/server";
import { BACKEND } from "@/app/api/_lib/backend";

export async function POST(req: NextRequest) {
  const body = await req.json();
  try {
    const res = await fetch(`${BACKEND}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(90_000),
    });
    if (!res.ok) {
      return NextResponse.json(
        { error: "AI 服務暫時無法回覆，請稍後再試。" },
        { status: res.status },
      );
    }
    const data = await res.json().catch(() => null);
    if (typeof data?.reply !== "string" || !data.reply.trim()) {
      return NextResponse.json(
        { error: "AI 未傳回有效內容，請重新送出。" },
        { status: 502 },
      );
    }
    return NextResponse.json(data);
  } catch (error) {
    const timedOut = error instanceof Error && error.name === "TimeoutError";
    return NextResponse.json(
      { error: timedOut ? "AI 回覆逾時，請稍後再試。" : "目前無法連線到 AI 服務，請稍後再試。" },
      { status: timedOut ? 504 : 503 },
    );
  }
}
