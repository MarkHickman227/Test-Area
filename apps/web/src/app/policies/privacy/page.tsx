export default function PrivacyPage() {
  return (
    <article className="card">
      <p className="kicker">Policy draft</p>
      <h1>Privacy notice</h1>
      <p>
        We store the minimum needed to run the service: account email, session data, age-assurance outcome and
        provider reference, encrypted prompts, private outputs, credit ledger events, and security logs.
      </p>
      <p>
        Prompts and outputs are not used for model training, advertising, or public display. Object storage is private.
        You can export or delete your account. A Data Protection Impact Assessment is required before live launch.
      </p>
    </article>
  );
}
