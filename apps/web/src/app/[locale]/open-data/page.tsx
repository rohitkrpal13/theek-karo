/**
 * Phase 23 — /open-data public portal.
 *
 * Allows public users to discover appropriate non-sensitive datasets.
 * Shows dataset metadata, license, coverage, schema, version, and links
 * to download/API access.
 */

"use client";

import { useEffect, useState } from "react";

import { publicDataApi, type PublicDataset } from "@/lib/api/public-data";

const CATEGORIES = [
  { value: "", label: "All Categories" },
  { value: "civic_reports", label: "Civic Reports" },
  { value: "verified_reports", label: "Verified Reports" },
  { value: "cases", label: "Cases" },
  { value: "resolutions", label: "Resolutions" },
  { value: "institutions", label: "Institutions" },
  { value: "official_data", label: "Official Data" },
  { value: "geography", label: "Geography" },
];

const FRESHNESS_LABELS: Record<string, string> = {
  fresh: "🟢 Fresh",
  recently_updated: "🟡 Recently Updated",
  may_be_outdated: "🟠 May Be Outdated",
  stale: "🔴 Stale",
  no_data: "⚪ No Data",
};

export default function OpenDataPage() {
  const [datasets, setDatasets] = useState<PublicDataset[]>([]);
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const data = await publicDataApi.listDatasets(
          category ? { category } : {}
        );
        if (!cancelled) setDatasets(data.items || []);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load datasets");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })()
    return () => {
      cancelled = true
    }
  }, [category])

  const selectCategory = (next: string) => {
    setLoading(true);
    setCategory(next);
  };

  return (
    <main className="mx-auto max-w-6xl px-4 py-12">
      <h1 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
        Open Data Portal
      </h1>
      <p className="mt-3 text-lg text-gray-600 dark:text-gray-300">
        Discover publicly available datasets with full metadata, licensing, and
        methodology information.
      </p>

      {/* Category Filter */}
      <div className="mt-6 flex flex-wrap gap-2">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.value}
            onClick={() => selectCategory(cat.value)}
            className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
              category === cat.value
                ? "bg-blue-600 text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Dataset List */}
      {loading && (
        <div className="mt-8 text-center text-gray-500">Loading datasets...</div>
      )}
      {error && (
        <div className="mt-8 rounded-lg bg-red-50 p-4 text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      )}
      {!loading && !error && datasets.length === 0 && (
        <div className="mt-8 text-center text-gray-500">
          No datasets found for this category.
        </div>
      )}
      <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {datasets.map((ds) => (
          <div
            key={ds.slug}
            className="flex flex-col rounded-lg border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800"
          >
            <div className="flex items-start justify-between">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                {ds.name}
              </h2>
              <span className="text-xs">{FRESHNESS_LABELS[ds.freshness] || ds.freshness}</span>
            </div>
            {ds.name_hi && (
              <p className="text-sm text-gray-500 dark:text-gray-400">{ds.name_hi}</p>
            )}
            {ds.description && (
              <p className="mt-2 flex-1 text-sm text-gray-600 dark:text-gray-300 line-clamp-3">
                {ds.description}
              </p>
            )}
            <div className="mt-4 space-y-1 text-xs text-gray-500 dark:text-gray-400">
              {ds.publisher && <div>Publisher: {ds.publisher}</div>}
              {ds.source && <div>Source: {ds.source}</div>}
              {ds.license && <div>License: {ds.license}</div>}
              {ds.version && <div>Version: {ds.version}</div>}
              {ds.record_count !== null && (
                <div>Records: {ds.record_count.toLocaleString()}</div>
              )}
              {ds.last_updated_at && (
                <div>
                  Last Updated:{" "}
                  {new Date(ds.last_updated_at).toLocaleDateString()}
                </div>
              )}
              {ds.update_frequency && (
                <div>Update Frequency: {ds.update_frequency}</div>
              )}
            </div>
            <div className="mt-4 flex gap-2">
              <a
                href={`/api/v1/public-data/datasets/${ds.slug}`}
                className="rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
              >
                View Details
              </a>
              <a
                href={`/api/v1/public-data/datasets/${ds.slug}/records?format=csv`}
                className="rounded bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
              >
                Download CSV
              </a>
            </div>
          </div>
        ))}
      </div>

      {/* Attribution */}
      <div className="mt-12 rounded-lg border border-gray-200 bg-gray-50 p-6 dark:border-gray-700 dark:bg-gray-900">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
          Data Attribution & Licensing
        </h2>
        <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">
          All datasets on this portal include their source, publisher, license,
          and version information. Please respect the license terms when using
          this data. Attribution is required for most datasets. Contact the
          publisher for specific usage rights.
        </p>
      </div>
    </main>
  );
}
