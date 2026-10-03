import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../api'

export default function Home() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<{ status: string }>('/health'),
  })

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
    </main>
  )
}
