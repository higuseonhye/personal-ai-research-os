import { NextResponse } from "next/server";

import { saveStateSnapshot } from "@pa/memory-engine";

export async function POST(req: Request, { params }: { params: Promise<{ sessionId: string }> }) {
  try {
    const p = await params;
    const sessionId = String(p.sessionId || "").trim();
    if (!sessionId) return NextResponse.json({ error: "missing sessionId" }, { status: 400 });
    const body = await req.json().catch(() => ({}));
    if (!body || !body.state) return NextResponse.json({ error: "missing state" }, { status: 400 });
    await saveStateSnapshot(sessionId, body.state);
    return NextResponse.json({ ok: true });
  } catch (e: any) {
    const msg = typeof e?.message === "string" ? e.message : String(e);
    return NextResponse.json(
      { error: "Failed to save state snapshot", detail: msg },
      { status: 500 },
    );
  }
}

