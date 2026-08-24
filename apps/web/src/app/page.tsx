import Link from "next/link";

export default function HomePage() {
  return (
    <div className="grid grid-2">
      <section>
        <p className="kicker">Adults 18+ only</p>
        <h1>Private illustration, kept on your side of the wall.</h1>
        <p className="muted">
          PrivateCanvas lets verified adults generate original fictional artwork from text prompts.
          There is no public gallery, no social feed, and no sharing by default.
        </p>
        <div className="notice" style={{ margin: "1.2rem 0" }}>
          This service is restricted to adults. Sexual content depicting minors, real people, celebrities,
          non-consent, or other prohibited categories is blocked. A self-declared date of birth is not enough
          to enter the workspace — age assurance is required.
        </div>
        <div className="row">
          <Link className="button" href="/register">
            Create an account
          </Link>
          <Link className="button secondary" href="/policies/content">
            Read the content policy
          </Link>
        </div>
      </section>
      <aside className="card">
        <h2>What this is</h2>
        <p className="muted">Curated text-to-image workflows. Server-controlled models. Private library.</p>
        <ul className="muted">
          <li>Age assurance before generation or credit spend</li>
          <li>Prompt policy checks before any GPU work</li>
          <li>Short-lived downloads, private object storage</li>
          <li>You can delete outputs and the account</li>
        </ul>
        <p className="muted">Payments stay disabled until a processor confirms the business is permitted.</p>
      </aside>
    </div>
  );
}
