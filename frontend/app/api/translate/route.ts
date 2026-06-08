import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export async function POST(req: NextRequest) {
  const body = await req.json();
  let res: Response;
  try {
    res = await fetch(`${BACKEND}/translate/by-url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return NextResponse.json(
      { error: "後端服務無法連線，請確認後端已啟動。" },
      { status: 502 }
    );
  }

  const text = await res.text();
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    return NextResponse.json(
      { error: "保單解析失敗，請確認保單連結是否有效，或稍後再試。" },
      { status: 502 }
    );
  }

  return NextResponse.json(data, { status: res.status });
}
