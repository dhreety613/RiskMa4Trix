import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { apiGet, apiPost } from '../api'
import MatrixChart from '../components/MatrixChart'
import RiskCard from '../components/RiskCard'
import type { Company as CompanyType, IngestAck, MatrixPoint } from '../types'
import { ZONE_COLOR, ZONE_ORDER } from '../zoneColors'

export default function Company() {
  const { ticker = '' } = useParams<{ ticker: string }>()
  const [zoneFilter, setZoneFilter] = useState<string>('')
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [includeGeneric, setIncludeGeneric] = useState(false)
  const [selectedRiskId, setSelectedRiskId] = useState<number | null>(null)

  const company = useQuery({
    queryKey: ['company', ticker],
    queryFn: () => apiGet<CompanyType>(`/companies/${ticker}`),
    retry: false,
  })

  const matrix = useQuery({
    queryKey: ['matrix', ticker, zoneFilter, categoryFilter, includeGeneric],
    queryFn: () => {
      const params = new URLSearchParams()
      if (zoneFilter) params.set('zone', zoneFilter)
      if (categoryFilter) params.set('category', categoryFilter)
      params.set('include_generic', String(includeGeneric))
      return apiGet<MatrixPoint[]>(`/companies/${ticker}/matrix?${params}`)
    },
    enabled: company.isSuccess,
  })

  const [ingesting, setIngesting] = useState(false)
  const triggerIngest = async () => {
    setIngesting(true)
    await apiPost<IngestAck>(`/companies/${ticker}/ingest`)
  }

  const categories = Array.from(
    new Map(
      (matrix.data ?? [])
        .filter((p) => p.category)
        .map((p) => [p.category as string, p.category_name as string]),
    ),
  )

  if (company.isError) {
    return (
      <main className="mx-auto max-w-xl p-8 text-center">
        <h1 className="text-xl font-semibold text-slate-900">{ticker.toUpperCase()}</h1>
        <p className="mt-2 text-slate-500">Not ingested yet.</p>
        <button
          type="button"
          onClick={triggerIngest}
          disabled={ingesting}
          className="mt-4 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {ingesting ? 'Ingesting... (this takes a minute or two)' : 'Ingest this ticker'}
        </button>
      </main>
    )
  }

  return (
    <main className="mx-auto max-w-4xl p-8">
      <h1 className="text-2xl font-semibold text-slate-900">
        {company.data?.name ?? ticker.toUpperCase()}{' '}
        <span className="text-base font-normal text-slate-400">{ticker.toUpperCase()}</span>
      </h1>

      {/* Filters - one row, above the chart, per dataviz skill's
          interaction spec. */}
      <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
        <select
          value={zoneFilter}
          onChange={(e) => setZoneFilter(e.target.value)}
          className="rounded-md border border-slate-300 px-2 py-1"
        >
          <option value="">All zones</option>
          {ZONE_ORDER.map((z) => (
            <option key={z} value={z}>
              {ZONE_COLOR[z].label}
            </option>
          ))}
        </select>

        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="rounded-md border border-slate-300 px-2 py-1"
        >
          <option value="">All categories</option>
          {categories.map(([slug, name]) => (
            <option key={slug} value={slug}>
              {name}
            </option>
          ))}
        </select>

        <label className="flex items-center gap-1.5">
          <input
            type="checkbox"
            checked={includeGeneric}
            onChange={(e) => setIncludeGeneric(e.target.checked)}
          />
          Show generic / boilerplate risks
        </label>
      </div>

      <div className="mt-4 rounded-lg border border-slate-200 p-4">
        {matrix.isLoading && <p className="text-slate-500">Loading matrix...</p>}
        {matrix.data && matrix.data.length === 0 && (
          <p className="text-slate-500">No risks match these filters.</p>
        )}
        {matrix.data && matrix.data.length > 0 && (
          <MatrixChart points={matrix.data} onSelect={setSelectedRiskId} />
        )}
      </div>

      {selectedRiskId !== null && (
        <RiskCard riskId={selectedRiskId} onClose={() => setSelectedRiskId(null)} />
      )}
    </main>
  )
}
