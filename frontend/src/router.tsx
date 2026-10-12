import { createBrowserRouter } from 'react-router'

import { AppLayout, RouteError } from './components/layout/AppLayout'
import {
  adminLayoutLoader,
  adminNewQuotationLoader,
  adminQuotationDetailLoader,
  adminQuotationsLoader,
  auditLogLoader,
  dashboardLoader,
  laborRatesLoader,
  materialsLoader,
  productDetailLoader,
  productsLoader,
  sessionsLoader,
  usersLoader,
} from './features/admin/loaders'
import { HomePage } from './features/auth/HomePage'
import { LoginPage } from './features/auth/LoginPage'
import { StaffLoginPage } from './features/auth/StaffLoginPage'
import { profileLoader } from './features/profile/loader'
import { ProfilePage } from './features/profile/ProfilePage'
import {
  newQuotationLoader,
  quotationDetailLoader,
  quotationsLoader,
} from './features/quotations/loader'
import { NewQuotationPage } from './features/quotations/NewQuotationPage'
import { QuotationDetailPage } from './features/quotations/QuotationDetailPage'
import { QuotationsPage } from './features/quotations/QuotationsPage'
import { redirectIfSignedIn, requireRole, rootLoader } from './lib/guards'

// Admin pages load on first visit to /admin, so customers never download them.
const adminPages = () => import('./features/admin/pages')
const admin = (name: keyof Awaited<ReturnType<typeof adminPages>>) => async () => ({
  Component: (await adminPages())[name],
})

export const router = createBrowserRouter([
  {
    id: 'root',
    element: <AppLayout />,
    loader: rootLoader,
    errorElement: <RouteError />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/login', element: <LoginPage />, loader: redirectIfSignedIn },
      { path: '/staff/login', element: <StaffLoginPage />, loader: redirectIfSignedIn },
      {
        // Customer area
        path: '/app',
        loader: () => requireRole(['user']),
        children: [
          {
            path: 'profile',
            element: <ProfilePage />,
            loader: profileLoader,
          },
          { path: 'quotations', element: <QuotationsPage />, loader: quotationsLoader },
          { path: 'quotations/new', element: <NewQuotationPage />, loader: newQuotationLoader },
          {
            path: 'quotations/:quotationId',
            element: <QuotationDetailPage />,
            loader: quotationDetailLoader,
          },
        ],
      },
      {
        // Staff area
        id: 'admin',
        path: '/admin',
        lazy: admin('AdminLayout'),
        loader: adminLayoutLoader,
        children: [
          { index: true, lazy: admin('DashboardPage'), loader: dashboardLoader },
          { path: 'users', lazy: admin('UsersPage'), loader: usersLoader },
          { path: 'sessions', lazy: admin('SessionsPage'), loader: sessionsLoader },
          { path: 'quotations', lazy: admin('AdminQuotationsPage'), loader: adminQuotationsLoader },
          {
            path: 'quotations/new',
            lazy: admin('AdminNewQuotationPage'),
            loader: adminNewQuotationLoader,
          },
          {
            path: 'quotations/:quotationId',
            lazy: admin('AdminQuotationDetailPage'),
            loader: adminQuotationDetailLoader,
          },
          { path: 'materials', lazy: admin('MaterialsPage'), loader: materialsLoader },
          { path: 'labor-rates', lazy: admin('LaborRatesPage'), loader: laborRatesLoader },
          { path: 'products', lazy: admin('ProductsPage'), loader: productsLoader },
          {
            path: 'products/:productId',
            lazy: admin('ProductDetailPage'),
            loader: productDetailLoader,
          },
          { path: 'settings', lazy: admin('PricingSettingsPage') },
          { path: 'audit-log', lazy: admin('AuditLogPage'), loader: auditLogLoader },
        ],
      },
    ],
  },
])
