import { z } from "zod";

export const SeveritySchema = z.enum(["low", "medium", "high"]);
export type Severity = z.infer<typeof SeveritySchema>;

export const UnknownSchema = z.object({
  description: z.string().min(1),
  severity: SeveritySchema,
  blockingDegree: z.number().int().min(0).max(10),
  proposedResolution: z.string().min(1).optional(),
});
export type Unknown = z.infer<typeof UnknownSchema>;

export const DecisionRecordSchema = z.object({
  decision: z.string().min(1),
  rationale: z.string().min(1),
  tradeoffs: z.array(z.string().min(1)).default([]),
  rejectedAlternatives: z.array(z.string().min(1)).optional(),
  revisitCondition: z.string().min(1).optional(),
});
export type DecisionRecord = z.infer<typeof DecisionRecordSchema>;

export const InsightNodeSchema = z.object({
  source: z.string().min(1),
  type: z.string().min(1), // url | pdf | note | paper | repo | meeting | etc.
  mainClaim: z.string().min(1),
  whyRelevant: z.string().min(1),
  possibleApplications: z.array(z.string().min(1)).default([]),
  relatedTopics: z.array(z.string().min(1)).default([]),
  openQuestions: z.array(z.string().min(1)).optional(),
  confidence: z.number().min(0).max(1).optional(),
});
export type InsightNode = z.infer<typeof InsightNodeSchema>;

export const ResearchStateSchema = z.object({
  problem: z.string().min(1),
  currentGoal: z.string().min(1),
  knowns: z.array(z.string().min(1)).default([]),
  unknowns: z.array(z.string().min(1)).default([]),
  assumptions: z.array(z.string().min(1)).default([]),
  constraints: z.array(z.string().min(1)).default([]),
  candidatePaths: z.array(z.string().min(1)).default([]),
  blockedBy: z.array(z.string().min(1)).default([]),
  nextExperiment: z.string().min(1).optional(),
  confidence: z.number().min(0).max(1).optional(),
});
export type ResearchState = z.infer<typeof ResearchStateSchema>;

export const SynthesisSummarySchema = z.object({
  recurringThemes: z.array(z.string().min(1)).default([]),
  crossLinks: z.array(z.string().min(1)).default([]),
  unresolvedUncertainty: z.array(UnknownSchema).default([]),
  dangerousAssumptions: z.array(z.string().min(1)).default([]),
  continuityWarnings: z.array(z.string().min(1)).default([]),
  nextBestActions: z.array(z.string().min(1)).default([]),
});
export type SynthesisSummary = z.infer<typeof SynthesisSummarySchema>;

