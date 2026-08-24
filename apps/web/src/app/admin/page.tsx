"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Queue = {
  counts: Record<string, number>;
  held_jobs: { id: string; user_id: string; status: string; policy_decision: string }[];
  worker_health: string;
};

export default function AdminPage() {
  const [queue, setQueue] = useState<Queue | null>(null);
  const [error, setError] = useState("");
  const [rationale, setRationale] = useState("Reviewed in moderator console.");

  useEffect(() => {
    api<Queue>("/v1/admin/queue").then(setQueue).catch((err) => setError((err as Error).message));
  }, []);

  async function decide(jobId: string, decision: string) {
    await api(`/v1/admin/jobs/${jobId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, reason_code: decision, rationale }),
    });
    setQueue(await api<Queue>("/v1/admin/queue"));
  }

  if (error) return <p className="error">{error}</p>;
  if (!queue) return <p className="muted">Loading operator console…</p>;

  return (
    <div>
      <p className="kicker">Operator</p>
      <h1>Queues, workers, moderation</h1>
      <p className="muted">Worker health: {queue.worker_health}. Access is audited.</p>
      <div className="row" style={{ margin: "1rem 0" }}>
        {Object.entries(queue.counts).map(([status, n]) => (
          <div key={status} className="card" style={{ minWidth: 120, padding: "0.8rem" }}>
            <div className="muted">{status}</div>
            <div className="stat">{n}</div>
          </div>
        ))}
      </div>
      <div className="card">
        <h2>Held jobs</h2>
        <label>Decision rationale</label>
        <input value={rationale} onChange={(e) => setRationale(e.target.value)} />
        <table className="table">
          <thead>
            <tr>
              <th>Job</th>
              <th>Policy</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {queue.held_jobs.map((job) => (
              <tr key={job.id}>
                <td>{job.id.slice(0, 8)}</td>
                <td>{job.policy_decision}</td>
                <td className="row">
                  <button type="button" onClick={() => decide(job.id, "APPROVE")}>
                    Approve
                  </button>
                  <button type="button" className="secondary" onClick={() => decide(job.id, "BLOCK")}>
                    Block
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {queue.held_jobs.length === 0 ? <p className="muted">No held jobs.</p> : null}
      </div>
    </div>
  );
}
