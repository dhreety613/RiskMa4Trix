import type { Zone } from './types'

// Status palette (fixed, never themed) from the dataviz skill's reference
// palette - a 4T zone IS a severity escalation, so the good/warning/
// serious/critical status roles map onto it directly rather than using
// an arbitrary categorical palette.
export const ZONE_COLOR: Record<Zone, { light: string; dark: string; label: string }> = {
  tolerate: { light: '#0ca30c', dark: '#0ca30c', label: 'Tolerate' },
  treat: { light: '#fab219', dark: '#fab219', label: 'Treat' },
  transfer: { light: '#ec835a', dark: '#ec835a', label: 'Transfer' },
  terminate: { light: '#d03b3b', dark: '#d03b3b', label: 'Terminate' },
}

export const ZONE_ORDER: Zone[] = ['tolerate', 'treat', 'transfer', 'terminate']

// Matches backend/app/scoring/zones.py defaults - kept in sync by hand
// for now; worth exposing via /methodology in a later pass so the
// frontend never has to duplicate a backend constant.
export const P_THRESHOLD = 0.2
export const IMPACT_THRESHOLD = 0.5
