"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";

type Session = {
  status: string;
  provider?: string;
  sandbox?: boolean;
  handoff_url?: string;
};

type Launch = { sandbox_age?: boolean; age_provider?: string };

export default function AgePage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [session, setSession] = useState<Session | null>(null);
  const [sandboxAge, setSandboxAge] = useState(false);

  useEffect(() => {
    api<Launch>("/v1/meta/launch")
      .then((meta) => setSandboxAge(Boolean(meta.sandbox_age)))
      .catch(() => undefined);
    api<Session>("/v1/age-verification/status")
      .then((row) => {
        setSession({ status: row.status });
        if (row.status === "PASSED") router.push("/generate");
      })
      .catch(() => undefined);
  }, [router]);

  async function start() {
    try {
      const data = await api<Session>("/v1/age-verification/session", { method: "POST" });
      setSession(data);
      if (data.status === "PASSED") {
        router.push("/generate");
        return;
      }
      if (data.handoff_url && !data.sandbox) {
        window.location.href = data.handoff_url;
      }
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
        assurance level, and an encrypted provider reference — not identity documents or a date of birth.
      </p>
      {sandboxAge ? (
        <div className="notice">
          Sandbox provider is enabled in this development build. Production must use an approved age-assurance
          supplier over HTTPS webhooks.
        </div>
      ) : (
        <div className="notice">
          You will be sent to the age-assurance provider. We never accept a typed date of birth as proof of age.
        </div>
      )}
      {error ? <p className="error">{error}</p> : null}
      <div className="row" style={{ marginTop: "1rem" }}>
        <button type="button" onClick={start}>
          Start verification
        </button>
        {sandboxAge ? (
          <button type="button" className="secondary" onClick={sandbox}>
            Complete sandbox check
          </button>
        ) : null}
      </div>
      {session?.status ? <p className="muted">Current status: {session.status}</p> : null}
    </div>
  );
}
