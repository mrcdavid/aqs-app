import { LogIn } from 'lucide-react'
import { Link, useSearchParams } from 'react-router'

import { GOOGLE_LOGIN_URL } from '../../api/auth'
import { buttonClass } from '../../components/ui/Field'

const ERRORS: Record<string, string> = {
  domain: 'Please sign in with your @up.edu.ph Google account.',
  conflict: 'This email belongs to a staff account. Use Staff login instead.',
  disabled: 'This account has been disabled. Please contact the shop.',
  google: 'Google sign-in did not complete. Please try again.',
}

export function LoginPage() {
  const [params] = useSearchParams()
  const errorCode = params.get('error')
  const error = errorCode ? (ERRORS[errorCode] ?? ERRORS.google) : null

  return (
    <section className="mx-auto max-w-sm rounded-xl bg-white p-6 shadow-sm">
      <h1 className="text-xl font-semibold">Sign in</h1>
      <p className="mt-1 text-sm text-muted">Use your @up.edu.ph Google account.</p>
      {error && (
        <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}
      {/* Full-page navigation, not fetch: the backend redirects to Google. */}
      <a href={GOOGLE_LOGIN_URL} className={`${buttonClass} mt-6 w-full`}>
        <LogIn className="size-4" aria-hidden />
        Continue with Google
      </a>
      <p className="mt-4 text-center text-sm">
        <Link to="/staff/login" className="text-brand-600 hover:underline">
          Staff login
        </Link>
      </p>
    </section>
  )
}
