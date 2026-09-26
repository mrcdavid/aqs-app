// Single fetch wrapper for the API. Every request:
// - sends cookies (the httpOnly session cookie is handled by the browser, never by JS)
// - adds the X-CSRF-Token header on state-changing requests

const CSRF_COOKIE = 'aqs_csrf'
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// FastAPI sends a string, or for validation errors a list of { loc, msg }.
function errorMessage(detail: unknown): string | undefined {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => {
        const field = d.loc?.filter((p) => p !== 'body').join('.')
        return field ? `${field}: ${d.msg}` : d.msg
      })
      .join('; ')
  }
  return undefined
}

function readCookie(name: string): string | undefined {
  return document.cookie
    .split('; ')
    .find((c) => c.startsWith(`${name}=`))
    ?.split('=')[1]
}

async function ensureCsrfCookie(): Promise<string> {
  let token = readCookie(CSRF_COOKIE)
  if (!token) {
    // Any GET makes the server issue the cookie.
    await fetch('/api/v1/health', { credentials: 'same-origin' })
    token = readCookie(CSRF_COOKIE)
  }
  if (!token) throw new ApiError(0, 'Could not get CSRF token')
  return token
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers = new Headers(init.headers)
  if (init.body !== undefined && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  if (!SAFE_METHODS.has(method)) {
    headers.set('X-CSRF-Token', await ensureCsrfCookie())
  }

  const res = await fetch(`/api/v1${path}`, { ...init, method, headers, credentials: 'same-origin' })
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: unknown } | null
    throw new ApiError(res.status, errorMessage(body?.detail) ?? res.statusText)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}
