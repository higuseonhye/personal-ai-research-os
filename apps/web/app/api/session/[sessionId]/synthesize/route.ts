import { NextResponse } from "next/server";

import { getLatestState, saveSynthesis, upsertUnknowns } from "@pa/memory-engine";
import { synthesize } from "@pa/synthesis-engine";

export async function POST(_req: Request, { params }: { params: Promise<{ sessionId: string }> }) {
  try {
    const p = await params;
    const sessionId = String(p.sessionId || "").trim();
    if (!sessionId) return NextResponse.json({ error: "missing sessionId" }, { status: 400 });

    const latest = await getLatestState(sessionId);
    const summary = synthesize({
      state: latest.state,
      insights: latest.insights,
      unknowns: latest.unknowns,
      decisions: latest.decisions,
    });

    // Persist synthesis summary.
    await saveSynthesis(sessionId, summary);

    // MVP: also refresh unknowns with top unresolved uncertainties if not present.
    if (summary.unresolvedUncertainty?.length) {
      await upsertUnknowns(sessionId, summary.unresolvedUncertainty);
    }

    return NextResponse.json({ ok: true, summary });
  } catch (e: any) {
    const msg = typeof e?.message === "string" ? e.message : String(e);
    return NextResponse.json({ error: "Failed to synthesize", detail: msg }, { status: 500 });
  }
}

