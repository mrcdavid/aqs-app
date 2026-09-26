import { useState } from 'react'

import type { DayPoint } from '../../api/admin'
import { formatDate, formatMoney } from '../../lib/format'

/** Round up to a readable axis maximum: 1, 2, 5, 10, 20, 50 ... */
function niceMax(value: number): number {
  if (value <= 4) return 4
  const pow = 10 ** Math.floor(Math.log10(value))
  for (const step of [1, 2, 5, 10]) {
    if (value <= step * pow) return step * pow
  }
  return 10 * pow
}

/**
 * Quotation requests per day. One series (brand colour, no legend: the title names it),
 * thin bars with 2px gaps and rounded tops, recessive grid, hover/focus tooltip per bar,
 * and a table view for screen readers and exact numbers.
 */
export function DailyChart({ days, currency }: { days: DayPoint[]; currency: string }) {
  const [active, setActive] = useState<number | null>(null)
  const max = niceMax(Math.max(0, ...days.map((d) => d.requested)))
  const ticks = [max, max / 2, 0]
  const point = active === null ? null : days[active]
  const labelIdx = new Set([0, Math.floor((days.length - 1) / 2), days.length - 1])

  return (
    <figure className="space-y-3">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-semibold">Quotation requests per day</span>
        <span className="text-sm text-muted" aria-live="polite">
          {point
            ? `${formatDate(point.day)}: ${point.requested} requested, ${point.approved} approved (${formatMoney(point.approved_value, currency)})`
            : 'Hover or focus a bar for details'}
        </span>
      </figcaption>

      <div className="flex gap-2">
        <div className="flex h-48 flex-col justify-between text-right text-xs tabular-nums text-muted" aria-hidden>
          {ticks.map((t) => (
            <span key={t} className="-translate-y-1/2 first:translate-y-0 last:translate-y-0">
              {t}
            </span>
          ))}
        </div>
        <div className="relative h-48 flex-1">
          {/* recessive grid */}
          {ticks.map((t) => (
            <div
              key={t}
              className="absolute inset-x-0 border-t border-line"
              style={{ bottom: `${(t / max) * 100}%` }}
              aria-hidden
            />
          ))}
          <div
            className="absolute inset-0 flex items-end gap-[2px]"
            role="group"
            aria-label="Requests per day"
            onMouseLeave={() => setActive(null)}
          >
            {days.map((d, i) => (
              <button
                key={d.day}
                type="button"
                className="group relative flex h-full flex-1 items-end focus:outline-none"
                aria-label={`${formatDate(d.day)}: ${d.requested} requested, ${d.approved} approved`}
                onMouseEnter={() => setActive(i)}
                onFocus={() => setActive(i)}
                onBlur={() => setActive(null)}
              >
                <span
                  className={`w-full rounded-t-[4px] ${
                    active === i ? 'bg-brand-700' : 'bg-brand-600'
                  } group-focus-visible:ring-2 group-focus-visible:ring-brand-500`}
                  style={{ height: d.requested ? `${(d.requested / max) * 100}%` : '0' }}
                />
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="relative ml-8 h-4 text-xs text-muted" aria-hidden>
        {days.map((d, i) =>
          labelIdx.has(i) ? (
            <span
              key={d.day}
              className="absolute whitespace-nowrap"
              style={{
                left: `${((i + 0.5) / days.length) * 100}%`,
                transform:
                  i === 0 ? 'translateX(0)' : i === days.length - 1 ? 'translateX(-100%)' : 'translateX(-50%)',
              }}
            >
              {formatDate(d.day)}
            </span>
          ) : null,
        )}
      </div>

      <details className="text-sm">
        <summary className="cursor-pointer font-medium text-brand">Show as table</summary>
        <div className="mt-2 max-h-64 overflow-auto">
          <table className="w-full text-left tabular-nums">
            <thead className="text-muted">
              <tr>
                <th className="py-1 pr-4 font-medium">Day</th>
                <th className="py-1 pr-4 text-right font-medium">Requested</th>
                <th className="py-1 pr-4 text-right font-medium">Approved</th>
                <th className="py-1 text-right font-medium">Approved value</th>
              </tr>
            </thead>
            <tbody>
              {days.map((d) => (
                <tr key={d.day} className="border-t border-line">
                  <td className="py-1 pr-4">{formatDate(d.day)}</td>
                  <td className="py-1 pr-4 text-right">{d.requested}</td>
                  <td className="py-1 pr-4 text-right">{d.approved}</td>
                  <td className="py-1 text-right">{formatMoney(d.approved_value, currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  )
}
