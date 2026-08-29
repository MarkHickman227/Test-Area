"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";

type Options = {
  model_profiles: { id: string; name: string; description: string; base_credit_cost: number }[];
  style_presets: { id: string; name: string; description: string; model_profile_id: string }[];
  aspect_ratios: string[];
  resolutions: string[];
  image_counts: number[];
};

type Job = {
  job_id: string;
  status: string;
  estimated_credit_cost: number;
  queue_position: number | null;
  policy_decision: string;
  failure_code?: string | null;
  worker_id?: string | null;
};

type Launch = { generation_backend?: string };

const ASPECT_RES: Record<string, string> = {
  "1:1": "768x768",
  "2:3": "768x1152",
  "3:2": "1152x768",
  "9:16": "768x1152",
  "16:9": "1152x768",
};

export default function GeneratePage() {
  const [options, setOptions] = useState<Options | null>(null);
  const [account, setAccount] = useState<{ status: string; balance: number; age_verification_status: string } | null>(null);
  const [error, setError] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [aspect, setAspect] = useState("2:3");
  const [count, setCount] = useState(1);
  const [backend, setBackend] = useState("mock");

  useEffect(() => {
    api<typeof account>("/v1/account")
      .then(setAccount)
      .catch((err) => setError((err as Error).message));
    api<Options>("/v1/generation/options").then(setOptions).catch(() => undefined);
    api<Launch>("/v1/meta/launch")
      .then((meta) => setBackend(meta.generation_backend || "mock"))
      .catch(() => undefined);
  }, []);

  const estimate = useMemo(() => {
    const base = options?.model_profiles[0]?.base_credit_cost || 4;
    const mult = ASPECT_RES[aspect] === "1024x1024" ? 1.5 : aspect === "1:1" ? 1 : 1.25;
    return Math.max(1, Math.round(base * mult * count));
  }, [options, aspect, count]);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    const form = new FormData(e.currentTarget);
    try {
      const created = await api<Job>("/v1/generations", {
        method: "POST",
        body: JSON.stringify({
          idempotency_key: crypto.randomUUID(),
          model_profile_id: form.get("model_profile_id"),
          style_preset_id: form.get("style_preset_id") || null,
          prompt: form.get("prompt"),
          negative_prompt: form.get("negative_prompt") || null,
          aspect_ratio: aspect,
          resolution: form.get("resolution"),
          image_count: Number(form.get("image_count")),
          seed: form.get("seed") ? Number(form.get("seed")) : null,
        }),
      });
      setJob(created);
      const acc = await api<typeof account>("/v1/account");
      setAccount(acc);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (account && (account.status !== "ACTIVE" || account.age_verification_status !== "PASSED")) {
    return (
      <div className="card">
        <h1>Workspace locked</h1>
        <p className="muted">Complete email verification and age assurance before generating.</p>
        <Link className="button" href="/age-verification">
          Continue age assurance
        </Link>
      </div>
    );
  }

  return (
    <div className="grid grid-2">
      <form className="card" onSubmit={onSubmit}>
        <p className="kicker">{backend === "comfyui" ? "ComfyUI workspace" : "Generation workspace"}</p>
        <h1>Compose a private image</h1>
        {backend === "comfyui" ? (
          <p className="muted">
            Generation runs through a private ComfyUI worker and a pinned workflow. There is no graph editor
            and you cannot upload models or custom nodes.
          </p>
        ) : null}
        <label>Model profile</label>
        <select name="model_profile_id" defaultValue="adult-illustration-v1">
          {(options?.model_profiles || []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <label>Style preset</label>
        <select name="style_preset_id" defaultValue="cinematic-photo-v1">
          {(options?.style_presets || []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <label>Prompt</label>
        <textarea name="prompt" required placeholder="An original fictional adult character, clearly 25 years old..." />
        <label>Negative prompt (optional)</label>
        <textarea name="negative_prompt" style={{ minHeight: 80 }} placeholder="celebrity, public figure, watermark" />
        <div className="row">
          <div style={{ flex: 1 }}>
            <label>Aspect ratio</label>
            <select value={aspect} onChange={(e) => setAspect(e.target.value)} name="aspect_ratio">
              {(options?.aspect_ratios || Object.keys(ASPECT_RES)).map((a) => (
                <option key={a}>{a}</option>
              ))}
            </select>
          </div>
          <div style={{ flex: 1 }}>
            <label>Resolution</label>
            <select name="resolution" defaultValue={ASPECT_RES[aspect]}>
              <option value={ASPECT_RES[aspect]}>{ASPECT_RES[aspect]}</option>
              {aspect === "1:1" ? <option value="1024x1024">1024x1024</option> : null}
            </select>
          </div>
        </div>
        <div className="row">
          <div style={{ flex: 1 }}>
            <label>Images</label>
            <select name="image_count" value={count} onChange={(e) => setCount(Number(e.target.value))}>
              <option value={1}>1</option>
              <option value={2}>2</option>
              <option value={4}>4</option>
            </select>
          </div>
          <div style={{ flex: 1 }}>
            <label>Seed (blank = random)</label>
            <input name="seed" type="number" />
          </div>
        </div>
        <p className="notice" style={{ marginTop: "1rem" }}>
          Prohibited: anyone 17 or under, real people, face swaps, non-consent, illegal content, or attempts to evade filters.
          Workflow internals are not user-editable.
        </p>
        <p>
          Estimated cost: <strong className="stat">{estimate}</strong> credits
          {account ? <span className="muted"> · balance {account.balance}</span> : null}
        </p>
        {error ? <p className="error">{error}</p> : null}
        <button type="submit">Generate</button>
      </form>
      <aside className="card">
        <h2>Queue</h2>
        {job ? (
          <div>
            <p>
              Status <span className="badge">{job.status}</span>
            </p>
            <p className="muted">Policy: {job.policy_decision}</p>
            <p className="muted">Cost reserved: {job.estimated_credit_cost}</p>
            {job.worker_id ? <p className="muted">Worker: {job.worker_id}</p> : null}
            {job.status === "COMPLETED" ? <Link href="/library">Open library</Link> : null}
            {job.status === "QUEUED" ? (
              <button
                className="secondary"
                type="button"
                onClick={async () => {
                  const cancelled = await api<Job>(`/v1/generations/${job.job_id}/cancel`, { method: "POST" });
                  setJob(cancelled);
                }}
              >
                Cancel queued job
              </button>
            ) : null}
          </div>
        ) : (
          <p className="muted">
            Submit a prompt to see live job status. History lives in your private library.
            Backend: {backend === "comfyui" ? "ComfyUI (pinned workflow)" : "mock placeholders"}.
          </p>
        )}
        <p style={{ marginTop: "1.5rem" }}>
          <Link href="/library">Job history / library</Link>
        </p>
      </aside>
    </div>
  );
}
