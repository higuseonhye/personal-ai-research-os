import type {
  DecisionRecord,
  InsightNode,
  ResearchState,
  SynthesisSummary,
  Unknown,
} from "@pa/reasoning-engine";

export type SessionId = string;

export type CreateSessionInput = {
  problem: string;
  currentGoal: string;
};

export type CreateSessionResult = {
  sessionId: SessionId;
};

export type LatestState = {
  sessionId: SessionId;
  state: ResearchState | null;
  unknowns: Unknown[];
  decisions: DecisionRecord[];
  insights: InsightNode[];
  synthesis: SynthesisSummary | null;
};

