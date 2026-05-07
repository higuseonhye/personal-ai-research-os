import { createSession, getLatestState, ingestInboxItem, saveStateSnapshot, upsertUnknowns, appendDecision, saveSynthesis } from "../packages/memory-engine/dist/index.js";
import { synthesize } from "../packages/synthesis-engine/dist/index.js";

async function main() {
  const problem = "Improve RAG retrieval quality for internal docs";
  const currentGoal = "Reduce hallucination by improving grounding and retrieval precision.";

  const { sessionId } = await createSession({ problem, currentGoal });

  await saveStateSnapshot(sessionId, {
    problem,
    currentGoal,
    knowns: ["We have an internal document corpus"],
    unknowns: ["Do we have relevance labels?", "What is the noise profile?"],
    assumptions: ["Chunking policy is not the bottleneck"],
    constraints: ["low latency"],
    candidatePaths: ["hybrid retrieval", "reranker"],
    blockedBy: ["no evaluation set"],
    nextExperiment: "Create a 200-query eval set and run ablations",
    confidence: 0.35,
  });

  await ingestInboxItem(sessionId, {
    kind: "note",
    title: "RAG retrieval note",
    text: "Hybrid retrieval can improve recall on noisy corpora. Rerankers can improve precision but increase latency. Build an eval set before tuning.",
  });

  await upsertUnknowns(sessionId, [
    {
      description: "No evaluation set",
      severity: "high",
      blockingDegree: 9,
      proposedResolution: "Create a small labeled set and regression harness",
    },
    { description: "ACL enforcement in retrieval is unclear", severity: "medium", blockingDegree: 6 },
  ]);

  await appendDecision(sessionId, {
    decision: "Establish eval set before reranker tuning",
    rationale: "Avoid optimizing blindly and reduce synthesis churn",
    tradeoffs: ["slower start", "requires labeling effort"],
    revisitCondition: "Once baseline hits >=85% groundedness on eval set",
  });

  const latest = await getLatestState(sessionId);
  const summary = synthesize({
    state: latest.state,
    insights: latest.insights,
    unknowns: latest.unknowns,
    decisions: latest.decisions,
  });
  await saveSynthesis(sessionId, summary);

  console.log("Seeded session:", sessionId);
  console.log("Open http://localhost:3000 and paste sessionId to inspect (MVP).");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

