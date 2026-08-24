"use client";

import { FormEvent, useState } from "react";
import { api } from "@/lib/api";

export default function ForgotPage() {
  const [done, setDone] = useState(false);
  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    await api("/v1/auth/password/forgot", {
      method: "POST",
      body: JSON.stringify({ email: form.get("email") }),
    });
    setDone(true);
  }
  return (
    <form className="card" style={{ maxWidth: 460 }} onSubmit={onSubmit}>
      <h1>Reset password</h1>
      <label>Email</label>
      <input name="email" type="email" required />
      <button type="submit" style={{ marginTop: "1rem" }}>
        Send reset link
      </button>
      {done ? <p className="ok">If that account exists, a reset email was sent.</p> : null}
    </form>
  );
}
