"use client";

import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import { useSearchParams, useRouter } from "next/navigation";
import { Suspense } from "react";

function VerifyInner() {
  const params = useSearchParams();
  const router = useRouter();
  const [token, setToken] = useState(params.get("token") || "");
  const [error, setError] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      await api("/v1/auth/verify-email", { method: "POST", body: JSON.stringify({ token }) });
      router.push("/age-verification");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form className="card" style={{ maxWidth: 480 }} onSubmit={onSubmit}>
      <h1>Verify email</h1>
      <label>Verification token</label>
      <input value={token} onChange={(e) => setToken(e.target.value)} required />
      {error ? <p className="error">{error}</p> : null}
      <button type="submit" style={{ marginTop: "1rem" }}>
        Confirm email
      </button>
    </form>
  );
}

export default function VerifyPage() {
  return (
    <Suspense>
      <VerifyInner />
    </Suspense>
  );
}
