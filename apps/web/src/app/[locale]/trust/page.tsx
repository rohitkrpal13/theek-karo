/**
 * Phase 23 — /trust public transparency page.
 *
 * Explains how data is collected, how evidence works, verification,
 * source quality, AI usage, privacy, corrections, disputes, and limitations.
 * Uses simple language. No misleading trust claims.
 */

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Data Trust — Theek Karo",
  description:
    "Understand how Theek Karo collects, verifies, and presents civic data. Transparent methodology, sources, and limitations.",
};

const TRUST_SECTIONS = [
  {
    id: "how-data-is-collected",
    title: "How is data collected?",
    body: "Theek Karo collects data from two primary channels: citizen reports submitted through the platform, and official government datasets imported from public sources. Every piece of data is attributed to its source — we never fabricate information.",
  },
  {
    id: "what-is-a-report",
    title: "What is a report?",
    body: "A report is a civic observation submitted by a citizen — for example 'street light not working on MG Road'. Reports reflect what people choose to report, where they are active, and how easy the platform is to use. A high-reporting area may simply have more active users, not necessarily more problems.",
  },
  {
    id: "evidence",
    title: "How does evidence work?",
    body: "Evidence includes photos, videos, documents, and official records attached to reports and cases. Every piece of evidence is registered with its source, upload timestamp, and a cryptographic integrity hash. The hash helps detect if files have been changed — but it does not prove the underlying content is truthful.",
  },
  {
    id: "verification",
    title: "How is data verified?",
    body: "Verification is not binary. Data goes through multiple verification stages: human review, official source confirmation, cross-source consistency checks, location validation, and document verification. AI may assist reviewers but never makes final verification decisions alone. A report is verified when independent ground evidence confirms it.",
  },
  {
    id: "source-quality",
    title: "How do we assess source quality?",
    body: "Every data source is tracked with multiple quality dimensions: authority (is it an official government source?), freshness (how recently was it updated?), completeness (are required fields present?), consistency (do values agree across sources?), and coverage (what geography and time period does it cover?). We do not use a single trust score — different dimensions may tell different stories.",
  },
  {
    id: "official-data",
    title: "What is official data?",
    body: "Official data is information imported from government sources such as state education departments, health departments, or census publications. Every official dataset shows its source, retrieval date, and license. Theek Karo never fabricates official numbers. When official data and citizen observations differ, both values are shown — official data is never silently overwritten.",
  },
  {
    id: "how-metrics-are-calculated",
    title: "How are metrics calculated?",
    body: "Every metric on this site links to a formal definition with its numerator, denominator, and time period. Definitions come from the platform's public metric registry, not from ad-hoc formulas. If a formula changes, historical reports retain the methodology that was used at the time.",
  },
  {
    id: "ai-usage",
    title: "How does AI work here?",
    body: "AI on this platform explains data it receives from structured tools. It does not invent statistics: every number in an AI answer comes from a database query performed by a tool, and the answer cites the dataset, metric, period, and geography it used. AI-generated content is clearly labeled. AI must not become the source of truth.",
  },
  {
    id: "discrepancies",
    title: "What happens when sources disagree?",
    body: "When official data and citizen observations differ, the platform shows a data conflict. Both values are displayed with their sources and timestamps. Authorized reviewers may resolve conflicts by selecting the authoritative source, merging records, or marking the conflict as unresolved. We never silently choose one value over another.",
  },
  {
    id: "corrections",
    title: "How can I suggest a correction?",
    body: "Every appropriate public record provides a 'Suggest a correction' option. You can report incorrect institution information, outdated data, wrong locations, or duplicate entities. Corrections go through a review workflow — they do not automatically update the data. Accepted corrections are recorded in an audit trail.",
  },
  {
    id: "disputes",
    title: "What is a dispute?",
    body: "Authorized users may file a formal dispute against a report, evidence, dataset, institution information, or public metric. A dispute does not automatically remove data — it creates a review process. If a public record is disputed, it shows an 'Information currently under review' banner. We do not present disputed information as fully verified.",
  },
  {
    id: "privacy",
    title: "How is privacy protected?",
    body: "Public datasets never include phone numbers, emails, private addresses, exact personal locations, or private media. Locations are generalized to about one kilometre. Small cells are protected — if an aggregation could identify individuals, the data is suppressed or aggregated. User identity is never linked to exported rows.",
  },
  {
    id: "reporting-bias",
    title: "Reporting volume is not problem severity",
    body: "A high-reporting area may simply have more active users, better connectivity, or higher awareness. Areas with few reports are shown as 'limited reporting data', never as problem-free. The platform never implies that lack of data means lack of problems.",
  },
  {
    id: "limitations",
    title: "What are the limitations?",
    body: "All data on this platform has limitations. Reports reflect what people choose to report. Official data may be outdated. Verification depends on available evidence. AI explanations are advisory. Metrics depend on the quality and completeness of underlying data. Every dataset shows its freshness, coverage, and known limitations.",
  },
  {
    id: "data-lifecycle",
    title: "What happens to my data?",
    body: "Your civic contributions (reports, evidence, corrections) are preserved to maintain a transparent record. Personal information is handled according to our privacy policy. You can request correction of your personal information. Data retention follows documented policies for each data category.",
  },
];

export default function TrustPage() {
  return (
    <main className="mx-auto max-w-4xl px-4 py-12">
      <h1 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
        Data Trust
      </h1>
      <p className="mt-3 text-lg text-gray-600 dark:text-gray-300">
        Understanding how Theek Karo collects, verifies, and presents civic
        data. Transparent methodology, sources, and limitations.
      </p>

      <div className="mt-8 space-y-8">
        {TRUST_SECTIONS.map((section) => (
          <section
            key={section.id}
            id={section.id}
            className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800"
          >
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              {section.title}
            </h2>
            <p className="mt-2 leading-relaxed text-gray-700 dark:text-gray-300">
              {section.body}
            </p>
          </section>
        ))}
      </div>

      <div className="mt-12 rounded-lg border border-amber-200 bg-amber-50 p-6 dark:border-amber-800 dark:bg-amber-950">
        <h2 className="text-lg font-semibold text-amber-800 dark:text-amber-200">
          Important Disclaimer
        </h2>
        <p className="mt-2 text-amber-700 dark:text-amber-300">
          Theek Karo never implies that &quot;data exists, therefore data is
          true.&quot; Every dataset, report, and metric shown on this platform
          has been attributed to its source, timestamped, and — where
          applicable — verified through documented methods. Data quality
          varies by source, and users should consider the limitations
          described above when interpreting any information.
        </p>
      </div>
    </main>
  );
}
