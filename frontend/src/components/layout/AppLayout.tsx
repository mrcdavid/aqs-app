import { FileText, LogOut } from 'lucide-react'
import { Link, Outlet, useNavigate, useRouteLoaderData } from 'react-router'

import { logout, type Me } from '../../api/auth'

export function AppLayout() {
  const me = useRouteLoaderData('root') as Me | null
  const navigate = useNavigate()

  async function onLogout() {
    await logout().catch(() => undefined) // cookie is cleared server-side either way
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-brand-50 text-ink">
      <header className="border-b border-brand-100 bg-white">
        <div className="mx-auto flex max-w-5xl items-center gap-2 px-4 py-3">
          <FileText className="size-5 text-brand-600" aria-hidden />
          <Link to="/" className="font-semibold">
            AQS APP
          </Link>
          {me && (
            <div className="ml-auto flex items-center gap-3 text-sm">
              <span className="hidden text-muted sm:inline">{me.email}</span>
              <button
                type="button"
                onClick={onLogout}
                className="inline-flex items-center gap-1 rounded-lg px-2 py-1 hover:bg-brand-50"
              >
                <LogOut className="size-4" aria-hidden />
                Log out
              </button>
            </div>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}

export function RouteError() {
  return (
    <div className="mx-auto max-w-md p-8 text-center">
      <h1 className="text-xl font-semibold">Something went wrong</h1>
      <p className="mt-2 text-muted">Please refresh the page or try again later.</p>
      <Link to="/" className="mt-4 inline-block text-brand-600 hover:underline">
        Go home
      </Link>
    </div>
  )
}
