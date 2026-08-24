"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";

type Output = {
  id: string;
  job_id: string;
  width: number;
  height: number;
  favourite: boolean;
  created_at: string;
};

export default function LibraryPage() {
  const [items, setItems] = useState<Output[]>([]);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");

  async function load(query = "") {
    const path = query ? `/v1/library/outputs?q=${encodeURIComponent(query)}` : "/v1/library/outputs";
    const data = await api<Output[]>(path);
    setItems(data);
  }

  useEffect(() => {
    load().catch((err) => setError((err as Error).message));
  }, []);

  return (
    <div>
      <p className="kicker">Private library</p>
      <h1>Only you can see these</h1>
      <div className="row" style={{ marginBottom: "1rem" }}>
        <input placeholder="Search your prompts" value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 320 }} />
        <button type="button" className="secondary" onClick={() => load(q)}>
          Search
        </button>
        <button
          type="button"
          className="secondary"
          onClick={async () => {
            await api("/v1/library/bulk-delete", { method: "POST", body: JSON.stringify({ delete_all: true }) });
            await load();
          }}
        >
          Delete all
        </button>
      </div>
      {error ? <p className="error">{error}</p> : null}
      <div className="gallery">
        {items.map((item) => (
            <Link key={item.id} href={`/library/${item.id}`} className="thumb">
            <img alt="" src={`/v1/library/outputs/${item.id}/thumbnail`} />
            <div style={{ padding: "0.5rem", color: "var(--muted)", fontSize: "0.8rem" }}>
              {item.width}×{item.height}
            </div>
          </Link>
        ))}
      </div>
      {items.length === 0 ? <p className="muted">No outputs yet.</p> : null}
    </div>
  );
}
