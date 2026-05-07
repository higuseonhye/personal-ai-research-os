import { NextResponse } from "next/server";

import { getLatestState } from "@pa/memory-engine";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const p = await params;
  const sessionId = String(p.sessionId || "").trim();
  if (!sessionId) return NextResponse.json({ error: "missing sessionId" }, { status: 400 });
  const latest = await getLatestState(sessionId);
  return NextResponse.json(latest);
}

