"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import { useEffect, useRef, useState } from "react"

import { Button, Combobox } from "@/components/ui/primitives"
import { Icon } from "@/components/ui/icons"
import { civicApi, institutionsApi, reportsApi } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { useT } from "@/lib/i18n-client"
import type {
  Category,
  CoordinateSource,
  Institution,
  IssueType,
  ReportSeverity,
} from "@/lib/types"

interface Props {
  initialCategory?: string
  initialLat?: number
  initialLon?: number
  draftId?: string
}

interface UploadedFile {
  id: string
  name: string
  size: number
  mimeType: string
  previewUrl: string
}

const STORAGE_DRAFT_KEY = "tk_report_draft_v1"

export function SubmitWizard({ initialCategory, initialLat, initialLon, draftId }: Props) {
  const t = useT()
  const params = useParams<{ locale?: string }>()
  const locale = params.locale ?? "en"
  const { user } = useAuth()

  // Steps:
  // 0: Category Selection
  // 1: Location & Coordinates
  // 2: Institution Linkage
  // 3: Issue Type, Severity, Details & Category Schema
  // 4: Evidence Media Upload
  // 5: Review & Final Submission
  const [step, setStep] = useState(0)

  // Form State
  const [categories, setCategories] = useState<Category[]>([])
  const [selectedCategory, setSelectedCategory] = useState<Category | null>(null)
  const [issueTypes, setIssueTypes] = useState<IssueType[]>([])
  const [selectedIssueType, setSelectedIssueType] = useState<IssueType | null>(null)

  const [position, setPosition] = useState<[number, number]>([
    initialLon ?? 75.7873,
    initialLat ?? 26.9124,
  ])
  const [accuracy, setAccuracy] = useState(15)
  const [coordSource, setCoordSource] = useState<CoordinateSource>("USER_SELECTED")
  const [addressHint, setAddressHint] = useState("")

  const [institutions, setInstitutions] = useState<Institution[]>([])
  const [selectedInstitution, setSelectedInstitution] = useState<Institution | null>(null)
  const [noInstitution, setNoInstitution] = useState(false)

  // Details
  const [observedDateOption, setObservedDateOption] = useState<"today" | "yesterday" | "custom">("today")
  const [customObservedDate, setCustomObservedDate] = useState<string>(new Date().toISOString().split("T")[0])
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [severity, setSeverity] = useState<ReportSeverity>("medium")
  const [fields, setFields] = useState<Record<string, unknown>>({})

  // Evidence files
  const [files, setFiles] = useState<UploadedFile[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)
  const cameraInputRef = useRef<HTMLInputElement>(null)

  // AI Suggestion State
  const [aiLoading, setAiLoading] = useState(false)
  const [aiSuggestion, setAiSuggestion] = useState<{
    category: string | null
    title: string | null
    severity: ReportSeverity | null
    missing: string[]
    hazard: string | null
  } | null>(null)

  // Draft & Submission State
  const [activeDraftId, setActiveDraftId] = useState<string | null>(draftId || null)
  const [autoSavedTime, setAutoSavedTime] = useState<string | null>(null)
  const [hasRestoredDraft, setHasRestoredDraft] = useState(false)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<{ id: string; ticket_no: string } | null>(null)
  const idempotencyKey = useRef<string>(crypto.randomUUID())

  // Load Categories on mount
  useEffect(() => {
    async function loadCategories() {
      try {
        const res = await civicApi.listCategories()
        setCategories(res.items)
        if (initialCategory) {
          const match = res.items.find((c) => c.slug === initialCategory)
          if (match) setSelectedCategory(match)
        }
      } catch (err) {
        console.error("Failed to load categories in wizard", err)
      }
    }
    void loadCategories()
  }, [initialCategory])

  // Load Issue Types when category changes
  useEffect(() => {
    async function loadIssueTypes() {
      if (!selectedCategory) {
        setIssueTypes([])
        setSelectedIssueType(null)
        return
      }
      try {
        const list = await civicApi.listIssueTypes(selectedCategory.slug)
        setIssueTypes(list)
      } catch (err) {
        console.error("Failed to load issue types", err)
        setIssueTypes([])
      }
    }
    void loadIssueTypes()
  }, [selectedCategory])

  // Load Institutions
  useEffect(() => {
    async function loadInstitutions() {
      try {
        const res = await institutionsApi.list({ limit: 40 })
        setInstitutions(res.items)
      } catch (err) {
        console.error("Failed to load institutions in wizard", err)
      }
    }
    void loadInstitutions()
  }, [selectedCategory])

  // Restore local draft if available (only in browser environment)
  useEffect(() => {
    if (typeof window === "undefined" || hasRestoredDraft || activeDraftId || initialCategory) return
    const restoreTimer = setTimeout(() => {
      const raw = localStorage.getItem(STORAGE_DRAFT_KEY)
      if (raw) {
        try {
          const saved = JSON.parse(raw)
          if (saved.title || saved.description || saved.category_slug) {
            setTitle(saved.title || "")
            setDescription(saved.description || "")
            setSeverity(saved.severity || "medium")
            setAddressHint(saved.address_hint || "")
            if (saved.position) setPosition(saved.position)
            if (saved.coordSource) setCoordSource(saved.coordSource)
            if (saved.fields) setFields(saved.fields)
            setAutoSavedTime("Restored from backup")
          }
        } catch (e) {
          console.warn("Failed to parse local draft", e)
        }
      }
      setHasRestoredDraft(true)
    }, 0)
    return () => clearTimeout(restoreTimer)
  }, [hasRestoredDraft, activeDraftId, initialCategory])

  // Auto-save local draft
  useEffect(() => {
    if (typeof window === "undefined") return
    if (done) {
      localStorage.removeItem(STORAGE_DRAFT_KEY)
      return
    }
    const timer = setTimeout(() => {
      const payload = {
        category_slug: selectedCategory?.slug,
        title,
        description,
        severity,
        position,
        coordSource,
        addressHint,
        fields,
        updatedAt: new Date().toISOString(),
      }
      localStorage.setItem(STORAGE_DRAFT_KEY, JSON.stringify(payload))
      setAutoSavedTime(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }))
    }, 2000)
    return () => clearTimeout(timer)
  }, [selectedCategory, title, description, severity, position, coordSource, addressHint, fields, done])

  const stepsList = [
    { label: t("submit.step.category") },
    { label: t("submit.step.location") },
    { label: t("submit.step.institution") },
    { label: t("submit.step.fields") },
    { label: t("submit.step.evidence") },
    { label: t("submit.step.review") },
  ]

  function categorySchema(): Record<string, unknown> | null {
    if (!selectedCategory) return null
    const schema = selectedCategory.form_schema as { properties?: Record<string, unknown> }
    return schema.properties ?? null
  }

  function schemaFields(): Record<string, unknown> {
    // Only ever submit fields the current category's schema actually declares.
    // Keeps stale values from a previously selected category from being sent
    // to the API (categories with additionalProperties:false reject extras 422).
    const props = categorySchema()
    if (!props) return {}
    return Object.fromEntries(Object.entries(fields).filter(([k]) => k in props))
  }

  function schemaRequired(): string[] {
    if (!selectedCategory) return []
    const req = (selectedCategory.form_schema as { required?: unknown }).required
    return Array.isArray(req) ? (req as string[]) : []
  }

  function canNext(): boolean {
    if (step === 0) return selectedCategory !== null
    if (step === 1) return position[0] !== 0 && position[1] !== 0
    if (step === 2) return true // Institution is optional
    if (step === 3) {
      const filled = (name: string) => {
        const val = fields[name]
        return val !== undefined && val !== "" && val !== null
      }
      return (
        title.trim().length >= 5 &&
        description.trim().length >= 10 &&
        schemaRequired().every(filled)
      )
    }
    if (step === 4) return true // Evidence is optional
    return true
  }

  // AI-Assisted Intake Helper
  async function handleAiAssist() {
    if (!description.trim() || description.trim().length < 5) return
    setAiLoading(true)
    setAiSuggestion(null)
    try {
      const res = await reportsApi.aiSuggestIntake({
        description,
        location: { type: "Point", coordinates: position },
        category_hint: selectedCategory?.slug,
      })
      setAiSuggestion({
        category: res.category_suggestion,
        title: res.title_suggestion,
        severity: res.severity_suggestion,
        missing: res.missing_information,
        hazard: res.hazard_alert,
      })
    } catch (err) {
      console.warn("AI suggestion error:", err)
    } finally {
      setAiLoading(false)
    }
  }

  function applyAiSuggestion() {
    if (!aiSuggestion) return
    if (aiSuggestion.title && !title) {
      setTitle(aiSuggestion.title)
    }
    if (aiSuggestion.severity) {
      setSeverity(aiSuggestion.severity)
    }
    if (aiSuggestion.category && !selectedCategory) {
      const match = categories.find((c) => c.slug === aiSuggestion.category)
      if (match) setSelectedCategory(match)
    }
    setAiSuggestion(null)
  }

  // Evidence File Handling
  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files
    if (!selected) return

    const newFiles: UploadedFile[] = Array.from(selected).map((f) => ({
      id: crypto.randomUUID(),
      name: f.name,
      size: f.size,
      mimeType: f.type || "image/jpeg",
      previewUrl: URL.createObjectURL(f),
    }))

    setFiles((prev) => [...prev, ...newFiles])
  }

  function removeFile(id: string) {
    setFiles((prev) => prev.filter((f) => f.id !== id))
  }

  // Calculate Observation Timestamp
  function getObservedAt(): string {
    const now = new Date()
    if (observedDateOption === "today") {
      return now.toISOString()
    }
    if (observedDateOption === "yesterday") {
      const y = new Date(now.getTime() - 24 * 60 * 60 * 1000)
      return y.toISOString()
    }
    return new Date(customObservedDate).toISOString()
  }

  // Save backend draft explicitly
  async function handleSaveBackendDraft() {
    if (!user) {
      setError("Please log in to save drafts to your account cloud.")
      return
    }
    setError(null)
    try {
      if (activeDraftId) {
        await reportsApi.updateDraft(activeDraftId, {
          category_slug: selectedCategory?.slug,
          institution_id: selectedInstitution?.id || null,
          issue_type_id: selectedIssueType?.id || null,
          title: title || "Draft Observation",
          description,
          severity,
          location: { type: "Point", coordinates: position },
          location_accuracy_m: accuracy,
          coordinate_source: coordSource,
          observed_at: getObservedAt(),
          address_hint: addressHint,
          fields: schemaFields(),
        })
        setAutoSavedTime(`Cloud draft updated (${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })})`)
      } else {
        const draft = await reportsApi.createDraft({
          category_slug: selectedCategory?.slug,
          institution_id: selectedInstitution?.id || null,
          issue_type_id: selectedIssueType?.id || null,
          title: title || "Draft Observation",
          description,
          severity,
          location: { type: "Point", coordinates: position },
          location_accuracy_m: accuracy,
          coordinate_source: coordSource,
          observed_at: getObservedAt(),
          address_hint: addressHint,
          fields: schemaFields(),
        })
        setActiveDraftId(draft.id)
        setAutoSavedTime(`Saved to account draft #${draft.ticket_no}`)
      }
    } catch (err) {
      console.warn("Draft save failed", err)
      setError("Failed to save draft to server")
    }
  }

  // Final Submit
  async function handleSubmit() {
    if (!selectedCategory) return
    setSending(true)
    setError(null)

    try {
      let result
      if (activeDraftId) {
        result = await reportsApi.submitDraft(activeDraftId, {
          category_slug: selectedCategory.slug,
          institution_id: selectedInstitution?.id || null,
          issue_type_id: selectedIssueType?.id || null,
          title,
          description,
          severity,
          location: { type: "Point", coordinates: position },
          location_accuracy_m: accuracy,
          coordinate_source: coordSource,
          observed_at: getObservedAt(),
          address_hint: addressHint,
          fields: schemaFields(),
        })
      } else {
        result = await reportsApi.submit(
          {
            category_slug: selectedCategory.slug,
            institution_id: selectedInstitution?.id || null,
            issue_type_id: selectedIssueType?.id || null,
            title,
            description,
            severity,
            location: { type: "Point", coordinates: position },
            location_accuracy_m: accuracy,
            coordinate_source: coordSource,
            observed_at: getObservedAt(),
            address_hint: addressHint,
            fields: schemaFields(),
          },
          idempotencyKey.current,
        )
      }

      if (typeof window !== "undefined") {
        localStorage.removeItem(STORAGE_DRAFT_KEY)
      }
      setDone({ id: result.id, ticket_no: result.ticket_no })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit report")
    } finally {
      setSending(false)
    }
  }

  // Success Confirmation Screen
  if (done) {
    return (
      <div className="mx-auto max-w-lg rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-8 text-center shadow-xs">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
          <Icon name="check" size={32} />
        </div>
        <h2 className="mt-4 text-2xl font-black text-(--color-ink)">
          {t("submit.thanks")}
        </h2>
        <p className="mt-2 text-sm text-(--color-ink-muted)">
          Your observation has been registered on the civic ledger with unique ticket:
        </p>
        <div className="mt-3 flex items-center justify-center gap-2">
          <p className="rounded-(--radius-md) bg-(--color-surface-sunken) px-4 py-2 font-mono text-base font-bold text-(--color-primary-strong)">
            {done.ticket_no}
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              void navigator.clipboard.writeText(done.ticket_no)
            }}
          >
            Copy
          </Button>
        </div>

        <p className="mt-4 text-xs text-(--color-ink-muted)">
          Community members and verifiers can now corroborate this report. You can track status transitions and resolution progress anytime.
        </p>

        <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-center">
          <Link href={`/${locale}/reports/${done.id}`}>
            <Button variant="primary" size="md">
              View Report Details
            </Button>
          </Link>
          <Button
            variant="outline"
            size="md"
            onClick={() => {
              setDone(null)
              setStep(0)
              setTitle("")
              setDescription("")
              setFiles([])
              setActiveDraftId(null)
              idempotencyKey.current = crypto.randomUUID()
            }}
          >
            Submit Another Report
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {/* Wizard Header & Stepper */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-black tracking-tight">{t("submit.title")}</h1>
          {autoSavedTime && (
            <span className="text-xs text-(--color-ink-muted) flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-emerald-500 inline-block" />
              {autoSavedTime}
            </span>
          )}
        </div>
        <nav aria-label="Submission progress" className="w-full">
          <ol className="flex items-center justify-between gap-1 text-xs">
            {stepsList.map((s, idx) => {
              const isCurrent = idx === step
              const isDone = idx < step
              return (
                <li
                  key={s.label}
                  className={`flex flex-1 items-center gap-1 border-b-2 pb-1 font-medium transition-colors ${
                    isCurrent
                      ? "border-(--color-primary) text-(--color-primary-strong) font-bold"
                      : isDone
                        ? "border-emerald-500 text-emerald-700 dark:text-emerald-400"
                        : "border-(--color-line) text-(--color-ink-muted)"
                  }`}
                >
                  <span className="truncate">{s.label}</span>
                </li>
              )
            })}
          </ol>
        </nav>
      </div>

      {error && (
        <div role="alert" className="rounded-(--radius-md) bg-rose-50 border border-rose-200 p-3 text-xs text-rose-800 dark:bg-rose-950 dark:border-rose-800 dark:text-rose-200">
          {error}
        </div>
      )}

      {/* STEP 0: Category Selection */}
      {step === 0 && (
        <fieldset className="space-y-4">
          <legend className="text-base font-bold text-(--color-ink)">
            Select Civic Domain Category
          </legend>
          <p className="text-xs text-(--color-ink-muted)">
            Choose the civic sector that best corresponds to the problem you are observing.
          </p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {categories.map((cat) => {
              const isSelected = selectedCategory?.id === cat.id
              return (
                <button
                  key={cat.id}
                  type="button"
                  onClick={() => {
                  setSelectedCategory(cat)
                  const props = (cat.form_schema as { properties?: Record<string, unknown> })?.properties
                  const allowed = new Set(Object.keys(props ?? {}))
                  setFields((prev) =>
                    Object.fromEntries(Object.entries(prev).filter(([k]) => allowed.has(k))),
                  )
                }}
                  className={`flex flex-col items-start justify-between rounded-(--radius-lg) border p-4 text-left transition-all ${
                    isSelected
                      ? "border-(--color-primary) bg-(--color-primary-soft) ring-2 ring-(--color-primary)"
                      : "border-(--color-line) bg-(--color-surface) hover:border-(--color-primary)"
                  }`}
                >
                  <span className="font-bold text-sm capitalize text-(--color-ink)">
                    {cat.slug.replace(/_/g, " ")}
                  </span>
                  <span className="mt-2 text-xs text-(--color-ink-muted)">
                    {isSelected ? "Selected ✓" : "Select"}
                  </span>
                </button>
              )
            })}
          </div>
        </fieldset>
      )}

      {/* STEP 1: Location & Coordinates */}
      {step === 1 && (
        <div className="space-y-4">
          <h2 className="text-base font-bold text-(--color-ink)">
            Incident Location
          </h2>
          <p className="text-xs text-(--color-ink-muted)">
            Provide accurate geographic coordinates and landmarks where the issue is situated.
          </p>

          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="input-lat" className="text-xs font-semibold text-(--color-ink-muted)">
                Latitude (WGS84)
              </label>
              <input
                id="input-lat"
                type="number"
                step="any"
                value={position[1]}
                onChange={(e) => {
                  setPosition([position[0], parseFloat(e.target.value) || 0])
                  setCoordSource("USER_SELECTED")
                }}
                className="mt-1 w-full rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-2.5 text-xs text-(--color-ink)"
              />
            </div>
            <div>
              <label htmlFor="input-lon" className="text-xs font-semibold text-(--color-ink-muted)">
                Longitude (WGS84)
              </label>
              <input
                id="input-lon"
                type="number"
                step="any"
                value={position[0]}
                onChange={(e) => {
                  setPosition([parseFloat(e.target.value) || 0, position[1]])
                  setCoordSource("USER_SELECTED")
                }}
                className="mt-1 w-full rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-2.5 text-xs text-(--color-ink)"
              />
            </div>
          </div>

          <div>
            <label htmlFor="address-hint" className="text-xs font-semibold text-(--color-ink-muted)">
              Landmark / Address Hint (Optional)
            </label>
            <input
              id="address-hint"
              type="text"
              placeholder="e.g. Opposite Government Senior Secondary School, Ward 12"
              value={addressHint}
              onChange={(e) => setAddressHint(e.target.value)}
              className="mt-1 w-full rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-2.5 text-xs text-(--color-ink)"
            />
          </div>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Button
              variant="outline"
              size="sm"
              icon="map"
              onClick={() => {
                if (navigator.geolocation) {
                  navigator.geolocation.getCurrentPosition(
                    (pos) => {
                      setPosition([pos.coords.longitude, pos.coords.latitude])
                      setAccuracy(Math.round(pos.coords.accuracy))
                      setCoordSource("DEVICE_LOCATION")
                    },
                    (err) => console.warn("GPS detection warning:", err),
                    { enableHighAccuracy: true, timeout: 10000 }
                  )
                }
              }}
            >
              Detect Device GPS ({accuracy}m accuracy)
            </Button>
            <span className="text-xs text-(--color-ink-muted)">
              Source: <span className="font-mono font-semibold text-(--color-ink)">{coordSource}</span>
            </span>
          </div>
        </div>
      )}

      {/* STEP 2: Optional Institution Linkage */}
      {step === 2 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-(--color-ink)">
              Linked Public Institution (Optional)
            </h2>
            <span className="text-xs text-(--color-ink-muted)">Optional</span>
          </div>
          <p className="text-xs text-(--color-ink-muted)">
            If this issue pertains to a specific school, hospital, ration shop, or public office, link its verified digital twin record.
          </p>

          <div className="flex items-center gap-2">
            <input
              id="no-inst-check"
              type="checkbox"
              checked={noInstitution}
              onChange={(e) => {
                setNoInstitution(e.target.checked)
                if (e.target.checked) setSelectedInstitution(null)
              }}
              className="rounded text-(--color-primary)"
            />
            <label htmlFor="no-inst-check" className="text-xs text-(--color-ink)">
              This issue is on a public road or open space (not inside an institution)
            </label>
          </div>

          {!noInstitution && (
            <>
              <Combobox
                label="Search institution"
                placeholder="Search institution name or official ID…"
                options={institutions.map((inst) => ({
                  value: inst.id,
                  label: `${inst.name} (${inst.operational_status})`,
                }))}
                onSelect={(val) => {
                  const match = institutions.find((i) => i.id === val)
                  setSelectedInstitution(match ?? null)
                  if (match && match.location_geojson) {
                    setPosition(match.location_geojson.coordinates)
                    setCoordSource("INSTITUTION_LOCATION")
                  }
                }}
              />

              {selectedInstitution && (
                <div className="flex items-center justify-between rounded-(--radius-md) border border-(--color-primary) bg-(--color-primary-soft) p-3">
                  <div>
                    <span className="text-xs font-bold text-(--color-primary-strong)">Selected Institution</span>
                    <p className="text-sm font-semibold text-(--color-ink)">{selectedInstitution.name}</p>
                    <p className="text-xs text-(--color-ink-muted)">Status: {selectedInstitution.operational_status}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setSelectedInstitution(null)}
                    className="text-xs text-(--color-danger) hover:underline"
                  >
                    {t("submit.file_remove")}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* STEP 3: Issue Details & Category Schema */}
      {step === 3 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-(--color-ink)">
              Issue Details & Category Schema
            </h2>
            <Button
              variant="outline"
              size="sm"
              disabled={aiLoading || !description.trim()}
              onClick={() => void handleAiAssist()}
            >
              {aiLoading ? "Analyzing…" : "✨ Auto-suggest (AI)"}
            </Button>
          </div>

          {/* AI Intake Suggestion Banner */}
          {aiSuggestion && (
            <div className="rounded-(--radius-lg) border border-purple-200 bg-purple-50/70 p-4 text-xs text-purple-950 dark:border-purple-900 dark:bg-purple-950/40 dark:text-purple-200 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-bold">✨ AI Intake Observation Suggestions</span>
                <Button variant="primary" size="sm" onClick={applyAiSuggestion}>
                  Apply Suggestions
                </Button>
              </div>
              {aiSuggestion.title && (
                <p>Suggested Title: <span className="font-semibold">{aiSuggestion.title}</span></p>
              )}
              {aiSuggestion.hazard && (
                <p className="font-bold text-amber-800 dark:text-amber-300">⚠️ {aiSuggestion.hazard}</p>
              )}
              {aiSuggestion.missing.length > 0 && (
                <p className="text-purple-800 dark:text-purple-300">
                  Tip: Adding details about ({aiSuggestion.missing.join(", ")}) will speed up resolution.
                </p>
              )}
            </div>
          )}

          {/* Observation Date */}
          <div>
            <label className="text-xs font-semibold text-(--color-ink-muted)">
              When did you observe this problem?
            </label>
            <div className="mt-1 flex gap-2">
              <button
                type="button"
                onClick={() => setObservedDateOption("today")}
                className={`rounded-(--radius-md) px-3 py-1.5 text-xs font-semibold border ${
                  observedDateOption === "today"
                    ? "border-(--color-primary) bg-(--color-primary-soft) text-(--color-primary-strong)"
                    : "border-(--color-line) bg-(--color-surface) text-(--color-ink)"
                }`}
              >
                Today
              </button>
              <button
                type="button"
                onClick={() => setObservedDateOption("yesterday")}
                className={`rounded-(--radius-md) px-3 py-1.5 text-xs font-semibold border ${
                  observedDateOption === "yesterday"
                    ? "border-(--color-primary) bg-(--color-primary-soft) text-(--color-primary-strong)"
                    : "border-(--color-line) bg-(--color-surface) text-(--color-ink)"
                }`}
              >
                Yesterday
              </button>
              <button
                type="button"
                onClick={() => setObservedDateOption("custom")}
                className={`rounded-(--radius-md) px-3 py-1.5 text-xs font-semibold border ${
                  observedDateOption === "custom"
                    ? "border-(--color-primary) bg-(--color-primary-soft) text-(--color-primary-strong)"
                    : "border-(--color-line) bg-(--color-surface) text-(--color-ink)"
                }`}
              >
                Custom Date
              </button>
            </div>
            {observedDateOption === "custom" && (
              <input
                type="date"
                value={customObservedDate}
                onChange={(e) => setCustomObservedDate(e.target.value)}
                className="mt-2 rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-2 text-xs text-(--color-ink)"
              />
            )}
          </div>

          {/* Issue Type Selector */}
          {issueTypes.length > 0 && (
            <div>
              <label htmlFor="issue-type-select" className="text-xs font-semibold text-(--color-ink-muted)">
                Specific Issue Type
              </label>
              <select
                id="issue-type-select"
                value={selectedIssueType?.id ?? ""}
                onChange={(e) => {
                  const match = issueTypes.find((it) => it.id === e.target.value)
                  setSelectedIssueType(match ?? null)
                }}
                className="mt-1 w-full rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-2.5 text-xs text-(--color-ink)"
              >
                <option value="">Select specific issue type…</option>
                {issueTypes.map((it) => (
                  <option key={it.id} value={it.id}>
                    {it.name_key} (Default SLA: {it.default_sla_hours}h)
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Title */}
          <div>
            <label htmlFor="issue-title" className="text-xs font-semibold text-(--color-ink-muted)">
              Issue Title (min 5 characters) *
            </label>
            <input
              id="issue-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Broken water pipeline on Main Street"
              className="mt-1 w-full rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-2.5 text-xs text-(--color-ink) focus:border-(--color-primary) focus:outline-hidden"
            />
          </div>

          {/* Severity */}
          <div>
            <label htmlFor="issue-severity" className="text-xs font-semibold text-(--color-ink-muted)">
              Severity Level
            </label>
            <select
              id="issue-severity"
              value={severity}
              onChange={(e) => setSeverity(e.target.value as ReportSeverity)}
              className="mt-1 w-full rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-2.5 text-xs text-(--color-ink)"
            >
              <option value="low">{t("report.severity.low")}</option>
              <option value="medium">{t("report.severity.medium")}</option>
              <option value="high">{t("report.severity.high")}</option>
              <option value="critical">{t("report.severity.critical")}</option>
            </select>
          </div>

          {/* Description */}
          <div>
            <label htmlFor="issue-desc" className="text-xs font-semibold text-(--color-ink-muted)">
              Detailed Description (min 10 characters) *
            </label>
            <textarea
              id="issue-desc"
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Provide clear, neutral observations of what is visible, affected area, and impact…"
              className="mt-1 w-full rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-2.5 text-xs text-(--color-ink) focus:border-(--color-primary) focus:outline-hidden"
            />
          </div>

          {/* Dynamic Category Properties */}
          {categorySchema() && (
            <div className="space-y-3 rounded-(--radius-md) border border-(--color-line) p-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-(--color-ink-muted)">
                Structured Category Attributes
              </h3>
              {Object.entries(categorySchema()!).map(([key, prop]) => {
                const req = schemaRequired().includes(key)
                const propObj = prop as { type?: string; description?: string }
                return (
                  <div key={key}>
                    <label htmlFor={`field-${key}`} className="text-xs font-semibold text-(--color-ink-muted) capitalize">
                      {key.replace(/_/g, " ")} {req ? "*" : ""}
                    </label>
                    <input
                      id={`field-${key}`}
                      type={propObj.type === "integer" ? "number" : "text"}
                      value={String(fields[key] ?? "")}
                      onChange={(e) =>
                        setFields((prev) => ({
                          ...prev,
                          [key]: propObj.type === "integer" ? parseInt(e.target.value, 10) || 0 : e.target.value,
                        }))
                      }
                      className="mt-1 w-full rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-2 text-xs text-(--color-ink)"
                    />
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* STEP 4: Evidence Media Upload */}
      {step === 4 && (
        <div className="space-y-4">
          <h2 className="text-base font-bold text-(--color-ink)">
            {t("submit.step.evidence")}
          </h2>
          <p className="text-xs text-(--color-ink-muted)">
            Attach photos, short videos, or documents corroborating this report. Images undergo automatic privacy verification before publishing.
          </p>

          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="image/jpeg,image/png,image/webp,video/mp4,application/pdf"
            className="hidden"
            onChange={handleFileUpload}
          />
          <input
            ref={cameraInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={handleFileUpload}
          />

          <div className="grid gap-3 sm:grid-cols-2">
            <div
              onClick={() => fileInputRef.current?.click()}
              className="flex cursor-pointer flex-col items-center justify-center rounded-(--radius-lg) border-2 border-dashed border-(--color-line) p-6 text-center hover:border-(--color-primary) hover:bg-(--color-surface-sunken)"
            >
              <Icon name="activity" size={28} />
              <p className="mt-2 text-sm font-semibold text-(--color-ink)">
                {t("submit.upload_gallery")}
              </p>
              <p className="mt-1 text-xs text-(--color-ink-muted)">
                {t("submit.upload_limits")}
              </p>
            </div>

            <div
              onClick={() => cameraInputRef.current?.click()}
              className="flex cursor-pointer flex-col items-center justify-center rounded-(--radius-lg) border-2 border-dashed border-(--color-line) p-6 text-center hover:border-(--color-primary) hover:bg-(--color-surface-sunken)"
            >
              <Icon name="check" size={28} />
              <p className="mt-2 text-sm font-semibold text-(--color-ink)">
                {t("submit.capture_camera")}
              </p>
              <p className="mt-1 text-xs text-(--color-ink-muted)">
                {t("submit.capture_hint")}
              </p>
            </div>
          </div>

          {files.length > 0 && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {files.map((file) => (
                <div
                  key={file.id}
                  className="relative rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-2 space-y-1"
                >
                  <p className="truncate text-xs font-semibold text-(--color-ink)">
                    {file.name}
                  </p>
                  <p className="text-xs text-(--color-ink-muted)">
                    {(file.size / 1024).toFixed(0)} KB · {t("submit.file_ready")}
                  </p>
                  <button
                    type="button"
                    onClick={() => removeFile(file.id)}
                    className="text-xs text-(--color-danger) hover:underline"
                  >
                    {t("submit.file_remove")}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* STEP 5: Review & Final Submission */}
      {step === 5 && (
        <div className="space-y-4 rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) p-6">
          <h2 className="text-lg font-bold text-(--color-ink)">
            {t("submit.review_title")}
          </h2>

          <dl className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <dt className="text-(--color-ink-muted)">Category</dt>
              <dd className="font-bold text-(--color-ink) capitalize">
                {selectedCategory?.slug.replace(/_/g, " ")}
              </dd>
            </div>
            <div>
              <dt className="text-(--color-ink-muted)">Severity</dt>
              <dd className="font-bold uppercase text-(--color-ink)">{severity}</dd>
            </div>
            <div>
              <dt className="text-(--color-ink-muted)">Observed Timestamp</dt>
              <dd className="font-mono text-(--color-ink)">
                {new Date(getObservedAt()).toLocaleDateString()}
              </dd>
            </div>
            <div>
              <dt className="text-(--color-ink-muted)">Coordinates ({coordSource})</dt>
              <dd className="font-mono text-(--color-ink)">
                {position[1].toFixed(4)}, {position[0].toFixed(4)}
              </dd>
            </div>
            <div className="col-span-2">
              <dt className="text-(--color-ink-muted)">Linked Institution</dt>
              <dd className="font-semibold text-(--color-ink)">
                {selectedInstitution ? selectedInstitution.name : t("submit.no_institution")}
              </dd>
            </div>
            <div className="col-span-2">
              <dt className="text-(--color-ink-muted)">Title</dt>
              <dd className="font-bold text-sm text-(--color-ink)">{title}</dd>
            </div>
            <div className="col-span-2">
              <dt className="text-(--color-ink-muted)">Description</dt>
              <dd className="text-xs text-(--color-ink) whitespace-pre-wrap">
                {description}
              </dd>
            </div>
            <div>
              <dt className="text-(--color-ink-muted)">Attached Evidence</dt>
              <dd className="font-semibold text-(--color-ink)">
                {files.length} file(s) attached
              </dd>
            </div>
          </dl>

          {!user && (
            <p className="rounded-(--radius-md) bg-amber-50 border border-amber-200 p-3 text-xs text-amber-800 dark:bg-amber-950 dark:border-amber-800 dark:text-amber-200">
              {t("submit.guest_note")}
            </p>
          )}
        </div>
      )}

      {/* Navigation Buttons */}
      <div className="flex items-center justify-between border-t border-(--color-line) pt-4">
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="md"
            disabled={step === 0 || sending}
            onClick={() => setStep((s) => Math.max(0, s - 1))}
          >
            {t("submit.back")}
          </Button>
          {user && !done && (
            <Button
              variant="outline"
              size="md"
              disabled={sending}
              onClick={() => void handleSaveBackendDraft()}
            >
              {t("submit.save_draft")}
            </Button>
          )}
        </div>

        {step < stepsList.length - 1 ? (
          <Button
            variant="primary"
            size="md"
            data-testid="wizard-next"
            disabled={!canNext()}
            onClick={() => setStep((s) => s + 1)}
          >
            {t("submit.next")}
          </Button>
        ) : (
          <Button
            variant="primary"
            size="md"
            disabled={sending}
            onClick={() => void handleSubmit()}
          >
            {sending ? t("submit.sending") : t("submit.done")}
          </Button>
        )}
      </div>
    </div>
  )
}