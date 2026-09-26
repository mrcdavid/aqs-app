import { ArrowRight, FileCheck2, LayoutDashboard, MousePointerClick, Ruler, ShieldCheck } from 'lucide-react'
import { useRouteLoaderData } from 'react-router'

import { STAFF_ROLES, type Me } from '../../api/auth'
import { ButtonLink } from '../../components/ui/Button'

const STEPS = [
  { icon: MousePointerClick, title: 'Choose a product', text: 'Sliding windows, sliding doors, window grills and more.' },
  { icon: Ruler, title: 'Enter the size', text: 'Width and height in centimetres or inches.' },
  { icon: FileCheck2, title: 'Get your quotation', text: 'An instant estimate PDF, then the official quote once approved.' },
]

export function HomePage() {
  const me = useRouteLoaderData('root') as Me | null
  const staff = me && STAFF_ROLES.includes(me.role)
  const cta = !me ? '/login' : staff ? '/admin' : me.has_profile ? '/app/quotations/new' : '/app/profile'

  return (
    <div className="space-y-10">
      <section className="bg-hero relative overflow-hidden rounded-3xl border border-line bg-surface px-6 py-12 text-center shadow-card sm:px-12 sm:py-16">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-soft px-3 py-1 text-xs font-medium text-brand-soft-ink">
          <ShieldCheck className="size-3.5" aria-hidden /> For UP students, staff and offices
        </span>
        <h1 className="mx-auto mt-5 max-w-2xl text-3xl font-bold tracking-tight sm:text-5xl">
          Glass & aluminum quotations, <span className="text-brand-gradient">in minutes</span>
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-muted sm:text-lg">
          Get an instant, itemised estimate for sliding windows, sliding doors and window grills — then an official
          quotation you can print.
        </p>
        <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
          <ButtonLink to={cta} icon={staff ? LayoutDashboard : ArrowRight} className="h-12 px-6 text-base">
            {staff ? 'Open admin' : 'Get a quotation'}
          </ButtonLink>
          {!me && (
            <ButtonLink to="/staff/login" variant="secondary" className="h-12 px-6 text-base">
              Staff login
            </ButtonLink>
          )}
        </div>
      </section>

      <section aria-labelledby="how" className="space-y-4">
        <h2 id="how" className="text-center text-sm font-semibold tracking-wide text-muted uppercase">
          How it works
        </h2>
        <ol className="grid gap-4 sm:grid-cols-3">
          {STEPS.map(({ icon: Icon, title, text }, i) => (
            <li key={title} className="rounded-2xl border border-line bg-surface p-5 shadow-card">
              <div className="flex items-center gap-3">
                <span className="bg-brand-gradient grid size-10 place-items-center rounded-xl text-white">
                  <Icon className="size-5" aria-hidden />
                </span>
                <span className="text-sm font-semibold text-muted">Step {i + 1}</span>
              </div>
              <h3 className="mt-4 font-semibold">{title}</h3>
              <p className="mt-1 text-sm text-muted">{text}</p>
            </li>
          ))}
        </ol>
      </section>
    </div>
  )
}
