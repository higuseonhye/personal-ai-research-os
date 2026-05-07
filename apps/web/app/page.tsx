"use client";

import { useEffect, useMemo, useState } from "react";

type Tab = "session" | "inbox" | "synthesis";

type LatestState = {
  sessionId: string;
  state: any | null;
  unknowns: any[];
  decisions: any[];
  insights: any[];
  synthesis: any | null;
};

async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let msg = await res.text();
    try {
      const j = JSON.parse(msg);
      msg = j.detail ? `${j.error}: ${j.detail}` : j.error || msg;
      if (j.hint) msg += `\nHint: ${j.hint}`;
    } catch {
      // ignore
    }
    throw new Error(msg);
  }
  return (await res.json()) as T;
}

export default function HomePage() {
  const [tab, setTab] = useState<Tab>("session");
  const [problem, setProblem] = useState("Improve RAG retrieval quality for internal docs");
  const [goal, setGoal] = useState("Reduce hallucination by improving grounding and retrieval precision.");
  const [sessionId, setSessionId] = useState<string>("");
  const [latest, setLatest] = useState<LatestState | null>(null);
  const [error, setError] = useState<string>("");

  const [inboxText, setInboxText] = useState("");
  const [inboxUrl, setInboxUrl] = useState("");

  const canUseApi = useMemo(() => Boolean(sessionId), [sessionId]);

  async function refresh() {
    if (!sessionId) return;
    setError("");
    try {
      const data = await jsonFetch<LatestState>(`/api/session/${sessionId}`);
      setLatest(data);
    } catch (e: any) {
      setError(String(e?.message || e));
    }
  }

  useEffect(() => {
    if (!sessionId) return;
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  async function createSession() {
    setError("");
    try {
      const out = await jsonFetch<{ sessionId: string }>(`/api/session`, {
        method: "POST",
        body: JSON.stringify({ problem, currentGoal: goal }),
      });
      setSessionId(out.sessionId);
      setTab("inbox");
    } catch (e: any) {
      setError(String(e?.message || e));
    }
  }

  async function saveStateSnapshot() {
    if (!sessionId) return;
    setError("");
    const knowns = (latest?.state?.knowns || []).join("\n");
    const unknowns = (latest?.state?.unknowns || []).join("\n");
    const assumptions = (latest?.state?.assumptions || []).join("\n");
    const constraints = (latest?.state?.constraints || []).join("\n");
    const candidatePaths = (latest?.state?.candidatePaths || []).join("\n");
    const blockedBy = (latest?.state?.blockedBy || []).join("\n");
    const nextExperiment = latest?.state?.nextExperiment || "";
    const confidence = latest?.state?.confidence ?? "";

    const state = {
      problem,
      currentGoal: goal,
      knowns: String(knowns).split("\n").map((s) => s.trim()).filter(Boolean),
      unknowns: String(unknowns).split("\n").map((s) => s.trim()).filter(Boolean),
      assumptions: String(assumptions).split("\n").map((s) => s.trim()).filter(Boolean),
      constraints: String(constraints).split("\n").map((s) => s.trim()).filter(Boolean),
      candidatePaths: String(candidatePaths).split("\n").map((s) => s.trim()).filter(Boolean),
      blockedBy: String(blockedBy).split("\n").map((s) => s.trim()).filter(Boolean),
      nextExperiment: String(nextExperiment).trim() || undefined,
      confidence: confidence === "" ? undefined : Number(confidence),
    };

    try {
      await jsonFetch(`/api/session/${sessionId}/state`, {
        method: "POST",
        body: JSON.stringify({ state }),
      });
      await refresh();
    } catch (e: any) {
      setError(String(e?.message || e));
    }
  }

  async function ingest() {
    if (!sessionId) return;
    if (!inboxText.trim() && !inboxUrl.trim()) return;
    setError("");
    const payload =
      inboxUrl.trim() !== ""
        ? { kind: "url", url: inboxUrl.trim() }
        : { kind: "text", text: inboxText.trim(), source: "pasted_text" };
    try {
      await jsonFetch(`/api/session/${sessionId}/inbox`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setInboxText("");
      setInboxUrl("");
      await refresh();
    } catch (e: any) {
      setError(String(e?.message || e));
    }
  }

  async function synthesize() {
    if (!sessionId) return;
    setError("");
    try {
      await jsonFetch(`/api/session/${sessionId}/synthesize`, { method: "POST", body: JSON.stringify({}) });
      await refresh();
      setTab("synthesis");
    } catch (e: any) {
      setError(String(e?.message || e));
    }
  }

  const state = latest?.state;
  const synthesisSummary = latest?.synthesis;

  return (
    <>
      <div className="tabs">
        <button className={`tab ${tab === "session" ? "tabActive" : ""}`} onClick={() => setTab("session")}>
          Session
        </button>
        <button className={`tab ${tab === "inbox" ? "tabActive" : ""}`} onClick={() => setTab("inbox")} disabled={!canUseApi}>
          Inbox
        </button>
        <button className={`tab ${tab === "synthesis" ? "tabActive" : ""}`} onClick={() => setTab("synthesis")} disabled={!canUseApi}>
          Synthesis
        </button>
        {sessionId ? <span className="pill">sessionId: <span className="mono">{sessionId}</span></span> : <span className="pill">no session</span>}
      </div>

      {error ? (
        <div className="panel" style={{ marginTop: 14 }}>
          <h2>Error</h2>
          <pre className="mono danger">{error}</pre>
        </div>
      ) : null}

      {tab === "session" && (
        <div className="row">
          <div className="panel">
            <h2>Define the problem</h2>
            <div className="muted">Keep it stable. The goal is continuity, not one-shot answers.</div>
            <div style={{ marginTop: 10 }}>
              <label className="muted">Problem</label>
              <textarea value={problem} onChange={(e) => setProblem(e.target.value)} />
            </div>
            <div style={{ marginTop: 10 }}>
              <label className="muted">Current goal</label>
              <textarea value={goal} onChange={(e) => setGoal(e.target.value)} />
            </div>
            <div className="btnRow">
              <button className="btn btnPrimary" onClick={() => void createSession()}>
                Create session
              </button>
              <span className="muted">Requires `DATABASE_URL` for Prisma.</span>
            </div>
          </div>

          <div className="panel">
            <h2>ResearchState (latest snapshot)</h2>
            <div className="muted">In MVP, edit via JSON view after creating session (we’ll polish later).</div>
            <div className="btnRow">
              <button className="btn" onClick={() => void refresh()} disabled={!sessionId}>
                Refresh
              </button>
              <button className="btn" onClick={() => void saveStateSnapshot()} disabled={!sessionId}>
                Save snapshot
              </button>
              <button className="btn" onClick={() => void synthesize()} disabled={!sessionId}>
                Re-synthesize
              </button>
            </div>
            <pre className="mono" style={{ marginTop: 10 }}>{JSON.stringify(state, null, 2)}</pre>
          </div>
        </div>
      )}

      {tab === "inbox" && (
        <div className="row">
          <div className="panel">
            <h2>Add an inbox item</h2>
            <div className="muted">Paste text, or add a URL/GitHub link. It becomes an InsightNode.</div>
            <div style={{ marginTop: 10 }}>
              <label className="muted">URL (optional)</label>
              <input value={inboxUrl} onChange={(e) => setInboxUrl(e.target.value)} placeholder="https://..." />
            </div>
            <div style={{ marginTop: 10 }}>
              <label className="muted">Text (optional)</label>
              <textarea value={inboxText} onChange={(e) => setInboxText(e.target.value)} placeholder="paste notes, paper excerpts, meeting notes..." />
            </div>
            <div className="btnRow">
              <button className="btn btnPrimary" onClick={() => void ingest()} disabled={!sessionId}>
                Ingest
              </button>
              <button className="btn" onClick={() => void refresh()} disabled={!sessionId}>
                Refresh
              </button>
            </div>
          </div>

          <div className="panel">
            <h2>Latest InsightNodes</h2>
            {latest?.insights?.length ? (
              <ul className="list">
                {latest.insights.slice(0, 12).map((n, i) => (
                  <li key={i}>
                    <div><span className="pill">{n.type}</span> <span className="mono">{n.source}</span></div>
                    <div>{n.mainClaim}</div>
                    <div className="muted">{n.whyRelevant}</div>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="muted">No insights yet.</div>
            )}
          </div>
        </div>
      )}

      {tab === "synthesis" && (
        <div className="row">
          <div className="panel">
            <h2>SynthesisSummary</h2>
            <div className="muted">Heuristic MVP: themes, risk hotspots, warnings, next actions.</div>
            <div className="btnRow">
              <button className="btn btnPrimary" onClick={() => void synthesize()} disabled={!sessionId}>
                Re-synthesize
              </button>
              <button className="btn" onClick={() => void refresh()} disabled={!sessionId}>
                Refresh
              </button>
            </div>
            <pre className="mono" style={{ marginTop: 10 }}>{JSON.stringify(synthesisSummary, null, 2)}</pre>
          </div>

          <div className="panel">
            <h2>Next-best actions</h2>
            {synthesisSummary?.nextBestActions?.length ? (
              <ul className="list">
                {synthesisSummary.nextBestActions.map((a: string, i: number) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            ) : (
              <div className="muted">Run synthesis to see actions.</div>
            )}

            <h2 style={{ marginTop: 14 }}>Continuity warnings</h2>
            {synthesisSummary?.continuityWarnings?.length ? (
              <ul className="list">
                {synthesisSummary.continuityWarnings.map((a: string, i: number) => (
                  <li key={i} className="danger">{a}</li>
                ))}
              </ul>
            ) : (
              <div className="muted">No warnings.</div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

