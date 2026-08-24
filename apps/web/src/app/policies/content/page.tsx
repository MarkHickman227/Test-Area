export default function ContentPolicyPage() {
  return (
    <article className="card">
      <p className="kicker">Policy draft</p>
      <h1>Acceptable use and content policy</h1>
      <p>PrivateCanvas is an adult-only service for original fictional illustration. The following are prohibited:</p>
      <ul>
        <li>Sexual content depicting or plausibly depicting minors, including ambiguous age cues</li>
        <li>Real people, celebrities, public figures, or identity transfer / face swap</li>
        <li>Coercion, non-consent, sexual violence, incest, bestiality, trafficking, or other illegal content</li>
        <li>Attempts to evade safety systems</li>
        <li>Uploading reference photos or submitting custom ComfyUI graphs</li>
      </ul>
      <p className="muted">
        Automated filters are imperfect. Held requests go to a human moderator. Lawful permitted work can be appealed.
        This draft is not legal advice and is not a launch sign-off.
      </p>
    </article>
  );
}
