import { NextResponse } from "next/server";

import { ingestInboxItem } from "@pa/memory-engine";

export async function POST(req: Request, { params }: { params: Promise<{ sessionId: string }> }) {
  try {
    const p = await params;
    const sessionId = String(p.sessionId || "").trim();
    if (!sessionId) return NextResponse.json({ error: "missing sessionId" }, { status: 400 });
    const body = await req.json().catch(() => ({}));
    const kind = String(body.kind || "").trim();
    if (!kind) return NextResponse.json({ error: "missing kind" }, { status: 400 });

    // Pass-through; memory-engine validates InsightNode shape.
    const node = await ingestInboxItem(sessionId, body);
    return NextResponse.json({ ok: true, node });
  } catch (e: any) {
    const msg = typeof e?.message === "string" ? e.message : String(e);
    return NextResponse.json({ error: "Failed to ingest inbox item", detail: msg }, { status: 500 });
  }
}

