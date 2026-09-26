import { LogIn, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import { GOOGLE_LOGIN_URL } from '../../api/auth'
import { buttonStyles } from '../../components/ui/buttonStyles'
import { ErrorBanner } from '../../components/ui/Card'
import { Spinner } from '../../components/ui/Spinner'
import { AuthShell, GoogleMark } from './AuthShell'

const ERRORS: Record<string, string> = {
  domain: 'Please sign in with your @up.edu.ph Google account.',
  conflict: 'This email belongs to a staff account. Use Staff login instead.',
  disabled: 'This account has been disabled. Please contact the shop.',
  google: 'Google sign-in did not complete. Please try again.',
}

export function LoginPage() {
  const [params] = useSearchParams()
  const [leaving, setLeaving] = useState(false)
  const errorCode = params.get('error')
  const error = errorCode ? (ERRORS[errorCode] ?? ERRORS.google) : null

  return (
    <AuthShell
      icon={LogIn}
      title="Sign in"
      subtitle="Use your @up.edu.ph Google account to request quotations."
      footer={
        <>
          Staff member?{' '}
          <Link to="/staff/login" className="font-medium text-brand hover:underline">
            Staff login
          </Link>
        </>
      }
    >
      <div className="space-y-4">
        <ErrorBanner message={error} />
        {/* Full-page navigation, not fetch: the backend redirects to Google. */}
        <a
          href={GOOGLE_LOGIN_URL}
          onClick={() => setLeaving(true)}
          aria-busy={leaving || undefined}
          className={buttonStyles('secondary', 'md', 'h-12 w-full text-base')}
        >
          {leaving ? <Spinner className="size-5" /> : <GoogleMark />}
          {leaving ? 'Opening Google…' : 'Continue with Google'}
        </a>
        <p className="flex items-start gap-2 rounded-xl bg-surface-2 p-3 text-xs text-muted">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
          We only receive your name and email from Google. We never see your Google password.
        </p>
      </div>
    </AuthShell>
  )
}
