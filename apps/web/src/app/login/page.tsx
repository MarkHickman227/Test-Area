"use client";

import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      const data = await api<{ user: { status: string; role: string }; mfa_required: boolean }>("/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
      });
      if (data.mfa_required) {
        router.push("/account?mfa=1");
        return;
      }
      if (data.user.status === "PENDING_AGE_VERIFICATION") router.push("/age-verification");
      else if (["SUPPORT", "MODERATOR", "FINANCE", "SYSTEM_ADMIN", "SUPER_ADMIN"].includes(data.user.role)) {
        router.push("/admin");
      } else router.push("/generate");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form className="card" style={{ maxWidth: 460 }} onSubmit={onSubmit}>
      <p className="kicker">Sign in</p>
      <h1>Welcome back</h1>
      <label>Email</label>
      <input name="email" type="email" required autoComplete="email" />
      <label>Password</label>
      <input name="password" type="password" required autoComplete="current-password" />
      {error ? <p className="error">{error}</p> : null}
      <div className="row" style={{ marginTop: "1rem" }}>
        <button type="submit">Sign in</button>
        <Link href="/forgot-password">Forgot password</Link>
      </div>
    </form>
  );
}
