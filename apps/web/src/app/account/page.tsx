"use client";

import { useEffect, useState } from "react";
import { Account, api } from "@/lib/api";
import { useRouter } from "next/navigation";

type LedgerItem = { id: string; event_type: string; amount: number; reason_code: string; created_at: string };
type Product = { id: string; name: string; credits: number; available: boolean; note: string };

export default function AccountPage() {
  const router = useRouter();
  const [account, setAccount] = useState<Account | null>(null);
  const [ledger, setLedger] = useState<LedgerItem[]>([]);
  const [error, setError] = useState("");

  function refresh() {
    api<Account>("/v1/account").then(setAccount).catch((err) => setError((err as Error).message));
    api<LedgerItem[]>("/v1/billing/ledger").then(setLedger).catch(() => undefined);
  }

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("mfa") === "1") {
      router.replace("/mfa");
      return;
    }
    refresh();
  }, [router]);

  if (error) return <p className="error">{error}</p>;
  if (!account) return <p className="muted">Loading…</p>;

  return (
    <div className="grid grid-2">
      <div className="card">
        <h1>Account</h1>
        <p>{account.email}</p>
        <p className="muted">
          Status {account.status} · age {account.age_verification_status} · role {account.role} · plan {account.plan_id || "standard"}
        </p>
        <p>
          Balance <span className="stat">{account.balance}</span> credits
        </p>
        <CreditsPanel agePassed={account.age_verification_status === "PASSED"} onPurchased={refresh} />
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

function CreditsPanel({
  agePassed,
  onPurchased,
}: {
  agePassed: boolean;
  onPurchased: () => void;
}) {
  const [products, setProducts] = useState<Product[]>([]);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api<Product[]>("/v1/billing/products").then(setProducts).catch(() => undefined);
  }, []);

  const available = products.filter((item) => item.available);
  if (!available.length) {
    return <p className="muted">Paid checkout is disabled until a processor approves this service.</p>;
  }

  return (
    <div>
      <p className="notice">{products[0]?.note}</p>
      <div className="row" style={{ margin: "0.8rem 0" }}>
        {available.map((item) => (
          <button
            key={item.id}
            type="button"
            className="secondary"
            disabled={!agePassed}
            onClick={async () => {
              setMessage("");
              try {
                const session = await api<{
                  payment_id: string;
                  checkout_url: string | null;
                  sandbox: boolean;
                }>("/v1/billing/checkout-session", {
                  method: "POST",
                  body: JSON.stringify({ product_id: item.id }),
                });
                if (session.sandbox) {
                  await api("/v1/billing/sandbox-complete", {
                    method: "POST",
                    body: JSON.stringify({ payment_id: session.payment_id }),
                  });
                  onPurchased();
                  setMessage(`Added ${item.credits} credits.`);
                  return;
                }
                if (session.checkout_url) {
                  window.location.href = session.checkout_url;
                }
              } catch (err) {
                setMessage((err as Error).message);
              }
            }}
          >
            {item.name}
          </button>
        ))}
      </div>
      {message ? <p className="muted">{message}</p> : null}
    </div>
  );
}
