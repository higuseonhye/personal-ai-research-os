import {
  type DecisionRecord,
  type InsightNode,
  type ResearchState,
  type SynthesisSummary,
  type Unknown,
} from "@pa/reasoning-engine";
import { SynthesisSummarySchema } from "@pa/reasoning-engine";

type Inputs = {
  state: ResearchState | null;
  insights: InsightNode[];
  unknowns: Unknown[];
  decisions: DecisionRecord[];
};

const STOPWORDS = new Set([
  "the",
  "a",
  "an",
  "and",
  "or",
  "to",
  "of",
  "in",
  "on",
  "for",
  "with",
  "by",
  "is",
  "are",
  "was",
  "were",
  "be",
  "as",
  "at",
  "from",
  "that",
  "this",
  "it",
  "we",
  "you",
  "they",
  "their",
  "our",
  "your",
  "not",
  "but",
  "can",
  "may",
  "should",
  "could",
  "will",
  "would",
]);

function tokenize(text: string): string[] {
  return (text || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s\-_/]/g, " ")
    .split(/\s+/)
    .map((t) => t.trim())
    .filter((t) => t.length >= 3)
    .filter((t) => !STOPWORDS.has(t));
}

function topKeywords(texts: string[], k: number): string[] {
  const freq = new Map<string, number>();
  for (const t of texts) {
    for (const tok of tokenize(t)) {
      freq.set(tok, (freq.get(tok) || 0) + 1);
    }
  }
  return [...freq.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, k)
    .map(([w]) => w);
}

function unknownRiskScore(u: Unknown): number {
  const sev = u.severity === "high" ? 3 : u.severity === "medium" ? 2 : 1;
  return sev * (u.blockingDegree ?? 0);
}

export function synthesize(inputs: Inputs): SynthesisSummary {
  const { state, insights, unknowns, decisions } = inputs;

  const insightTexts = insights.flatMap((n) => [
    n.mainClaim,
    n.whyRelevant,
    ...(n.relatedTopics || []),
    ...(n.openQuestions || []),
  ]);
  const unkTexts = unknowns.map((u) => u.description);
  const decisionTexts = decisions.flatMap((d) => [d.decision, d.rationale, ...(d.tradeoffs || [])]);

  const recurringThemes = topKeywords(
    [
      ...(state ? [state.problem, state.currentGoal, ...(state.candidatePaths || [])] : []),
      ...insightTexts,
      ...unkTexts,
    ],
    10,
  );

  const highestRiskUnknowns = [...unknowns]
    .sort((a, b) => unknownRiskScore(b) - unknownRiskScore(a))
    .slice(0, 5);

  const dangerousAssumptions: string[] = [];
  if (state?.assumptions?.length) {
    // Simple heuristic: surface assumptions that look like guarantees.
    for (const a of state.assumptions.slice(0, 12)) {
      const al = a.toLowerCase();
      if (/(always|never|guarantee|must|obvious|trivial)/.test(al)) dangerousAssumptions.push(a);
    }
  }

  const continuityWarnings: string[] = [];
  const openPaths = state?.candidatePaths?.length ?? 0;
  const unkCount = unknowns.length;
  const decisionCount = decisions.length;
  if (openPaths >= 6) continuityWarnings.push("Exploration is diverging into too many candidate paths.");
  if (unkCount >= 8) continuityWarnings.push("Uncertainty is accumulating; prioritize the top blockers before adding new paths.");
  if (decisionCount >= 12) continuityWarnings.push("Decision journal is growing; consider consolidating decisions into 2-3 governing principles.");

  const nextBestActions: string[] = [];
  if (highestRiskUnknowns[0]) {
    nextBestActions.push(
      `Resolve top blocker: ${highestRiskUnknowns[0].description}${highestRiskUnknowns[0].proposedResolution ? ` (try: ${highestRiskUnknowns[0].proposedResolution})` : ""}`,
    );
  }
  if (state?.nextExperiment) nextBestActions.push(`Run next experiment: ${state.nextExperiment}`);
  if (!state?.nextExperiment) nextBestActions.push("Define a smallest-possible experiment to validate the highest-risk assumption.");
  if (insights.length < 3) nextBestActions.push("Add 2-3 InsightNodes from concrete sources (paper/blog/docs) to ground the exploration.");
  if (openPaths === 0) nextBestActions.push("Propose 2-3 candidate paths (approaches) and articulate tradeoffs for each.");

  const crossLinks: string[] = [];
  const kw = recurringThemes.slice(0, 6);
  if (kw.length >= 2) {
    crossLinks.push(`Cross-link: "${kw[0]}" <-> "${kw[1]}" (check how they interact under your constraints).`);
  }
  if (kw.length >= 4) {
    crossLinks.push(`Cross-link: "${kw[2]}" <-> "${kw[3]}" (possible hidden dependency).`);
  }

  const out: SynthesisSummary = {
    recurringThemes,
    crossLinks,
    unresolvedUncertainty: highestRiskUnknowns,
    dangerousAssumptions,
    continuityWarnings,
    nextBestActions,
  };

  // Validate shape for safety
  return SynthesisSummarySchema.parse(out);
}

export function decisionPressureScore(inputs: Inputs): number {
  const openPaths = inputs.state?.candidatePaths?.length ?? 0;
  const unk = inputs.unknowns.length;
  const dec = inputs.decisions.length;
  // 0..100 scale
  const score = openPaths * 8 + unk * 6 + Math.max(0, dec - 6) * 2;
  return Math.min(100, score);
}

