import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiGet } from '../api'
import type { Company } from '../types'

export default function Home() {
  const navigate = useNavigate()
  const [ticker, setTicker] = useState('')

  const health = useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<{ status: string }>('/health'),
  })

  const companies = useQuery({
    queryKey: ['companies'],
    queryFn: () => apiGet<Company[]>('/companies'),
  })

  const goToTicker = (e: React.FormEvent) => {
    e.preventDefault()
    if (ticker.trim()) navigate(`/company/${ticker.trim().toUpperCase()}`)
  }

  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-3xl font-semibold text-slate-900">Ma3Trix</h1>
      <p className="mt-2 text-slate-600">
        Finance risk platform - 10-K risk extraction, drift tracking, and a 4T
        risk matrix with Monte Carlo on Treat-zone risks.
      </p>

      <div className="mt-6 rounded-lg border border-slate-200 p-4">
        <span className="font-medium">API: </span>
        {health.isLoading && <span className="text-slate-500">checking...</span>}
        {health.isError && <span className="text-red-600">unreachable</span>}
        {health.data && <span className="text-emerald-600">{health.data.status}</span>}
      </div>

      <form onSubmit={goToTicker} className="mt-6 flex gap-2">
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="Ticker (e.g. AAPL)"
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm uppercase"
        />
        <button
          type="submit"
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white"
        >
          View matrix
        </button>
      </form>

      {companies.data && companies.data.length > 0 && (
        <div className="mt-6">
          <p className="text-sm font-medium text-slate-500">Already ingested</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {companies.data.map((c) => (
              <Link
                key={c.id}
                to={`/company/${c.ticker}`}
                className="rounded-full border border-slate-200 px-3 py-1 text-sm text-slate-700 hover:border-slate-400"
              >
                {c.ticker}
              </Link>
            ))}
          </div>
        </div>
      )}
    </main>
  )
}
