"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useParams, useRouter } from "next/navigation";

type Detail = {
  id: string;
  job_id: string;
  prompt: string;
  negative_prompt: string | null;
  seed: number | null;
  parameters: Record<string, unknown>;
  favourite: boolean;
  width: number;
  height: number;
};

export default function OutputPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [item, setItem] = useState<Detail | null>(null);
  const [src, setSrc] = useState<string>("");
  const [error, setError] = useState("");

  useEffect(() => {
    api<Detail>(`/v1/library/outputs/${id}`)
      .then(async (detail) => {
        setItem(detail);
        const dl = await api<{ url: string }>(`/v1/library/outputs/${id}/download-url`, { method: "POST" });
        setSrc(dl.url.startsWith("http") ? dl.url.replace("http://localhost:3000", "") : dl.url);
      })
      .catch((err) => setError((err as Error).message));
  }, [id]);

  if (error) return <p className="error">{error}</p>;
  if (!item) return <p className="muted">Loading…</p>;

  return (
    <div className="grid grid-2">
      <div className="card">
        {src ? <img alt="" src={src} style={{ width: "100%", borderRadius: 8 }} /> : null}
      </div>
      <div className="card">
        <h1>Output</h1>
        <p className="muted">{item.width}×{item.height} · seed {item.seed}</p>
        <h2>Prompt</h2>
        <p>{item.prompt}</p>
        <div className="row">
          <button
            type="button"
            onClick={async () => {
              const dl = await api<{ url: string }>(`/v1/library/outputs/${id}/download-url`, { method: "POST" });
              window.location.href = dl.url.startsWith("http") ? dl.url.replace("http://localhost:3000", "") : dl.url;
            }}
          >
            Download
          </button>
          <button
            className="secondary"
            type="button"
            onClick={async () => {
              await api(`/v1/library/outputs/${id}`, {
                method: "PATCH",
                body: JSON.stringify({ favourite: !item.favourite }),
              });
              setItem({ ...item, favourite: !item.favourite });
            }}
          >
            {item.favourite ? "Unfavourite" : "Favourite"}
          </button>
          <button
            className="secondary"
            type="button"
            onClick={async () => {
              await api(`/v1/generations/${item.job_id}/rerun`, {
                method: "POST",
                body: JSON.stringify({ idempotency_key: crypto.randomUUID() }),
              });
              router.push("/library");
            }}
          >
            Re-run
          </button>
          <button
            className="secondary"
            type="button"
            onClick={async () => {
              await api("/v1/reports", {
                method: "POST",
                body: JSON.stringify({
                  category: "policy",
                  description: "User-reported output",
                  job_id: item.job_id,
                  output_id: item.id,
                }),
              });
              alert("Report submitted to the private moderation queue.");
            }}
          >
            Report
          </button>
          <button
            className="secondary"
            type="button"
            onClick={async () => {
              await api(`/v1/library/outputs/${id}`, { method: "DELETE" });
              router.push("/library");
            }}
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
