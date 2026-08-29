"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";

type Capacity = { queue_depth: number; queue_max_depth: number; running: number; worker_slots: number; headroom: number };
type Finance = { payments_enabled: boolean; payment_provider?: string; user_count: number; open_holds: number };

export default function AdminHome() {
  const [capacity, setCapacity] = useState<Capacity | null>(null);
  const [finance, setFinance] = useState<Finance | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Capacity>("/v1/admin/capacity").then(setCapacity).catch((err) => setError((err as Error).message));
    api<Finance>("/v1/admin/finance/summary").then(setFinance).catch(() => undefined);
  }, []);

  return (
    <div>
      <p className="kicker">Operator</p>
      <h1>Operations</h1>
      {error ? (
        <p className="error">
          {error}{" "}
          {error.toLowerCase().includes("multi-factor") ? <Link href="/mfa">Complete authenticator setup</Link> : null}
        </p>
      ) : null}
      <div className="row" style={{ marginBottom: "1rem" }}>
        <Link className="button secondary" href="/admin/moderation">
          Moderation
        </Link>
        <Link className="button secondary" href="/admin/support">
          Support
        </Link>
      </div>
      <div className="grid grid-2">
        <div className="card">
          <h2>GPU / queue</h2>
          {capacity ? (
            <ul className="muted">
              <li>Queue {capacity.queue_depth} / {capacity.queue_max_depth}</li>
              <li>Running {capacity.running} / {capacity.worker_slots} slots</li>
              <li>Headroom {capacity.headroom}</li>
            </ul>
          ) : (
            <p className="muted">Loading capacity…</p>
          )}
        </div>
        <div className="card">
          <h2>Finance</h2>
          <p className="muted">Payments enabled: {String(finance?.payments_enabled ?? false)} · provider {finance?.payment_provider ?? "none"}</p>
          <p className="muted">Ledger users: {finance?.user_count ?? "—"} · open holds {finance?.open_holds ?? "—"}</p>
          <p className="notice">Paid checkout remains disabled until a processor confirms the business is permitted. See docs/PAYMENTS.md. Stripe keys are not approval.</p>
        </div>
      </div>
      <InviteForm />
    </div>
  );
}

function InviteForm() {
  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    await api("/v1/admin/invites", {
      method: "POST",
      body: JSON.stringify({ code: form.get("code"), max_uses: Number(form.get("max_uses") || 1) }),
    });
  }
  return (
    <form className="card" onSubmit={onSubmit} style={{ marginTop: "1rem" }}>
      <h2>Create invite</h2>
      <label>Code</label>
      <input name="code" required />
      <label>Max uses</label>
      <input name="max_uses" type="number" defaultValue={1} />
      <button type="submit">Save invite</button>
    </form>
  );
}
