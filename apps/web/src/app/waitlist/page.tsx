"use client";

import { FormEvent, useState } from "react";
import { api } from "@/lib/api";

export default function WaitlistPage() {
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      await api("/v1/waitlist", {
        method: "POST",
        body: JSON.stringify({ email: form.get("email"), note: form.get("note") }),
      });
      setDone(true);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form className="card" style={{ maxWidth: 520 }} onSubmit={onSubmit}>
      <p className="kicker">Invite / waitlist</p>
      <h1>Request access</h1>
      <p className="muted">
        Registration can be switched to invite-only. Paid plans stay off until a processor approves the service.
      </p>
      <label>Email</label>
      <input name="email" type="email" required />
      <label>Note (optional)</label>
      <textarea name="note" style={{ minHeight: 80 }} />
      {error ? <p className="error">{error}</p> : null}
      {done ? <p className="ok">You are on the waitlist.</p> : <button type="submit">Join waitlist</button>}
    </form>
  );
}
