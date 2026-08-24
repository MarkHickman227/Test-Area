"use client";

import { FormEvent, Suspense, useState } from "react";
import { api } from "@/lib/api";
import { useSearchParams, useRouter } from "next/navigation";

function Inner() {
  const params = useSearchParams();
  const router = useRouter();
  const [token, setToken] = useState(params.get("token") || "");
  const [error, setError] = useState("");

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      await api("/v1/auth/password/reset", {
        method: "POST",
        body: JSON.stringify({ token, password: form.get("password") }),
      });
      router.push("/login");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form className="card" style={{ maxWidth: 460 }} onSubmit={onSubmit}>
      <h1>Choose a new password</h1>
      <label>Token</label>
      <input value={token} onChange={(e) => setToken(e.target.value)} required />
      <label>New password</label>
      <input name="password" type="password" minLength={10} required />
      {error ? <p className="error">{error}</p> : null}
      <button type="submit">Update password</button>
    </form>
  );
}

export default function ResetPage() {
  return (
    <Suspense>
      <Inner />
    </Suspense>
  );
}
