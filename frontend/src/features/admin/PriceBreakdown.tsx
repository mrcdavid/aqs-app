import { PackagePlus } from 'lucide-react'

import type { Basis, PriceLine, PricePreview } from '../../api/admin'
import { Badge } from '../../components/ui/Badge'
import { barLabel, BASIS_LABEL, QTY_UNIT, trimDecimal, UNIT_LABEL } from '../../lib/format'

// Staff only: a price breakdown from the admin preview or an item's frozen snapshot.
// Quotations priced before v2 (pricing_method null) used metres and added VAT on top.

const METRIC_BASIS_LABEL: Record<Basis, string> = {
  area: 'Area (m²)',
  perimeter: 'Perimeter (m)',
  width: 'Width (m)',
  height: 'Height (m)',
  fixed: 'Fixed count',
}

type Money = (value: string) => string

/** "48 × 48 in · 16 sq ft · qty 2" (or mm for quotations priced before v2). */
export function BreakdownSize({ b }: { b: PricePreview }) {
  if (b.pricing_method && b.width_in && b.height_in && b.area_sqft) {
    return `${trimDecimal(b.width_in)} × ${trimDecimal(b.height_in)} in · ${trimDecimal(b.area_sqft)} sq ft · qty ${b.quantity}`
  }
  return `${b.width_mm} × ${b.height_mm} mm · qty ${b.quantity}`
}

function measuredAt(l: PriceLine, b: PricePreview): string | null {
  if (l.width_in && l.height_in && b.width_in && b.height_in) {
    const smaller = Number(l.width_in) !== Number(b.width_in) || Number(l.height_in) !== Number(b.height_in)
    return smaller ? `at ${trimDecimal(l.width_in)} × ${trimDecimal(l.height_in)} in` : null
  }
  if (l.width_mm != null && l.height_mm != null && (l.width_mm !== b.width_mm || l.height_mm !== b.height_mm)) {
    return `at ${l.width_mm} × ${l.height_mm} mm`
  }
  return null
}

function quantity(l: PriceLine): string {
  const qty = trimDecimal(l.quantity)
  if (l.unit === 'bar') {
    const bars = `${qty} × ${barLabel(l.stock_length, l.stock_length_unit)}`
    return l.needed && Number(l.needed) !== Number(l.quantity) ? `${bars} (needs ${trimDecimal(l.needed)})` : bars
  }
  return `${qty} ${QTY_UNIT[l.unit]}`
}

