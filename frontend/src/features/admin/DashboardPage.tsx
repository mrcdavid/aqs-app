import {
  ArrowRight,
  BadgeCheck,
  CalendarRange,
  Clock,
  FileText,
  LayoutDashboard,
  MapPin,
  Package,
  Trophy,
  Wallet,
  type LucideIcon,
} from 'lucide-react'
import { Form, Link, useLoaderData, useRouteLoaderData } from 'react-router'

import type { GroupRow } from '../../api/admin'
import type { Me } from '../../api/auth'
import { Button } from '../../components/ui/Button'
import { Card, EmptyState, PageHeader } from '../../components/ui/Card'
import { Field, inputClass } from '../../components/ui/Field'
import { formatDate, formatMoney, trimDecimal } from '../../lib/format'
import { DailyChart } from './DailyChart'
import type { dashboardLoader } from './loaders'

const PRESETS = [7, 30, 90, 365] as const

function isoDaysAgo(to: string, days: number): string {
  const d = new Date(`${to}T12:00:00+08:00`)
  d.setUTCDate(d.getUTCDate() - (days - 1))
  return d.toISOString().slice(0, 10)
}

function Stat({ label, value, hint, icon: Icon, featured = false }: { label: string; value: string; hint?: string; icon: LucideIcon; featured?: boolean }) {
  return (
    <div
      className={`h-full rounded-2xl p-4 sm:p-5 ${
        featured
          ? 'bg-brand-gradient text-white shadow-lg shadow-indigo-500/25'
          : 'border border-line bg-surface shadow-card'
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <p className={`text-sm ${featured ? 'text-white/80' : 'text-muted'}`}>{label}</p>
        <span className={`grid size-9 place-items-center rounded-xl ${featured ? 'bg-white/15' : 'bg-brand-soft text-brand'}`}>
          <Icon className="size-[18px]" aria-hidden />
        </span>
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight tabular-nums sm:text-3xl">{value}</p>
      {hint && <p className={`mt-1 text-xs ${featured ? 'text-white/80' : 'text-muted'}`}>{hint}</p>}
    </div>
  )
}

function GroupTable({ title, icon, rows, currency }: { title: string; icon: LucideIcon; rows: GroupRow[]; currency: string }) {
  const max = Math.max(1, ...rows.map((r) => r.requested))
  return (
    <Card title={title} icon={icon}>
      {rows.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted">No requests in this period.</p>
      ) : (
        <ul className="space-y-3">
          {rows.map((r) => (
            <li key={r.label}>
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="truncate font-medium">{r.label}</span>
                <span className="shrink-0 tabular-nums">{formatMoney(r.approved_value, currency)}</span>
              </div>
              <div className="mt-1 flex items-center gap-3">
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-2" aria-hidden>
                  <div className="bg-brand-gradient h-full rounded-full" style={{ width: `${(r.requested / max) * 100}%` }} />
                </div>
                <span className="w-32 shrink-0 text-right text-xs text-muted tabular-nums">
                  {r.requested} requests · {r.approved} approved
                </span>
              </div>
            </li>
          ))}
        </ul>
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
        icon={LayoutDashboard}
        description={`Welcome back, ${me?.email ?? ''}. Figures count requests made ${formatDate(d.date_from)} – ${formatDate(d.date_to)}.`}
      />

      <Card>
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <nav aria-label="Date range" className="inline-flex self-start rounded-xl bg-surface-2 p-1">
            {PRESETS.map((days) => (
              <Link
                key={days}
                to={`/admin?date_from=${isoDaysAgo(d.date_to, days)}&date_to=${d.date_to}`}
                aria-current={spanDays === days ? 'true' : undefined}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium whitespace-nowrap transition ${
                  spanDays === days ? 'bg-surface text-ink shadow-sm' : 'text-muted hover:text-ink'
                }`}
              >
                {days === 365 ? '1 year' : `${days} days`}
              </Link>
            ))}
          </nav>
          <Form method="get" className="grid grid-cols-2 items-end gap-2 sm:flex">
            <Field label="From" htmlFor="d-from">
              <input id="d-from" type="date" name="date_from" defaultValue={d.date_from} className={inputClass} />
            </Field>
            <Field label="To" htmlFor="d-to">
              <input id="d-to" type="date" name="date_to" defaultValue={d.date_to} className={inputClass} />
            </Field>
            <Button type="submit" variant="secondary" icon={CalendarRange} className="col-span-2">
              Apply
            </Button>
          </Form>
        </div>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat featured icon={Wallet} label="Approved value" value={money(d.approved_value)} hint={`${d.approved} approved quotation${d.approved === 1 ? '' : 's'}`} />
        <Stat icon={FileText} label="Requests" value={String(d.requested)} hint={`${d.pending} still pending`} />
        <Stat
          icon={BadgeCheck}
          label="Approval rate"
          value={d.approval_rate === null ? '—' : `${trimDecimal(d.approval_rate)}%`}
          hint={`${d.approved} approved, ${d.rejected} rejected`}
        />
        <Link to="/admin/quotations?status=pending" className="group rounded-2xl">
          <Stat icon={Clock} label="Waiting for review" value={String(d.pending_now)} hint="Open the review queue →" />
        </Link>
      </div>

      <Card>
        <DailyChart days={d.per_day} currency={d.currency} />
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <GroupTable title="By province" icon={MapPin} rows={d.by_location} currency={d.currency} />
        <GroupTable title="By product" icon={Package} rows={d.by_product} currency={d.currency} />
      </div>

      <Card title="Largest approved projects" icon={Trophy}>
        {d.top_projects.length === 0 ? (
          <EmptyState icon={Trophy} title="No approved quotations in this period" />
        ) : (
          <ul className="-my-2 divide-y divide-line">
            {d.top_projects.map((p, i) => (
              <li key={p.id}>
                <Link to={`/admin/quotations/${p.id}`} className="group -mx-2 flex items-center gap-3 rounded-xl px-2 py-3 hover:bg-surface-2/70">
                  <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-surface-2 text-sm font-semibold text-muted tabular-nums">
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">
                      {p.customer_name} <span className="font-normal text-muted">· {p.city}</span>
                    </p>
                    <p className="truncate text-xs text-muted">
                      <span className="font-mono">{p.number}</span> · {p.product_name}
                    </p>
                  </div>
                  <span className="font-semibold tabular-nums">{money(p.total)}</span>
                  <ArrowRight className="hidden size-4 text-muted transition group-hover:translate-x-0.5 sm:block" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  )
}
