"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";

type SupportUser = {
  id: string;
  email: string;
  status: string;
  plan_id: string;
  age_verification_status: string;
  balance: number;
  outputs_visible: boolean;
};

type Ticket = { id: string; email: string; subject: string; status: string; category: string };

export default function SupportPage() {
  const [q, setQ] = useState("");
  const [users, setUsers] = useState<SupportUser[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Ticket[]>("/v1/admin/support/tickets").then(setTickets).catch((err) => setError((err as Error).message));
  }, []);

  async function search(e: FormEvent) {
    e.preventDefault();
    setUsers(await api<SupportUser[]>(`/v1/admin/support/users?q=${encodeURIComponent(q)}`));
  }

  return (
    <div className="grid grid-2">
      <div className="card">
        <p className="kicker">Support</p>
        <h1>Accounts without image access</h1>
        <form onSubmit={search} className="row">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search email" minLength={3} />
          <button type="submit">Search</button>
        </form>
        {error ? <p className="error">{error}</p> : null}
        <table className="table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Status</th>
              <th>Plan</th>
              <th>Images</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.email}</td>
                <td>{u.status}</td>
                <td>{u.plan_id}</td>
                <td>{u.outputs_visible ? "yes" : "hidden"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card">
        <h2>Tickets</h2>
        <ul className="muted">
          {tickets.map((t) => (
            <li key={t.id}>
              {t.status} · {t.subject} ({t.email})
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
