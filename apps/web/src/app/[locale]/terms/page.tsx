export default async function TermsPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold">Terms of Use</h1>
      <section className="space-y-3 text-sm leading-6">
        <p>
          <strong>Draft for counsel review (Phase 11).</strong> Reports you submit
          become public civic records; verify before you post and never share
          others&rsquo; personal information.
        </p>
        <ul className="list-disc space-y-1 pl-6">
          <li>Content must be factual and non-defamatory; do not post members-only or private data.</li>
          <li>One vote per verified report; abusive or duplicate flooding is removed.</li>
          <li>Official data shown is attributed to its source; AI analysis is clearly labelled and never asserts official status.</li>
          <li>We may close accounts that repeatedly breach these terms.</li>
        </ul>
      </section>
    </div>
  );
}
