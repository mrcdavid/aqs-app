import {
  AppWindow,
  ChevronDown,
  FilePlus2,
  FileText,
  Home,
  LayoutDashboard,
  LogOut,
  Menu,
  RotateCcw,
  UserRound,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate, useRouteLoaderData } from 'react-router'

import { logout, STAFF_ROLES, type Me } from '../../api/auth'
import { useUiStore } from '../../stores/ui'
import { Button, ButtonLink } from '../ui/Button'
import { ConfirmHost, Toaster } from '../ui/Feedback'
import { TopProgressBar } from '../ui/Spinner'
import { ThemeToggle } from '../ui/ThemeToggle'

const CUSTOMER_NAV = [
  { to: '/app/quotations', label: 'My quotations', icon: FileText, end: true },
  { to: '/app/quotations/new', label: 'New quotation', icon: FilePlus2, end: true },
  { to: '/app/profile', label: 'Profile', icon: UserRound, end: true },
]

const ROLE_LABEL = { user: 'Customer', admin: 'Admin', super_admin: 'Super admin' } as const

export function Logo() {
  return (
    <Link to="/" aria-label="AQS APP home" className="flex items-center gap-2 rounded-lg font-semibold tracking-tight">
      <span className="bg-brand-gradient grid size-8 place-items-center rounded-xl text-white shadow-sm shadow-indigo-500/30">
        <AppWindow className="size-[18px]" aria-hidden />
      </span>
      <span className="text-lg">
        <span className="text-brand-gradient">AQS</span> APP
      </span>
    </Link>
  )
}

function UserMenu({ me }: { me: Me }) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false)
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  async function onLogout() {
    setBusy(true)
    await logout().catch(() => undefined) // cookie is cleared server-side either way
    setBusy(false)
    navigate(STAFF_ROLES.includes(me.role) ? '/staff/login' : '/login', { replace: true })
  }

  const initials = me.email.slice(0, 2).toUpperCase()
  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={`Account menu for ${me.email}`}
        className="flex items-center gap-2 rounded-xl py-1 pr-2 pl-1 hover:bg-surface-2"
      >
        <span className="bg-brand-gradient grid size-8 place-items-center rounded-full text-xs font-semibold text-white">
          {initials}
        </span>
        <span className="hidden max-w-44 truncate text-sm md:inline">{me.email}</span>
        <ChevronDown className="size-4 text-muted" aria-hidden />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-2 w-72 animate-fade-up rounded-2xl border border-line bg-surface p-2 shadow-card"
        >
          <div className="px-3 py-2">
            <p className="truncate text-sm font-medium">{me.email}</p>
            <p className="text-xs text-muted">{ROLE_LABEL[me.role]}</p>
          </div>
          <div className="px-3 py-2">
            <p className="mb-1.5 text-xs text-muted">Theme</p>
            <ThemeToggle />
          </div>
          <div className="my-1 border-t border-line" />
          {me.role === 'user' && (
            <Link
              role="menuitem"
              to="/app/profile"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-surface-2"
            >
              <UserRound className="size-4 text-muted" aria-hidden /> My profile
            </Link>
          )}
          <button
            role="menuitem"
            type="button"
            onClick={onLogout}
            disabled={busy}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-danger hover:bg-danger-soft"
          >
            <LogOut className="size-4" aria-hidden /> {busy ? 'Signing out…' : 'Log out'}
          </button>
        </div>
      )}
    </div>
  )
}

export function AppLayout() {
  const me = useRouteLoaderData('root') as Me | null
  const { pathname } = useLocation()
  const toggleSidebar = useUiStore((s) => s.toggleSidebar)
  const inAdmin = pathname.startsWith('/admin')
  const isCustomer = me?.role === 'user'

  return (
    <div className="min-h-dvh bg-canvas text-ink">
      <TopProgressBar />
      <header className="sticky top-0 z-30 border-b border-line bg-surface/85 backdrop-blur-md">
        <div className={`mx-auto flex h-16 items-center gap-3 px-4 ${inAdmin ? 'max-w-7xl' : 'max-w-5xl'}`}>
          {inAdmin && (
            <button
              type="button"
              onClick={toggleSidebar}
              aria-label="Open menu"
              className="-ml-2 grid size-10 place-items-center rounded-xl text-muted hover:bg-surface-2 md:hidden"
            >
              <Menu className="size-5" aria-hidden />
            </button>
          )}
          <Logo />

          {isCustomer && (
            <nav aria-label="Main" className="ml-6 hidden items-center gap-1 sm:flex">
              {CUSTOMER_NAV.map(({ to, label, icon: Icon, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    `flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition ${
                      isActive ? 'bg-brand-soft text-brand-soft-ink' : 'text-muted hover:bg-surface-2 hover:text-ink'
                    }`
                  }
                >
                  <Icon className="size-4" aria-hidden />
                  {label}
                </NavLink>
              ))}
            </nav>
          )}

          <div className="ml-auto flex items-center gap-2">
            {me && !isCustomer && !inAdmin && (
              <ButtonLink to="/admin" variant="secondary" size="sm" icon={LayoutDashboard}>
                Admin
              </ButtonLink>
            )}
            {me ? <UserMenu me={me} /> : <ThemeToggle compact />}
          </div>
        </div>
      </header>

      <main className={`mx-auto px-4 py-6 sm:py-8 ${inAdmin ? 'max-w-7xl' : 'max-w-5xl'} ${isCustomer ? 'pb-28 sm:pb-8' : ''}`}>
        <Outlet />
      </main>

      {/* Phone tab bar for customers */}
      {isCustomer && (
        <nav
          aria-label="Main"
          className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-3 border-t border-line bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur sm:hidden"
        >
          {CUSTOMER_NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex flex-col items-center gap-1 py-2.5 text-[11px] font-medium ${isActive ? 'text-brand' : 'text-muted'}`
              }
            >
              <Icon className="size-5" aria-hidden />
              {label}
            </NavLink>
          ))}
        </nav>
      )}

      <Toaster />
      <ConfirmHost />
    </div>
  )
}

export function RouteError() {
  const navigate = useNavigate()
  return (
    <div className="grid min-h-dvh place-items-center bg-canvas p-6 text-ink">
      <div className="max-w-md text-center">
        <p className="text-brand-gradient text-5xl font-bold">Oops</p>
        <h1 className="mt-3 text-xl font-semibold">Something went wrong</h1>
        <p className="mt-2 text-sm text-muted">Please try again. If it keeps happening, sign out and back in.</p>
        <div className="mt-6 flex justify-center gap-2">
          <Button variant="secondary" icon={RotateCcw} onClick={() => navigate(0)}>
            Try again
          </Button>
          <ButtonLink to="/" icon={Home}>
            Go home
          </ButtonLink>
        </div>
      </div>
    </div>
  )
}