export function BreakdownLines({ b, money, codes = false }: { b: PricePreview; money: Money; codes?: boolean }) {
  if (b.lines.length === 0) {
    return <p className="rounded-xl border border-dashed border-line p-3 text-sm text-muted">No cost lines (no cost guide yet).</p>
  }
  const basisLabel = b.pricing_method ? BASIS_LABEL : METRIC_BASIS_LABEL
  return (
    <div className="overflow-x-auto rounded-xl border border-line">
      <table className="w-full text-left text-sm tabular-nums">
        <thead className="bg-surface-2 text-xs tracking-wide text-muted uppercase">
          <tr>
            <th className="px-3 py-2 font-medium">Line</th>
            <th className="px-3 py-2 font-medium">Measured by</th>
            <th className="px-3 py-2 text-right font-medium">Qty</th>
            <th className="px-3 py-2 text-right font-medium">Price</th>
            <th className="px-3 py-2 text-right font-medium">Cost</th>
          </tr>
        </thead>
        <tbody>
          {b.lines.map((l, i) => {
            const at = measuredAt(l, b)
            return (
              <tr key={i} className="border-t border-line">
                <td className="px-3 py-2">
                  {l.label || l.name} {codes && <span className="font-mono text-xs text-muted">{l.code}</span>}{' '}
                  {l.option && (
                    <Badge tone="brand" icon={PackagePlus}>
                      {l.option}
                    </Badge>
                  )}
                </td>
                <td className="px-3 py-2 text-muted">
                  {basisLabel[l.basis]}
                  {at && <span className="block text-xs">{at}</span>}
                </td>
                <td className="px-3 py-2 text-right whitespace-nowrap">{quantity(l)}</td>
                <td className="px-3 py-2 text-right whitespace-nowrap">
                  {money(l.unit_price)}{' '}
                  <span className="text-muted">
                    {l.unit === 'bar' ? `per ${barLabel(l.stock_length, l.stock_length_unit)}` : UNIT_LABEL[l.unit]}
                  </span>
                </td>
                <td className="px-3 py-2 text-right">{money(l.cost)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/** The sums: how the price was reached, the amount, then VAT included, cost and margin. */
export function BreakdownSums({
  b,
  money,
  amountLabel,
  amount,
}: {
  b: PricePreview
  money: Money
  amountLabel: string
  amount: string
}) {
  const step = trimDecimal(b.rounding_step)
  const rounding: [string, string][] = Number(b.rounding_step) > 0 ? [[`Rounded up to the next ${step}`, b.rounding]] : []
  let steps: [string, string][]
  let after: [string, string][] = []
  if (b.pricing_method === 'per_sqft') {
    const area = trimDecimal(b.area_sqft ?? '0')
    steps = [
      ...b.rates.map((r): [string, string] => [`${r.name} (per sq ft)`, r.rate_per_sqft]),
      [`Price per piece (${area} sq ft × ${money(b.rate_per_sqft ?? '0')})`, b.unit_price],
      [`Subtotal (× ${b.quantity})`, b.net],
      ...rounding,
    ]
  } else if (b.pricing_method === 'computed') {
    steps = [
      ['Cost per piece', b.unit_subtotal],
      [`Price per piece (+${trimDecimal(b.markup_percent)}% markup)`, b.unit_price],
      [`Subtotal (× ${b.quantity})`, b.net],
      ...rounding,
    ]
  } else {
    // Priced before v2: VAT was added on top.
    steps = [
      ['Cost per piece', b.unit_subtotal],
      [`Customer unit price (+${trimDecimal(b.markup_percent)}% markup)`, b.unit_price],
      [`Subtotal (× ${b.quantity})`, b.net],
      [`VAT ${trimDecimal(b.vat_percent)}% (added)`, b.vat],
      ['Total incl. VAT', b.total],
      ...rounding,
    ]
  }
  if (b.pricing_method) {
    after = [
      [`VAT ${trimDecimal(b.vat_percent)}% included`, b.vat_included ?? '0'],
      [b.pricing_method === 'per_sqft' ? `Cost guide (× ${b.quantity})` : `Cost (× ${b.quantity})`, b.subtotal],
    ]
  }
  const margin = b.margin != null ? Number(b.margin) : null
  const marginPct = margin !== null && Number(amount) > 0 ? ((margin / Number(amount)) * 100).toFixed(1) : null

  return (
    <dl className="ml-auto max-w-sm space-y-1.5 text-sm tabular-nums">
      {steps.map(([label, value]) => (
        <div key={label} className="flex justify-between gap-4">
          <dt className="text-muted">{label}</dt>
          <dd>{money(value)}</dd>
        </div>
      ))}
      <div className="bg-brand-gradient mt-2 flex justify-between gap-4 rounded-xl px-4 py-3 text-base font-semibold text-white">
        <dt>{amountLabel}</dt>
        <dd>{money(amount)}</dd>
      </div>
      {after.length > 0 && (
        <div className="space-y-1.5 pt-1">
          {after.map(([label, value]) => (
            <div key={label} className="flex justify-between gap-4">
              <dt className="text-muted">{label}</dt>
              <dd>{money(value)}</dd>
            </div>
          ))}
          {b.margin != null && (
            <div className={`flex justify-between gap-4 font-medium ${margin !== null && margin < 0 ? 'text-danger' : 'text-success'}`}>
              <dt>Margin{marginPct !== null && ` (${marginPct}%)`}</dt>
              <dd>{money(b.margin)}</dd>
            </div>
          )}
        </div>
      )}
    </dl>
  )
}
