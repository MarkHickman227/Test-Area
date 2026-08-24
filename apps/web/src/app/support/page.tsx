"use client";

import { FormEvent, useState } from "react";
import { api } from "@/lib/api";

export default function SupportPage() {
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      await api("/v1/support/tickets", {
        method: "POST",
        body: JSON.stringify({
          email: form.get("email"),
          subject: form.get("subject"),
          body: form.get("body"),
          category: "account",
        }),
      });
      setDone(true);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form className="card" style={{ maxWidth: 560 }} onSubmit={onSubmit}>
      <h1>Support</h1>
      <p className="muted">
        Support staff cannot view generated images by default. For suspected illegal content, use Report on an output.
      </p>
      <label>Email</label>
      <input name="email" type="email" required />
      <label>Subject</label>
      <input name="subject" required />
      <label>Details</label>
      <textarea name="body" required />
      {error ? <p className="error">{error}</p> : null}
      {done ? <p className="ok">Ticket received.</p> : <button type="submit">Send</button>}
    </form>
  );
}
