import {
  CartesianGrid,
  ReferenceArea,
  ReferenceLine,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { MatrixPoint } from '../types'
import { IMPACT_THRESHOLD, P_THRESHOLD, ZONE_COLOR, ZONE_ORDER } from '../zoneColors'

interface Props {
  points: MatrixPoint[]
  onSelect: (riskId: number) => void
}

const QUADRANT_LABEL_STYLE = { fontSize: 11, fontWeight: 600, fill: '#898781' }

export default function MatrixChart({ points, onSelect }: Props) {
  return (
    <div>
      <ScatterChart
        width={720}
        height={440}
        margin={{ top: 16, right: 24, bottom: 24, left: 8 }}
      >
        <CartesianGrid stroke="#e1e0d9" strokeDasharray="0" />

        {/* Quadrant backgrounds - tinted by the zone they represent, so
            the region itself (not just the dots) carries the zone
            identity for anyone orienting on the chart before looking
            at individual points. */}
        <ReferenceArea
          x1={0}
          x2={P_THRESHOLD}
          y1={0}
          y2={IMPACT_THRESHOLD}
          fill={ZONE_COLOR.tolerate.light}
          fillOpacity={0.06}
          label={{ value: 'TOLERATE', position: 'insideBottomLeft', style: QUADRANT_LABEL_STYLE }}
        />
        <ReferenceArea
          x1={P_THRESHOLD}
          x2={1}
          y1={0}
          y2={IMPACT_THRESHOLD}
          fill={ZONE_COLOR.treat.light}
          fillOpacity={0.06}
          label={{ value: 'TREAT', position: 'insideBottomRight', style: QUADRANT_LABEL_STYLE }}
        />
        <ReferenceArea
          x1={0}
          x2={P_THRESHOLD}
          y1={IMPACT_THRESHOLD}
          y2={1}
          fill={ZONE_COLOR.transfer.light}
          fillOpacity={0.06}
          label={{ value: 'TRANSFER', position: 'insideTopLeft', style: QUADRANT_LABEL_STYLE }}
        />
        <ReferenceArea
          x1={P_THRESHOLD}
          x2={1}
          y1={IMPACT_THRESHOLD}
          y2={1}
          fill={ZONE_COLOR.terminate.light}
          fillOpacity={0.08}
          label={{ value: 'TERMINATE', position: 'insideTopRight', style: QUADRANT_LABEL_STYLE }}
        />

        <ReferenceLine x={P_THRESHOLD} stroke="#c3c2b7" strokeWidth={1} />
        <ReferenceLine y={IMPACT_THRESHOLD} stroke="#c3c2b7" strokeWidth={1} />

        <XAxis
          type="number"
          dataKey="p_mean"
          domain={[0, 1]}
          tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
          stroke="#898781"
          label={{ value: 'Probability (annual)', position: 'insideBottom', offset: -8, fill: '#52514e' }}
        />
        <YAxis
          type="number"
          dataKey="impact_norm"
          domain={[0, 1]}
          tickFormatter={(v: number) => `${Math.round(v * 100)}`}
          stroke="#898781"
          label={{ value: 'Impact (normalized)', angle: -90, position: 'insideLeft', fill: '#52514e' }}
        />

        <Tooltip
          cursor={{ strokeDasharray: '3 3' }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null
            const p = payload[0].payload as MatrixPoint
            return (
              <div className="rounded-md border border-slate-200 bg-white p-3 text-sm shadow-lg">
                <div className="font-medium text-slate-900">{p.title}</div>
                <div className="mt-1 text-slate-500">
                  {p.category_name ?? 'Unclassified'} ·{' '}
                  <span style={{ color: ZONE_COLOR[p.zone].light }}>{ZONE_COLOR[p.zone].label}</span>
                </div>
                <div className="mt-1 text-slate-600">
                  P = {(p.p_mean * 100).toFixed(1)}% · Impact ={' '}
                  {(p.impact_pct_ebitda * 100).toFixed(2)}% EBITDA
                </div>
                <div className="text-slate-600">
                  Expected loss ≈ ${(p.expected_loss / 1e6).toFixed(1)}M
                </div>
                {p.is_assumption_driven && (
                  <div className="mt-1 text-amber-600">assumption-driven</div>
                )}
              </div>
            )
          }}
        />

        {ZONE_ORDER.map((zone) => (
          <Scatter
            key={zone}
            name={ZONE_COLOR[zone].label}
            data={points.filter((p) => p.zone === zone)}
            fill={ZONE_COLOR[zone].light}
            stroke="#fcfcfb"
            strokeWidth={1}
            r={6}
            onClick={(p: unknown) => onSelect((p as MatrixPoint).risk_id)}
            cursor="pointer"
          />
        ))}
      </ScatterChart>

      {/* Legend - status color never carries meaning alone, so the
          label is always visible alongside the swatch. */}
      <div className="mt-2 flex gap-5 px-2 text-sm">
        {ZONE_ORDER.map((zone) => (
          <div key={zone} className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: ZONE_COLOR[zone].light }}
            />
            <span className="text-slate-600">{ZONE_COLOR[zone].label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
