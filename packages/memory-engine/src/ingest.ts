import type { InsightNode } from "@pa/reasoning-engine";
import { InsightNodeSchema } from "@pa/reasoning-engine";

import { appendInsight } from "./repo";
import type { SessionId } from "./types";

export type InboxItem =
  | { kind: "text"; text: string; source?: string }
  | { kind: "url"; url: string }
  | { kind: "github"; url: string }
  | { kind: "note"; title?: string; text: string };

function isGithubUrl(url: string): boolean {
  return /^https?:\/\/(www\.)?github\.com\/[^/]+\/[^/]+/i.test(url.trim());
}

function summarizeClaim(text: string): string {
  const cleaned = (text || "").trim().replace(/\s+/g, " ");
  if (!cleaned) return "No content provided.";
  // Heuristic: first sentence-ish chunk.
  const cut = cleaned.split(/(?<=[.!?])\s+/)[0] || cleaned;
  return cut.slice(0, 240);
}

function whyRelevantHeuristic(text: string): string {
  const cleaned = (text || "").trim();
  if (!cleaned) return "Added as a research artifact to preserve exploration context.";
  return "Captured to preserve reasoning context; extract unknowns, constraints, and next actions from this item.";
}

export function toInsightNode(item: InboxItem): InsightNode {
  if (item.kind === "url") {
    const url = item.url.trim();
    const kind = isGithubUrl(url) ? "repo" : "url";
    return InsightNodeSchema.parse({
      source: url,
      type: kind,
      mainClaim: `Source captured: ${url}`,
      whyRelevant: "Used to ground the research state with a concrete external reference.",
      possibleApplications: ["Ground assumptions", "Extract constraints", "Derive experiment ideas"],
      relatedTopics: kind === "repo" ? ["codebase", "implementation details"] : ["reference"],
      openQuestions: ["What is the key claim or technique in this source?", "What assumptions does it rely on?"],
      confidence: 0.6,
    });
  }

  if (item.kind === "github") {
    const url = item.url.trim();
    return InsightNodeSchema.parse({
      source: url,
      type: "repo",
      mainClaim: `Repository captured: ${url}`,
      whyRelevant: "Used to preserve implementation context and surface integration unknowns.",
      possibleApplications: ["Extract architecture", "Find evaluation hooks", "Identify missing components"],
      relatedTopics: ["codebase", "architecture", "dependencies"],
      openQuestions: ["What part of this repo is relevant to the current goal?", "What is uncertain or missing?"],
      confidence: 0.65,
    });
  }

  const text = item.kind === "text" ? item.text : item.text;
  const src =
    item.kind === "text"
      ? item.source || "pasted_text"
      : item.title
        ? `note:${item.title}`
        : "note";
  const mainClaim = summarizeClaim(text);

  return InsightNodeSchema.parse({
    source: src,
    type: item.kind === "note" ? "note" : "text",
    mainClaim,
    whyRelevant: whyRelevantHeuristic(text),
    possibleApplications: ["Turn into Unknowns", "Add to DecisionJournal", "Update candidate paths"],
    relatedTopics: [],
    openQuestions: ["What does this change in our current model?", "What remains uncertain after this?"],
    confidence: 0.55,
  });
}

export async function ingestInboxItem(sessionId: SessionId, item: InboxItem): Promise<InsightNode> {
  const node = toInsightNode(item);
  await appendInsight(sessionId, node);
  return node;
}

