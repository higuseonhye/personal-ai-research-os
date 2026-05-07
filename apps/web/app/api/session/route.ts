import { NextResponse } from "next/server";

import { createSession, saveStateSnapshot } from "@pa/memory-engine";

export async function POST(req: Request) {
  try {
    const body = await req.json().catch(() => ({}));
    const problem = String(body.problem || "").trim();
    const currentGoal = String(body.currentGoal || "").trim();
    if (!problem || !currentGoal) {
      return NextResponse.json({ error: "problem and currentGoal are required" }, { status: 400 });
    }

    const { sessionId } = await createSession({ problem, currentGoal });
    await saveStateSnapshot(sessionId, {
      problem,
      currentGoal,
      knowns: [],
      unknowns: [],
      assumptions: [],
      constraints: [],
      candidatePaths: [],
      blockedBy: [],
      confidence: 0.4,
    });

    return NextResponse.json({ sessionId });
  } catch (e: any) {
    const msg = typeof e?.message === "string" ? e.message : String(e);
    // Common setup issues: missing DATABASE_URL, migrations not applied, DB unreachable.
    return NextResponse.json(
      {
        error: "Failed to create session",
        detail: msg,
        hint: "Check DATABASE_URL and run: npm run prisma:generate && npm run db:migrate",
      },
      { status: 500 },
    );
  }
}

