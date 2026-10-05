export type Zone = 'tolerate' | 'treat' | 'transfer' | 'terminate'

export interface MatrixPoint {
  risk_id: number
  title: string
  category: string | null
  category_name: string | null
  p_mean: number
  impact_norm: number
  impact_pct_ebitda: number
  expected_loss: number
  zone: Zone
  is_generic: boolean
  is_assumption_driven: boolean
}

export interface RiskCard {
  risk_id: number
  ticker: string
  title: string
  text_excerpt: string
  category: string | null
  category_name: string | null
  zone: Zone | null
  p_mean: number | null
  p_lo: number | null
  p_hi: number | null
  impact_usd: number | null
  impact_pct_ebitda: number | null
  expected_loss: number | null
  is_generic: boolean
  generic_score: number | null
  is_assumption_driven: boolean
  fallbacks: string[]
  can_run_monte_carlo: boolean
}

export interface IngestAck {
  ticker: string
  status: string
}

export interface Company {
  id: number
  ticker: string
  cik: string
  name: string
  sector: string | null
  sic: string | null
  created_at: string
}

export interface DriftEvent {
  id: number
  from_fiscal_year: number | null
  to_fiscal_year: number
  label: 'new' | 'removed' | 'persisting' | 'reworded'
  similarity: number | null
  title: string
  category_id: number | null
}
