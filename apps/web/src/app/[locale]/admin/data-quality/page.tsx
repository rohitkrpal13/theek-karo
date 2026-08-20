/**
 * Phase 23 — /admin/data-quality admin page.
 *
 * Sections: Sources, Datasets, Imports, Conflicts, Duplicates,
 * Corrections, Disputes, Verification, Schema Changes.
 */

"use client";

import { useEffect, useState } from "react";

import { dataTrustApi } from "@/lib/api/data-trust";
import type { DataTrustDashboard, DataConflict, DisputeRecord } from "@/lib/api/data-trust";

export default function AdminDataQualityPage() {
  const [dashboard, setDashboard] = useState<DataTrustDashboard | null>(null);
  const [conflicts, setConflicts] = useState<DataConflict[]>([]);
  const [disputes, setDisputes] = useState<DisputeRecord[]>([]);
  const [activeTab, setActiveTab] = useState<
    "overview" | "conflicts" | "disputes" | "sources"
  >("overview");
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [dash, conf, disp] = await Promise.all([
          dataTrustApi.getDashboard().catch(() => null),
          dataTrustApi.listConflicts({ limit: 20 }).catch(() => ({ items: [] })),
          dataTrustApi.listDisputes({ limit: 20 }).catch(() => ({ items: [] })),
        ])
        if (cancelled) return
        if (dash === null && conf.items.length === 0 && disp.items.length === 0) {
          setFetchError(
            "Dashboard data is unavailable — this section requires an admin account with data-trust permissions."
          )
        }
        setDashboard(dash)
        setConflicts(conf.items)
        setDisputes(disp.items)
      } catch {
        if (!cancelled) {
          setFetchError("Failed to load the data quality dashboard. Please try again.")
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, []);

  if (loading) {
    return (
      <main className="mx-auto max-w-7xl px-4 py-12">
        <div className="text-center text-gray-500">
          Loading data quality dashboard...
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-12">
      <h1 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
        Data Quality Dashboard
      </h1>
      <p className="mt-3 text-lg text-gray-600 dark:text-gray-300">
        Monitor data sources, quality, conflicts, disputes, and verification
        status.
      </p>

      {fetchError && (
        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
          {fetchError}
        </div>
      )}

      {/* Tabs */}
      <div className="mt-6 flex gap-1 rounded-lg bg-gray-100 p-1 dark:bg-gray-800">
        {(["overview", "conflicts", "disputes", "sources"] as const).map(
          (tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === tab
                  ? "bg-white text-gray-900 shadow dark:bg-gray-700 dark:text-white"
                  : "text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white"
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          )
        )}
      </div>

      {/* Overview Tab */}
      {activeTab === "overview" && dashboard && (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Active Sources"
            value={dashboard.active_sources}
            total={dashboard.total_sources}
            color="green"
          />
          <StatCard
            label="Failed Sources"
            value={dashboard.failed_sources}
            color="red"
          />
          <StatCard
            label="Total Datasets"
            value={dashboard.total_datasets}
            color="blue"
          />
          <StatCard
            label="Open Conflicts"
            value={dashboard.open_conflicts}
            total={dashboard.total_conflicts}
            color="amber"
          />
          <StatCard
            label="Open Disputes"
            value={dashboard.open_disputes}
            total={dashboard.total_disputes}
            color="amber"
          />
          <StatCard
            label="Verified Evidence"
            value={dashboard.verified_evidence}
            total={dashboard.total_evidence}
            color="green"
          />
          <StatCard
            label="Total Verifications"
            value={dashboard.total_verifications}
            color="blue"
          />
          <StatCard
            label="Quarantined"
            value={dashboard.quarantined_records}
            color="red"
          />
        </div>
      )}

      {/* Conflicts Tab */}
      {activeTab === "conflicts" && (
        <div className="mt-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Data Conflicts ({conflicts.length})
          </h2>
          <div className="mt-4 space-y-3">
            {conflicts.length === 0 ? (
              <p className="text-gray-500">No conflicts found.</p>
            ) : (
              conflicts.map((c) => (
                <div
                  key={c.id}
                  className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="rounded bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700 dark:bg-gray-700 dark:text-gray-300">
                        {c.entity_type}
                      </span>
                      <span className="ml-2 text-sm font-medium text-gray-900 dark:text-white">
                        {c.field_name}
                      </span>
                    </div>
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-medium ${
                        c.severity === "CRITICAL"
                          ? "bg-red-100 text-red-700"
                          : c.severity === "HIGH"
                            ? "bg-orange-100 text-orange-700"
                            : "bg-gray-100 text-gray-700"
                      }`}
                    >
                      {c.severity}
                    </span>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-4 text-xs text-gray-600 dark:text-gray-400">
                    <div>
                      <span className="font-medium">Source A:</span>{" "}
                      {JSON.stringify(c.source_a_value)}
                    </div>
                    <div>
                      <span className="font-medium">Source B:</span>{" "}
                      {JSON.stringify(c.source_b_value)}
                    </div>
                  </div>
                  <div className="mt-2 text-xs text-gray-500">
                    Status: {c.status} |{" "}
                    {c.created_at ? new Date(c.created_at).toLocaleString() : ""}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Disputes Tab */}
      {activeTab === "disputes" && (
        <div className="mt-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Disputes ({disputes.length})
          </h2>
          <div className="mt-4 space-y-3">
            {disputes.length === 0 ? (
              <p className="text-gray-500">No disputes found.</p>
            ) : (
              disputes.map((d) => (
                <div
                  key={d.id}
                  className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="rounded bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700 dark:bg-gray-700 dark:text-gray-300">
                        {d.dispute_target_type}
                      </span>
                      <span
                        className={`ml-2 rounded px-2 py-0.5 text-xs font-medium ${
                          d.status === "OPEN"
                            ? "bg-yellow-100 text-yellow-700"
                            : d.status === "UNDER_REVIEW"
                              ? "bg-blue-100 text-blue-700"
                              : "bg-gray-100 text-gray-700"
                        }`}
                      >
                        {d.status}
                      </span>
                    </div>
                    {d.public_banner && (
                      <span className="text-xs text-amber-600">
                        ⚠ Public banner active
                      </span>
                    )}
                  </div>
                  <p className="mt-2 text-sm text-gray-700 dark:text-gray-300">
                    {d.reason}
                  </p>
                  <div className="mt-2 text-xs text-gray-500">
                    Filed:{" "}
                    {d.created_at ? new Date(d.created_at).toLocaleString() : ""}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Sources Tab */}
      {activeTab === "sources" && (
        <div className="mt-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Source Health
          </h2>
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
            Source health reflects operational status (sync success, response
            times), not data truthfulness. A healthy source may still contain
            inaccurate data.
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <div className="rounded-lg border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-950">
              <div className="text-2xl font-bold text-green-700 dark:text-green-300">
                {dashboard?.active_sources ?? 0}
              </div>
              <div className="text-sm text-green-600 dark:text-green-400">
                Active Sources
              </div>
            </div>
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-950">
              <div className="text-2xl font-bold text-red-700 dark:text-red-300">
                {dashboard?.failed_sources ?? 0}
              </div>
              <div className="text-sm text-red-600 dark:text-red-400">
                Failed Sources
              </div>
            </div>
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-950">
              <div className="text-2xl font-bold text-amber-700 dark:text-amber-300">
                {dashboard?.stale_sources ?? 0}
              </div>
              <div className="text-sm text-amber-600 dark:text-amber-400">
                Stale Sources
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

function StatCard({
  label,
  value,
  total,
  color,
}: {
  label: string;
  value: number;
  total?: number;
  color: "green" | "red" | "blue" | "amber";
}) {
  const colors = {
    green: "border-green-200 bg-green-50 text-green-700 dark:border-green-800 dark:bg-green-950 dark:text-green-300",
    red: "border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300",
    blue: "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-300",
    amber: "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300",
  };

  return (
    <div className={`rounded-lg border p-4 ${colors[color]}`}>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-sm opacity-80">{label}</div>
      {total !== undefined && total > 0 && (
        <div className="mt-1 text-xs opacity-60">of {total} total</div>
      )}
    </div>
  );
}
