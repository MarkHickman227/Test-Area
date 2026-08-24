"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";

export default function AgePage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [status, setStatus] = useState<string>("");

  async function start() {
    try {
      const data = await api<{ status: string }>("/v1/age-verification/session", { method: "POST" });
      setStatus(data.status);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function sandbox() {
    try {
      await api("/v1/age-verification/sandbox-complete", {
        method: "POST",
        body: JSON.stringify({ outcome: "PASSED" }),
      });
      router.push("/generate");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="card" style={{ maxWidth: 560 }}>
      <p className="kicker">Age assurance</p>
      <h1>Confirm you are an adult</h1>
      <p className="muted">
        A date of birth typed into a form is not enough. PrivateCanvas records only the provider outcome,
        assurance level, and a provider reference — not identity documents.
      </p>
      <div className="notice">Sandbox provider is enabled in this development build. Production must use an approved age-assurance supplier.</div>
      {error ? <p className="error">{error}</p> : null}
      <div className="row" style={{ marginTop: "1rem" }}>
        <button type="button" onClick={start}>
          Start verification
        </button>
        <button type="button" className="secondary" onClick={sandbox}>
          Complete sandbox check
        </button>
      </div>
      {status ? <p className="muted">Current provider status: {status}</p> : null}
    </div>
  );
}
