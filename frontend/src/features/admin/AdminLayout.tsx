import {
  Boxes,
  FileText,
  HardHat,
  LayoutDashboard,
  MonitorSmartphone,
  Package,
  ScrollText,
  Settings,
  Users,
  X,
  type LucideIcon,
} from 'lucide-react'
import { useEffect } from 'react'
import { NavLink, Outlet, useLocation, useRouteLoaderData } from 'react-router'

import type { Me } from '../../api/auth'
import { Logo } from '../../components/layout/AppLayout'
import { useUiStore } from '../../stores/ui'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  end?: boolean
  ownerOnly?: boolean
}

const GROUPS: { title: string; items: NavItem[] }[] = [
  {
    title: 'Overview',
    items: [
      { to: '/admin', label: 'Dashboard', icon: LayoutDashboard, end: true },
      { to: '/admin/quotations', label: 'Quotations', icon: FileText },
    ],
  },
  {
    title: 'Catalogue',
    items: [
      { to: '/admin/products', label: 'Products', icon: Package },
      { to: '/admin/materials', label: 'Materials', icon: Boxes },
      { to: '/admin/labor-rates', label: 'Labour rates', icon: HardHat },
    ],
  },
  {
    title: 'Administration',
    items: [
      { to: '/admin/users', label: 'Users', icon: Users },
      { to: '/admin/sessions', label: 'Active sessions', icon: MonitorSmartphone, ownerOnly: true },
      { to: '/admin/audit-log', label: 'Audit log', icon: ScrollText },
      { to: '/admin/settings', label: 'Settings', icon: Settings },
    ],
  },
]

function Nav({ isOwner }: { isOwner: boolean }) {
  return (
    <nav aria-label="Admin" className="space-y-6">
      {GROUPS.map((group) => (
        <div key={group.title}>
          <p className="mb-2 px-3 text-xs font-semibold tracking-wide text-muted uppercase">{group.title}</p>
          <ul className="space-y-1">
            {group.items
              .filter((item) => !item.ownerOnly || isOwner)
              .map(({ to, label, icon: Icon, end }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    end={end}
                    className={({ isActive }) =>
                      `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                        isActive
                          ? 'bg-brand-gradient text-white shadow-sm shadow-indigo-500/25'
                          : 'text-muted hover:bg-surface-2 hover:text-ink'
                      }`
                    }
                  >
                    <Icon className="size-[18px]" aria-hidden />
                    {label}
                  </NavLink>
                </li>
              ))}
          </ul>
        </div>
      ))}
    </nav>
  )
}

export function AdminLayout() {
  const me = useRouteLoaderData('root') as Me | null
  const isOwner = me?.role === 'super_admin'
  const open = useUiStore((s) => s.sidebarOpen)
  const setOpen = useUiStore((s) => s.setSidebarOpen)
  const { pathname, search } = useLocation()

  // Close the phone drawer after navigating, and on Esc.
  useEffect(() => setOpen(false), [pathname, search, setOpen])
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, setOpen])

  return (
    <div className="flex gap-8">
      <aside className="hidden w-60 shrink-0 md:block">
        <div className="sticky top-24">
          <Nav isOwner={isOwner} />
        </div>
      </aside>

      {open && (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label="Admin menu">
          <button
            type="button"
            aria-label="Close menu"
            className="absolute inset-0 bg-[var(--backdrop)] backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 flex w-72 max-w-[85vw] animate-slide-in flex-col bg-surface shadow-2xl">
            <div className="flex h-16 items-center justify-between border-b border-line px-4">
              <Logo />
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close menu"
                className="grid size-10 place-items-center rounded-xl text-muted hover:bg-surface-2"
              >
                <X className="size-5" aria-hidden />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              <Nav isOwner={isOwner} />
            </div>
          </div>
        </div>
      )}

      <div className="min-w-0 flex-1 space-y-6">
        <Outlet />
      </div>
    </div>
  )
}
