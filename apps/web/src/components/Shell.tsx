import Link from "next/link";
import { ReactNode } from "react";

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="shell">
      <nav className="nav">
        <Link href="/" className="brand">
          <span className="mark">P</span>
          <strong>PrivateCanvas</strong>
        </Link>
        <div className="nav-links">
          <Link href="/generate">Workspace</Link>
          <Link href="/library">Library</Link>
          <Link href="/account">Account</Link>
          <Link href="/waitlist">Waitlist</Link>
          <Link href="/admin">Admin</Link>
          <Link href="/login">Sign in</Link>
        </div>
      </nav>
      {children}
      <footer className="site">
        Adults only. No public gallery. Outputs stay private to the account that created them.{" "}
        <Link href="/policies/content">Content policy</Link> · <Link href="/policies/privacy">Privacy</Link> ·{" "}
        <Link href="/support">Support</Link>
      </footer>
    </div>
  );
}
