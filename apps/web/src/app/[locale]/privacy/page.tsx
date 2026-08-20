export default async function PrivacyPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8 py-6">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight">Privacy Notice</h1>
        <p className="mt-2 text-sm text-(--color-ink-muted)">
          Effective: 20 August 2026 · Aligned with India DPDP Act 2023
        </p>
      </div>

      <section className="space-y-3 text-sm leading-relaxed">
        <p>
          Theek Karo is a civic intelligence platform operated for public good. We
          collect the minimum personal data needed for civic reporting, community
          verification, and government interoperability. This notice explains what
          we collect, why, how long we keep it, and your rights under the Digital
          Personal Data Protection (DPDP) Act 2023.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold">1. Data We Collect</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border border-(--color-line) rounded-lg overflow-hidden">
            <thead className="bg-(--color-surface-sunken) text-left">
              <tr>
                <th className="px-4 py-2 font-semibold">Category</th>
                <th className="px-4 py-2 font-semibold">Data</th>
                <th className="px-4 py-2 font-semibold">Purpose</th>
                <th className="px-4 py-2 font-semibold">Legal Basis</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-(--color-line)">
              <tr>
                <td className="px-4 py-2 font-medium">Account</td>
                <td className="px-4 py-2">Phone/email, display name, password hash</td>
                <td className="px-4 py-2">Authentication, notifications</td>
                <td className="px-4 py-2">Consent (registration)</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-medium">Reports</td>
                <td className="px-4 py-2">Title, description, location, photos, severity</td>
                <td className="px-4 py-2">Civic issue tracking, public record</td>
                <td className="px-4 py-2">Public interest / consent</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-medium">Community</td>
                <td className="px-4 py-2">Comments, votes, follows, reactions</td>
                <td className="px-4 py-2">Community verification, engagement</td>
                <td className="px-4 py-2">Consent</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-medium">Government Data</td>
                <td className="px-4 py-2">Official datasets (UDISE+, NHP, etc.)</td>
                <td className="px-4 py-2">Baseline comparison, transparency</td>
                <td className="px-4 py-2">Public interest</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-medium">Technical</td>
                <td className="px-4 py-2">Request logs, AI runs, media metadata</td>
                <td className="px-4 py-2">Security, reliability, debugging</td>
                <td className="px-4 py-2">Legitimate interest</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold">2. How We Use AI</h2>
        <ul className="list-disc space-y-1.5 pl-6 text-sm">
          <li>AI classifies and routes reports (never closes or rejects them).</li>
          <li>AI detects duplicates — only humans apply the merge.</li>
          <li>AI summarizes government data for comparison — always labelled T4.</li>
          <li>AI never accesses private account data or raw credentials.</li>
          <li>Every AI output carries a provenance label (T4 = AI Generated).</li>
          <li>AI conversations are retained for 90 days, then purged.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold">3. Your Rights (DPDP Act)</h2>
        <ul className="list-disc space-y-1.5 pl-6 text-sm">
          <li><strong>Access:</strong> View your data via your profile page.</li>
          <li><strong>Correction:</strong> Edit your profile and preferences at any time.</li>
          <li><strong>Erasure:</strong> Delete your account — PII anonymised immediately; public civic contributions retained (anonymised) as permitted by law.</li>
          <li><strong>Withdrawal:</strong> Withdraw consent for AI processing via settings.</li>
          <li><strong>Grievance:</strong> File a complaint with our Data Protection Officer.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold">4. Data Retention</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border border-(--color-line) rounded-lg overflow-hidden">
            <thead className="bg-(--color-surface-sunken) text-left">
              <tr>
                <th className="px-4 py-2 font-semibold">Data Type</th>
                <th className="px-4 py-2 font-semibold">Retention</th>
                <th className="px-4 py-2 font-semibold">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-(--color-line)">
              <tr>
                <td className="px-4 py-2">Account (active)</td>
                <td className="px-4 py-2">Duration of account</td>
                <td className="px-4 py-2">Deleted on account removal</td>
              </tr>
              <tr>
                <td className="px-4 py-2">Account (anonymised)</td>
                <td className="px-4 py-2">Permanent (tombstone)</td>
                <td className="px-4 py-2">Preserves FK integrity</td>
              </tr>
              <tr>
                <td className="px-4 py-2">Reports &amp; civic data</td>
                <td className="px-4 py-2">Indefinite (public interest)</td>
                <td className="px-4 py-2">Reporter anonymised on erasure</td>
              </tr>
              <tr>
                <td className="px-4 py-2">Media files</td>
                <td className="px-4 py-2">Campaign policy</td>
                <td className="px-4 py-2">Deleted with report</td>
              </tr>
              <tr>
                <td className="px-4 py-2">AI conversations</td>
                <td className="px-4 py-2">90 days</td>
                <td className="px-4 py-2">Hard delete</td>
              </tr>
              <tr>
                <td className="px-4 py-2">AI run logs</td>
                <td className="px-4 py-2">90 days</td>
                <td className="px-4 py-2">Hard delete</td>
              </tr>
              <tr>
                <td className="px-4 py-2">Session tokens</td>
                <td className="px-4 py-2">90 days</td>
                <td className="px-4 py-2">Hard delete</td>
              </tr>
              <tr>
                <td className="px-4 py-2">Refresh tokens</td>
                <td className="px-4 py-2">90 days</td>
                <td className="px-4 py-2">Hard delete</td>
              </tr>
              <tr>
                <td className="px-4 py-2">Security events</td>
                <td className="px-4 py-2">365 days</td>
                <td className="px-4 py-2">Hard delete</td>
              </tr>
              <tr>
                <td className="px-4 py-2">Audit logs</td>
                <td className="px-4 py-2">Indefinite (write-once)</td>
                <td className="px-4 py-2">Never purged (DPDP §8)</td>
              </tr>
              <tr>
                <td className="px-4 py-2">Consent records</td>
                <td className="px-4 py-2">Indefinite (regulatory)</td>
                <td className="px-4 py-2">Never purged (DPDP §6)</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold">5. Data Security</h2>
        <ul className="list-disc space-y-1.5 pl-6 text-sm">
          <li>Passwords hashed with Argon2id; never stored in plaintext.</li>
          <li>JWT tokens with 15-minute expiry and rotating refresh.</li>
          <li>MFA (TOTP) enforced for officials and administrators.</li>
          <li>All data encrypted in transit (TLS) and at rest (RDS encryption).</li>
          <li>Media uploads scanned for malware before serving.</li>
          <li>Rate limiting and abuse detection on all endpoints.</li>
          <li>Security headers (CSP, HSTS, nosniff) on every response.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold">6. Data Sharing</h2>
        <ul className="list-disc space-y-1.5 pl-6 text-sm">
          <li>Government departments receive case data within their jurisdiction only.</li>
          <li>AI providers receive anonymised prompts — no training on your data.</li>
          <li>No data sold to third parties. Ever.</li>
          <li>Open data exports are aggregate-only — no individual PII exposed.</li>
          <li>Webhooks are HMAC-signed and delivery-tracked.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold">7. Children's Privacy</h2>
        <p className="text-sm">
          Theek Karo is not directed at children under 18. We do not knowingly
          collect personal data from minors. If you believe a minor has submitted
          data, contact us immediately for removal.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold">8. Changes to This Notice</h2>
        <p className="text-sm">
          We will notify registered users of material changes via email or in-app
          notification. Continued use after notification constitutes acceptance.
        </p>
      </section>

      <section className="space-y-3 rounded-lg border border-(--color-line) bg-(--color-surface-sunken) p-4">
        <h2 className="text-lg font-bold">Contact &amp; Grievances</h2>
        <p className="text-sm">
          For privacy questions, data-erasure requests, or grievances:
        </p>
        <ul className="list-disc space-y-1 pl-6 text-sm">
          <li>Email: <a href="mailto:grievance@theekkar.in" className="text-(--color-primary-strong) hover:underline">grievance@theekkar.in</a></li>
          <li>Data Protection Officer: <a href="mailto:dpo@theekkar.in" className="text-(--color-primary-strong) hover:underline">dpo@theekkar.in</a></li>
          <li>Grievance portal: <a href="https://theekkar.in/grievance" className="text-(--color-primary-strong) hover:underline">theekkar.in/grievance</a></li>
        </ul>
        <p className="text-xs text-(--color-ink-muted)">
          We aim to respond within 72 hours as required by the DPDP Act 2023.
        </p>
      </section>
    </div>
  );
}
