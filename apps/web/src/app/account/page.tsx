"use client";

import { useEffect, useState } from "react";
import { Account, api } from "@/lib/api";
import { useRouter } from "next/navigation";

type LedgerItem = { id: string; event_type: string; amount: number; reason_code: string; created_at: string };

export default function AccountPage() {
  const router = useRouter();
  const [account, setAccount] = useState<Account | null>(null);
  const [ledger, setLedger] = useState<LedgerItem[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Account>("/v1/account").then(setAccount).catch((err) => setError((err as Error).message));
    api<LedgerItem[]>("/v1/billing/ledger").then(setLedger).catch(() => undefined);
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!account) return <p className="muted">Loading…</p>;

  return (
    <div className="grid grid-2">
      <div className="card">
        <h1>Account</h1>
        <p>{account.email}</p>
        <p className="muted">
          Status {account.status} · age {account.age_verification_status} · role {account.role}
        </p>
        <p>
          Balance <span className="stat">{account.balance}</span> credits
        </p>
        <p className="muted">Paid checkout is disabled until a processor approves this service.</p>
        <div className="row">
          <button
            type="button"
            className="secondary"
            onClick={async () => {
              await api("/v1/account/export", { method: "POST" });
              alert("Export prepared.");
            }}
          >
            Export my data
          </button>
          <button
            type="button"
            className="secondary"
            onClick={async () => {
              if (!confirm("Permanently delete this account and outputs?")) return;
              await api("/v1/account/delete", { method: "POST" });
              router.push("/");
            }}
          >
            Delete account
          </button>
          <button
            type="button"
            className="secondary"
            onClick={async () => {
              await api("/v1/auth/logout", { method: "POST" });
              router.push("/");
            }}
          >
            Sign out
          </button>
        </div>
      </div>
      <div className="card">
        <h2>Credit ledger</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Event</th>
              <th>Amount</th>
            </tr>
          </thead>
          <tbody>
            {ledger.map((row) => (
              <tr key={row.id}>
                <td>{row.event_type}</td>
                <td>{row.amount}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
