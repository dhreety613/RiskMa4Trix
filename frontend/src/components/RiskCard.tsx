import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../api'
import type { RiskCard as RiskCardType } from '../types'
import { ZONE_COLOR } from '../zoneColors'

interface Props {
  riskId: number
  onClose: () => void
}

export default function RiskCard({ riskId, onClose }: Props) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['risk', riskId],
    queryFn: () => apiGet<RiskCardType>(`/risks/${riskId}`),
  })

  return (
    <div className="fixed inset-0 z-20 flex justify-end bg-black/20" onClick={onClose}>
      <div
        className="h-full w-full max-w-md overflow-y-auto bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="mb-4 text-sm text-slate-500 hover:text-slate-700"
        >
          Close ✕
        </button>

        {isLoading && <p className="text-slate-500">Loading...</p>}
        {isError && <p className="text-red-600">Could not load this risk.</p>}

        {data && (
          <>
            <div className="flex items-start justify-between gap-2">
              <h2 className="text-lg font-semibold text-slate-900">{data.title}</h2>
            </div>

            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
              {data.zone && (
                <span
                  className="rounded-full px-2 py-0.5 font-medium text-white"
                  style={{ backgroundColor: ZONE_COLOR[data.zone].light }}
                >
                  {ZONE_COLOR[data.zone].label}
                </span>
              )}
              <span className="text-slate-500">{data.category_name ?? 'Unclassified'}</span>
              {data.is_generic && (
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-500">
                  generic / boilerplate
                </span>
              )}
              {data.is_assumption_driven && (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-amber-700">
                  assumption-driven
                </span>
              )}
            </div>

            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-slate-500">Probability (annual)</dt>
                <dd className="font-medium text-slate-900">
                  {data.p_mean !== null ? `${(data.p_mean * 100).toFixed(1)}%` : '—'}
                  {data.p_lo !== null && data.p_hi !== null && (
                    <span className="ml-1 text-xs text-slate-400">
                      (90% CI {(data.p_lo * 100).toFixed(1)}–{(data.p_hi * 100).toFixed(1)}%)
                    </span>
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">Impact</dt>
                <dd className="font-medium text-slate-900">
                  {data.impact_pct_ebitda !== null
                    ? `${(data.impact_pct_ebitda * 100).toFixed(2)}% EBITDA`
                    : '—'}
                  {data.impact_usd !== null && (
                    <span className="ml-1 text-xs text-slate-400">
                      (${(data.impact_usd / 1e6).toFixed(1)}M)
                    </span>
                  )}
                </dd>
              </div>
              <div className="col-span-2">
                <dt className="text-slate-500">Expected loss</dt>
                <dd className="font-medium text-slate-900">
                  {data.expected_loss !== null
                    ? `$${(data.expected_loss / 1e6).toFixed(1)}M`
                    : '—'}
                </dd>
              </div>
            </dl>

            {data.fallbacks.length > 0 && (
              <div className="mt-4 rounded-md bg-amber-50 p-3 text-xs text-amber-800">
                <p className="font-medium">Assumptions used in this score:</p>
                <ul className="mt-1 list-disc pl-4">
                  {data.fallbacks.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="mt-4">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                From the 10-K
              </p>
              <p className="mt-1 text-sm leading-relaxed text-slate-700">{data.text_excerpt}...</p>
            </div>

            <button
              type="button"
              disabled={!data.can_run_monte_carlo}
              title={
                data.can_run_monte_carlo
                  ? 'Run Monte Carlo simulation'
                  : 'Monte Carlo is only available for Treat-zone risks'
              }
              className="mt-6 w-full rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
            >
              Run Monte Carlo {!data.can_run_monte_carlo && '(Treat-zone risks only)'}
            </button>
          </>
        )}
      </div>
    </div>
  )
}
