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
} from 'lucide-react'
import { NavLink, Outlet, useRouteLoaderData } from 'react-router'

import type { Me } from '../../api/auth'

const NAV = [
  { to: '/admin', label: 'Dashboard', icon: LayoutDashboard, end: true, ownerOnly: false },
  { to: '/admin/quotations', label: 'Quotations', icon: FileText, end: false, ownerOnly: false },
  { to: '/admin/products', label: 'Products', icon: Package, end: false, ownerOnly: false },
  { to: '/admin/materials', label: 'Materials', icon: Boxes, end: false, ownerOnly: false },
  { to: '/admin/labor-rates', label: 'Labour rates', icon: HardHat, end: false, ownerOnly: false },
  { to: '/admin/settings', label: 'Settings', icon: Settings, end: false, ownerOnly: false },
  { to: '/admin/users', label: 'Users', icon: Users, end: false, ownerOnly: false },
  { to: '/admin/sessions', label: 'Active sessions', icon: MonitorSmartphone, end: false, ownerOnly: true },
  { to: '/admin/audit-log', label: 'Audit log', icon: ScrollText, end: false, ownerOnly: false },
]

export function AdminLayout() {
  const me = useRouteLoaderData('root') as Me | null
  const items = NAV.filter((item) => !item.ownerOnly || me?.role === 'super_admin')
  return (
    <div className="flex flex-col gap-6 md:flex-row">
      <nav aria-label="Admin" className="md:w-52 md:shrink-0">
        <ul className="flex gap-1 overflow-x-auto md:flex-col">
          {items.map(({ to, label, icon: Icon, end }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={end}
                className={({ isActive }) =>
                  `flex items-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-sm ${
                    isActive ? 'bg-brand-600 text-white' : 'hover:bg-white'
                  }`
                }
              >
                <Icon className="size-4" aria-hidden />
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <div className="min-w-0 flex-1 space-y-6">
        <Outlet />
      </div>
    </div>
  )
}
