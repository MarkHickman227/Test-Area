"use client";

import { FormEvent, useState } from "react";
import { Account, api } from "@/lib/api";
import { useRouter } from "next/navigation";
import Link from "next/link";

const ADMIN_ROLES = new Set([
  "SUPPORT",
  "MODERATOR",
  "FINANCE",
  "SYSTEM_ADMIN",
  "SUPER_ADMIN",
]);

export default function MfaPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [secret, setSecret] = useState("");
  const [otpauth, setOtpauth] = useState("");
  const [code, setCode] = useState("");

  async function start() {
    setError("");
    try {
      const data = await api<{ otpauth_url: string; secret: string }>("/v1/auth/mfa/setup", {
        method: "POST",
      });
      setSecret(data.secret);
      setOtpauth(data.otpauth_url);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function verify(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    try {
      await api("/v1/auth/mfa/verify", {
        method: "POST",
        body: JSON.stringify({ code }),
      });
      const account = await api<Account>("/v1/account");
      router.push(ADMIN_ROLES.has(account.role) ? "/admin" : "/generate");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="card" style={{ maxWidth: 560 }}>
      <p className="kicker">Authenticator</p>
      <h1>Complete multi-factor authentication</h1>
      <p className="muted">
        Privileged consoles require a time-based code. Add this secret to an authenticator app, then enter the
        current six-digit code. The secret is shown once and is not stored in the browser.
      </p>
      {!secret ? (
        <div className="row" style={{ marginTop: "1rem" }}>
          <button type="button" onClick={start}>
            Generate authenticator secret
          </button>
          <Link href="/account">Back to account</Link>
        </div>
      ) : (
        <form onSubmit={verify} style={{ marginTop: "1rem" }}>
          <p className="notice">
            Authenticator secret: <strong>{secret}</strong>
          </p>
          {otpauth ? <p className="muted">otpauth URL is ready for a local authenticator app.</p> : null}
          <label>Authentication code</label>
          <input
            name="code"
            inputMode="numeric"
            autoComplete="one-time-code"
            minLength={6}
            maxLength={8}
            value={code}
            onChange={(e) => setCode(e.target.value.trim())}
            required
          />
          <div className="row" style={{ marginTop: "1rem" }}>
            <button type="submit">Verify and continue</button>
          </div>
        </form>
      )}
      {error ? <p className="error">{error}</p> : null}
    </div>
  );
}
