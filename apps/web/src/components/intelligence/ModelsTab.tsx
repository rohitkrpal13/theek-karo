"use client"

import { useCallback, useEffect, useState } from "react"

import { SectionCard, fmtDate } from "@/components/intelligence/shared"
import { Badge, EmptyState, ErrorState, Skeleton } from "@/components/ui/primitives"
import { intelligenceApi } from "@/lib/api"
import type { ModelVersionItem } from "@/lib/api"
import { useT } from "@/lib/i18n-client"

export function ModelsTab() {
  const t = useT()
  const [models, setModels] = useState<ModelVersionItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const res = await intelligenceApi.listModelVersions()
      setModels(res.models)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load])

  if (error) return <ErrorState title={t("intelligence.error")} detail={error} onRetry={load} />
  if (!models)
    return (
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} height={64} />
        ))}
      </div>
    )

  return (
    <div className="space-y-5">
      <p className="text-xs text-(--color-ink-muted)">{t("intelligence.models.subtitle")}</p>
      {models.length === 0 ? (
        <EmptyState icon="info" title={t("intelligence.empty")} />
      ) : (
        models.map((model) => (
          <SectionCard key={`${model.model_name}-${model.version}`} title={`${model.model_name} · ${model.version}`}>
            <div className="flex flex-wrap items-center gap-3 text-sm text-(--color-ink-muted)">
              <Badge tone={model.status === "active" ? "success" : "default"}>{model.status}</Badge>
              <span>
                {t("intelligence.models.type")}: {model.model_type}
              </span>
              {model.training_data_ref && (
                <span>
                  {t("intelligence.models.training")}: {model.training_data_ref}
                </span>
              )}
              {model.deployed_at && (
                <span>
                  {t("intelligence.models.deployed")}: {fmtDate(model.deployed_at, "en")}
                </span>
              )}
            </div>
            {model.feature_definition && (
              <pre className="mt-3 overflow-x-auto rounded-(--radius-md) border border-(--color-line) bg-(--color-surface-raised) p-3 text-xs text-(--color-ink-muted)">
                {JSON.stringify(model.feature_definition, null, 2)}
              </pre>
            )}
          </SectionCard>
        ))
      )}
    </div>
  )
}
