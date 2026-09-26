import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import { api } from '../../api/client'

export function HomePage() {
  const [apiStatus, setApiStatus] = useState<'checking' | 'ok' | 'down'>('checking')

  useEffect(() => {
    api<{ status: string }>('/health')
      .then(() => setApiStatus('ok'))
      .catch(() => setApiStatus('down'))
  }, [])

  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Automatic Quotation System</h1>
      <p className="text-muted">
        Get an instant estimate for sliding windows, sliding doors, and window grills.
      </p>
      <Link
        to="/login"
        className="inline-block rounded-lg bg-brand-600 px-4 py-2 font-medium text-white hover:bg-brand-700"
      >
        Get a quotation
      </Link>
      <p className="text-xs text-muted">API: {apiStatus}</p>
    </section>
  )
}
