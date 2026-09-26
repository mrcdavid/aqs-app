import { Form, Link, useLoaderData, useRouteLoaderData } from 'react-router'

import type { GroupRow } from '../../api/admin'
import type { Me } from '../../api/auth'
import { Card, PageHeader } from '../../components/ui/Card'
import { buttonClass, Field, inputClass } from '../../components/ui/Field'
import { formatDate, formatMoney, trimDecimal } from '../../lib/format'
import { DailyChart } from './DailyChart'
import type { dashboardLoader } from './loaders'

const PRESETS = [7, 30, 90, 365] as const

function isoDaysAgo(to: string, days: number): string {
  const d = new Date(`${to}T12:00:00+08:00`)
  d.setUTCDate(d.getUTCDate() - (days - 1))
  return d.toISOString().slice(0, 10)
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl bg-white p-4 shadow-sm">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  )
}

function GroupTable({ title, rows, currency, empty }: { title: string; rows: GroupRow[]; currency: string; empty: string }) {
  return (
    <Card title={title}>
      {rows.length === 0 ? (
        <p className="text-sm text-muted">{empty}</p>
      ) : (
        <table className="w-full text-left text-sm tabular-nums">
          <thead className="text-muted">
            <tr>
              <th className="py-1 pr-4 font-medium" />
              <th className="py-1 pr-4 text-right font-medium">Requests</th>
              <th className="py-1 pr-4 text-right font-medium">Approved</th>
              <th className="py-1 text-right font-medium">Approved value</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.label} className="border-t border-brand-50">
                <td className="py-1.5 pr-4">{r.label}</td>
                <td className="py-1.5 pr-4 text-right">{r.requested}</td>
                <td className="py-1.5 pr-4 text-right">{r.approved}</td>
                <td className="py-1.5 text-right">{formatMoney(r.approved_value, currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  )
}

export function DashboardPage() {
  const { dashboard: d } = useLoaderData<typeof dashboardLoader>()
  const me = useRouteLoaderData('root') as Me | null
  const money = (v: string) => formatMoney(v, d.currency)
  const spanDays = d.per_day.length

  return (
    <>
      <PageHeader
        title="Dashboard"
        description={`Signed in as ${me?.email ?? ''}. Figures count requests made ${formatDate(d.date_from)} – ${formatDate(d.date_to)}.`}
      />

      <div className="flex flex-wrap items-end gap-3">
        <nav aria-label="Date range" className="flex gap-1">
          {PRESETS.map((days) => (
            <Link
              key={days}
              to={`/admin?date_from=${isoDaysAgo(d.date_to, days)}&date_to=${d.date_to}`}
              className={`rounded-lg px-3 py-1.5 text-sm ${
                spanDays === days ? 'bg-brand-600 text-white' : 'bg-white hover:bg-brand-100'
              }`}
            >
              {days === 365 ? '1 year' : `${days} days`}
            </Link>
          ))}
        </nav>
        <Form method="get" className="flex flex-wrap items-end gap-2">
          <Field label="From" htmlFor="d-from">
            <input id="d-from" type="date" name="date_from" defaultValue={d.date_from} className={inputClass} />
          </Field>
          <Field label="To" htmlFor="d-to">
            <input id="d-to" type="date" name="date_to" defaultValue={d.date_to} className={inputClass} />
          </Field>
          <button type="submit" className={buttonClass}>
            Apply
          </button>
        </Form>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Requests" value={String(d.requested)} hint={`${d.pending} still pending`} />
        <Stat label="Approved value" value={money(d.approved_value)} hint={`${d.approved} approved quotations`} />
        <Stat
          label="Approval rate"
          value={d.approval_rate === null ? '—' : `${trimDecimal(d.approval_rate)}%`}
          hint={`${d.approved} approved, ${d.rejected} rejected`}
        />
        <Link to="/admin/quotations?status=pending" className="rounded-xl hover:ring-2 hover:ring-brand-100">
          <Stat label="Waiting for review" value={String(d.pending_now)} hint="All pending requests →" />
        </Link>
      </div>

      <Card>
        <DailyChart days={d.per_day} currency={d.currency} />
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <GroupTable title="By province" rows={d.by_location} currency={d.currency} empty="No requests in this period." />
        <GroupTable title="By product" rows={d.by_product} currency={d.currency} empty="No requests in this period." />
      </div>

      <Card title="Largest approved projects">
        {d.top_projects.length === 0 ? (
          <p className="text-sm text-muted">No approved quotations in this period.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm tabular-nums">
              <thead className="text-muted">
                <tr>
                  <th className="py-1 pr-4 font-medium">Quotation</th>
                  <th className="py-1 pr-4 font-medium">Customer</th>
                  <th className="py-1 pr-4 font-medium">Product</th>
                  <th className="py-1 text-right font-medium">Total</th>
                </tr>
              </thead>
              <tbody>
                {d.top_projects.map((p) => (
                  <tr key={p.id} className="border-t border-brand-50">
                    <td className="py-1.5 pr-4">
                      <Link to={`/admin/quotations/${p.id}`} className="font-mono text-xs text-brand-600 hover:underline">
                        {p.number}
                      </Link>
                    </td>
                    <td className="py-1.5 pr-4">
                      {p.customer_name} <span className="text-muted">· {p.city}</span>
                    </td>
                    <td className="py-1.5 pr-4">{p.product_name}</td>
                    <td className="py-1.5 text-right">{money(p.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
