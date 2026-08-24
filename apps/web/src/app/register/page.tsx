"use client";

import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";

const VERSIONS = {
  terms: "tos-2026-08-01",
  privacy: "privacy-2026-08-01",
  content_policy: "content-2026-08-01",
  age_policy: "age-2026-08-01",
};

export default function RegisterPage() {
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    const form = new FormData(e.currentTarget);
    try {
      await api("/v1/auth/register", {
        method: "POST",
        body: JSON.stringify({
          email: form.get("email"),
          password: form.get("password"),
          invite_code: form.get("invite_code") || null,
          acceptances: VERSIONS,
        }),
      });
      setDone(true);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (done) {
    return (
      <div className="card" style={{ maxWidth: 520 }}>
        <h1>Check your email</h1>
        <p className="muted">Confirm the address before age assurance. In local development the link is printed in the API log.</p>
      </div>
    );
  }

  return (
    <form className="card" style={{ maxWidth: 520 }} onSubmit={onSubmit}>
      <p className="kicker">Registration</p>
      <h1>Create an adult account</h1>
      <p className="muted">You must be 18 or over. Generation stays locked until age assurance passes.</p>
      <label>Email</label>
      <input name="email" type="email" required autoComplete="email" />
      <label>Password (10+ characters)</label>
      <input name="password" type="password" required minLength={10} autoComplete="new-password" />
      <label>Invite code</label>
      <input name="invite_code" placeholder="Required only when the waitlist is closed" />
      <p className="notice" style={{ marginTop: "1rem" }}>
        By continuing you accept the current{" "}
        <Link href="/policies/terms">Terms</Link>, <Link href="/policies/privacy">Privacy Notice</Link>,{" "}
        <Link href="/policies/content">Content Policy</Link>, and age-assurance policy. Versions: {VERSIONS.terms}.
      </p>
      {error ? <p className="error">{error}</p> : null}
      <div className="row" style={{ marginTop: "1rem" }}>
        <button type="submit">Register</button>
        <Link href="/login">Already have an account</Link>
      </div>
    </form>
  );
}
