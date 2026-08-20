/**
 * Phase 23 — /data-explorer page.
 *
 * Users can explore approved datasets with filters, table view,
 * charts, download, source, and methodology information.
 */

"use client";

import { useEffect, useState } from "react";

import { publicDataApi, type PublicDataset } from "@/lib/api/public-data";

type ExplorerRecord = Record<string, unknown> & {
  id?: string;
};

export default function DataExplorerPage() {
  const [datasets, setDatasets] = useState<PublicDataset[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<string>("");
  const [records, setRecords] = useState<ExplorerRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    status: "",
    date_from: "",
    date_to: "",
  });

  // Load dataset list
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const data = await publicDataApi.listDatasets();
        if (!cancelled) setDatasets(data.items || []);
      } catch {
        if (!cancelled) setDatasets([]);
      }
    })()
    return () => {
      cancelled = true
    }
  }, []);

  // Load records when dataset or filters change
  useEffect(() => {
    if (!selectedDataset) return
    let cancelled = false
    ;(async () => {
      try {
        const data = await publicDataApi.listRecords(selectedDataset, {
          status: filters.status || undefined,
          date_from: filters.date_from || undefined,
          date_to: filters.date_to || undefined,
          limit: 50,
        });
        if (!cancelled) setRecords(data.items || []);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load records");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })()
    return () => {
      cancelled = true
    }
  }, [selectedDataset, filters]);

  const selectedMeta = datasets.find((d) => d.slug === selectedDataset);

  const applyFilters = (next: Partial<typeof filters>) => {
    setFilters((f) => ({ ...f, ...next }));
    setLoading(true);
  };

  return (
    <main className="mx-auto max-w-7xl px-4 py-12">
      <h1 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
        Data Explorer
      </h1>
      <p className="mt-3 text-lg text-gray-600 dark:text-gray-300">
        Explore approved datasets with filters, tables, and source
        information.
      </p>

      <div className="mt-8 grid gap-6 lg:grid-cols-4">
        {/* Sidebar — Dataset Selection + Filters */}
        <aside className="space-y-4 lg:col-span-1">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
              Dataset
            </label>
            <select
              value={selectedDataset}
              onChange={(e) => { setLoading(true); setSelectedDataset(e.target.value); }}
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
            >
              <option value="">Select a dataset</option>
              {datasets.map((ds) => (
                <option key={ds.slug} value={ds.slug}>
                  {ds.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
              Status
            </label>
            <select
              value={filters.status}
              onChange={(e) => applyFilters({ status: e.target.value })}
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
            >
              <option value="">All</option>
              <option value="open">Open</option>
              <option value="resolved">Resolved</option>
              <option value="verified">Verified</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
              Date From
            </label>
            <input
              type="date"
              value={filters.date_from}
              onChange={(e) => applyFilters({ date_from: e.target.value })}
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
              Date To
            </label>
            <input
              type="date"
              value={filters.date_to}
              onChange={(e) => applyFilters({ date_to: e.target.value })}
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
            />
          </div>

          {selectedMeta && (
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-900">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
                Dataset Info
              </h3>
              <dl className="mt-2 space-y-1 text-xs text-gray-600 dark:text-gray-400">
                <div>
                  <dt className="inline font-medium">Version:</dt>{" "}
                  <dd className="inline">{selectedMeta.version}</dd>
                </div>
                <div>
                  <dt className="inline font-medium">Records:</dt>{" "}
                  <dd className="inline">
                    {selectedMeta.record_count?.toLocaleString() ?? "N/A"}
                  </dd>
                </div>
                <div>
                  <dt className="inline font-medium">Freshness:</dt>{" "}
                  <dd className="inline">{selectedMeta.freshness}</dd>
                </div>
                {selectedMeta.last_updated_at && (
                  <div>
                    <dt className="inline font-medium">Updated:</dt>{" "}
                    <dd className="inline">
                      {new Date(
                        selectedMeta.last_updated_at
                      ).toLocaleDateString()}
                    </dd>
                  </div>
                )}
              </dl>
            </div>
          )}
        </aside>

        {/* Main Content — Records Table */}
        <section className="lg:col-span-3">
          {!selectedDataset ? (
            <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-gray-300 text-gray-500 dark:border-gray-600">
              Select a dataset to explore
            </div>
          ) : loading ? (
            <div className="flex h-64 items-center justify-center text-gray-500">
              Loading records...
            </div>
          ) : error ? (
            <div className="rounded-lg bg-red-50 p-4 text-red-700 dark:bg-red-950 dark:text-red-300">
              {error}
            </div>
          ) : records.length === 0 ? (
            <div className="flex h-64 items-center justify-center text-gray-500">
              No records found
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                <thead className="bg-gray-50 dark:bg-gray-800">
                  <tr>
                    {Object.keys(records[0])
                      .filter((k) => k !== "id")
                      .slice(0, 6)
                      .map((key) => (
                        <th
                          key={key}
                          className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400"
                        >
                          {key.replace(/_/g, " ")}
                        </th>
                      ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white dark:divide-gray-700 dark:bg-gray-900">
                  {records.map((record, idx) => (
                    <tr
                      key={record.id || idx}
                      className="hover:bg-gray-50 dark:hover:bg-gray-800"
                    >
                      {Object.keys(record)
                        .filter((k) => k !== "id")
                        .slice(0, 6)
                        .map((key) => (
                          <td
                            key={key}
                            className="whitespace-nowrap px-4 py-2 text-sm text-gray-700 dark:text-gray-300"
                          >
                            {typeof record[key] === "object"
                              ? JSON.stringify(record[key])
                              : String(record[key] ?? "")}
                          </td>
                        ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Methodology & Source */}
          {selectedMeta && (
            <div className="mt-6 rounded-lg border border-gray-200 bg-gray-50 p-6 dark:border-gray-700 dark:bg-gray-900">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
                Methodology & Source
              </h3>
              <p className="mt-2 text-xs text-gray-600 dark:text-gray-400">
                This dataset is derived from{" "}
                <span className="font-medium">{selectedMeta.name}</span>. The
                data has been processed and validated through the platform&apos;s
                data quality engine. For the original source data, please
                contact the publisher. Freshness and completeness metrics are
                available in the dataset details.
              </p>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
