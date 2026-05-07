import { ResearchStateSchema } from "../packages/reasoning-engine/dist/domain.js";
import { synthesize } from "../packages/synthesis-engine/dist/synthesize.js";

// Minimal non-DB smoke test for synthesis and schemas.
const state = ResearchStateSchema.parse({
  problem: "Improve RAG retrieval quality for internal docs",
  currentGoal: "Reduce hallucination by improving grounding",
  knowns: ["We have an internal corpus", "Latency budget is ~2s"],
  unknowns: ["Do we have relevance labels?", "Is ACL enforced in retrieval?"],
  assumptions: ["Relevance labels match production distribution"],
  constraints: ["low latency"],
  candidatePaths: ["hybrid retrieval", "reranker"],
  blockedBy: ["no evaluation set"],
  nextExperiment: "Build a 200-query eval set and run ablations",
  confidence: 0.4,
});

const summary = synthesize({
  state,
  insights: [
    {
      source: "pasted_text",
      type: "note",
      mainClaim: "Rerankers often improve grounding but cost latency.",
      whyRelevant: "Tradeoff impacts constraints.",
      possibleApplications: ["Use reranker only on hard queries"],
      relatedTopics: ["reranking", "latency"],
      confidence: 0.6,
    },
  ],
  unknowns: [
    { description: "No evaluation set", severity: "high", blockingDegree: 9, proposedResolution: "Create labeled set" },
    { description: "ACL leakage risk", severity: "medium", blockingDegree: 6 },
  ],
  decisions: [
    {
      decision: "Start with hybrid retrieval baseline",
      rationale: "Balances recall under noise without heavy reranking upfront",
      tradeoffs: ["more tuning", "index complexity"],
      revisitCondition: "If latency exceeds 2s p95",
    },
  ],
});

console.log("OK smoke synthesis. Themes:", summary.recurringThemes.slice(0, 5));
