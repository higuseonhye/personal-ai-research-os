import { Prisma, PrismaClient } from "@prisma/client";
import type { DecisionRecordRow, InsightNodeRow, UnknownRecord } from "@prisma/client";
import {
  DecisionRecordSchema,
  InsightNodeSchema,
  ResearchStateSchema,
  SynthesisSummarySchema,
  UnknownSchema,
} from "@pa/reasoning-engine";
import type { z } from "zod";
import type {
  CreateSessionInput,
  CreateSessionResult,
  LatestState,
  SessionId,
} from "./types";

let _prisma: PrismaClient | null = null;

export function getPrisma(): PrismaClient {
  if (_prisma) return _prisma;
  _prisma = new PrismaClient();
  return _prisma;
}

export async function createSession(input: CreateSessionInput): Promise<CreateSessionResult> {
  const prisma = getPrisma();
  const row = await prisma.researchSession.create({
    data: {
      problem: input.problem,
      currentGoal: input.currentGoal,
    },
    select: { id: true },
  });
  return { sessionId: row.id };
}

export async function saveStateSnapshot(
  sessionId: SessionId,
  state: unknown,
): Promise<void> {
  const prisma = getPrisma();
  const parsed = ResearchStateSchema.parse(state);
  await prisma.researchStateSnapshot.create({
    data: {
      sessionId,
      snapshot: parsed,
      confidence: parsed.confidence ?? null,
    },
  });
}

export async function upsertUnknowns(sessionId: SessionId, unknowns: unknown[]): Promise<void> {
  const prisma = getPrisma();
  const parsed = unknowns.map((u) => UnknownSchema.parse(u));

  // MVP: wipe+insert to keep logic simple.
  await prisma.unknownRecord.deleteMany({ where: { sessionId } });
  await prisma.unknownRecord.createMany({
    data: parsed.map((u) => ({
      sessionId,
      description: u.description,
      severity: u.severity,
      blockingDegree: u.blockingDegree,
      proposedResolution: u.proposedResolution ?? null,
    })),
  });
}

export async function appendDecision(sessionId: SessionId, decision: unknown): Promise<void> {
  const prisma = getPrisma();
  const d = DecisionRecordSchema.parse(decision);
  await prisma.decisionRecordRow.create({
    data: {
      sessionId,
      decision: d.decision,
      rationale: d.rationale,
      tradeoffs: d.tradeoffs ?? [],
      rejectedAlternatives: d.rejectedAlternatives ?? Prisma.DbNull,
      revisitCondition: d.revisitCondition ?? null,
    },
  });
}

export async function appendInsight(sessionId: SessionId, insight: unknown): Promise<void> {
  const prisma = getPrisma();
  const n = InsightNodeSchema.parse(insight);
  await prisma.insightNodeRow.create({
    data: {
      sessionId,
      source: n.source,
      type: n.type,
      mainClaim: n.mainClaim,
      whyRelevant: n.whyRelevant,
      possibleApplications: n.possibleApplications ?? [],
      relatedTopics: n.relatedTopics ?? [],
      openQuestions: n.openQuestions ?? Prisma.DbNull,
      confidence: n.confidence ?? null,
    },
  });
}

export async function saveSynthesis(sessionId: SessionId, summary: unknown): Promise<void> {
  const prisma = getPrisma();
  const s = SynthesisSummarySchema.parse(summary);
  await prisma.synthesisSummaryRow.create({
    data: {
      sessionId,
      summary: s,
    },
  });
}

export async function getLatestState(sessionId: SessionId): Promise<LatestState> {
  const prisma = getPrisma();

  const [latestSnap, unknownRows, decisionRows, insightRows, synthRow] = await Promise.all([
    prisma.researchStateSnapshot.findFirst({
      where: { sessionId },
      orderBy: { createdAt: "desc" },
    }),
    prisma.unknownRecord.findMany({ where: { sessionId }, orderBy: { createdAt: "desc" } }),
    prisma.decisionRecordRow.findMany({ where: { sessionId }, orderBy: { createdAt: "desc" } }),
    prisma.insightNodeRow.findMany({ where: { sessionId }, orderBy: { createdAt: "desc" } }),
    prisma.synthesisSummaryRow.findFirst({ where: { sessionId }, orderBy: { createdAt: "desc" } }),
  ]);

  const state = latestSnap ? ResearchStateSchema.parse(latestSnap.snapshot) : null;
  const unknowns = unknownRows.map((u: UnknownRecord): z.infer<typeof UnknownSchema> =>
    UnknownSchema.parse({
      description: u.description,
      severity: u.severity,
      blockingDegree: u.blockingDegree,
      proposedResolution: u.proposedResolution ?? undefined,
    }),
  );
  const decisions = decisionRows.map((d: DecisionRecordRow): z.infer<typeof DecisionRecordSchema> =>
    DecisionRecordSchema.parse({
      decision: d.decision,
      rationale: d.rationale,
      tradeoffs: d.tradeoffs,
      rejectedAlternatives: d.rejectedAlternatives ?? undefined,
      revisitCondition: d.revisitCondition ?? undefined,
    }),
  );
  const insights = insightRows.map((n: InsightNodeRow): z.infer<typeof InsightNodeSchema> =>
    InsightNodeSchema.parse({
      source: n.source,
      type: n.type,
      mainClaim: n.mainClaim,
      whyRelevant: n.whyRelevant,
      possibleApplications: n.possibleApplications,
      relatedTopics: n.relatedTopics,
      openQuestions: n.openQuestions ?? undefined,
      confidence: n.confidence ?? undefined,
    }),
  );
  const synthesis = synthRow ? SynthesisSummarySchema.parse(synthRow.summary) : null;

  return { sessionId, state, unknowns, decisions, insights, synthesis };
}

