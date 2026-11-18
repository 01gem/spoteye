import { useEffect, useState } from 'react'
import { errorMessage, getHealth } from '../api'
import type { Health } from '../types'

interface Problem {
  what: string
  fix: string
}

function problems(health: Health): Problem[] {
  const list: Problem[] = []
  if (!health.ffmpeg) list.push({ what: 'FFmpeg not found', fix: 'winget install Gyan.FFmpeg' })
  if (!health.deno) list.push({ what: 'Deno not found', fix: 'winget install DenoLand.Deno' })
  if (health.spotify_auth === 'missing') {
    list.push({
      what: 'Spotify sign-in needed (run in backend)',
      fix: 'python cli.py info <any spotify url>',
    })
  }
  return list
}

const LOGIN_CMD = 'python cli.py login'
const EXPIRY_WARN_DAYS = 14
const DAY_MS = 86_400_000

interface SignInNotice {
  expired: boolean
  text: string
}

/** Red once Spotify ended the sign-in, amber during its last two weeks. */
function signInNotice(health: Health): SignInNotice | null {
  if (health.spotify_auth === 'expired') return { expired: true, text: 'Spotify sign-in expired:' }
  if (health.spotify_auth !== 'ok' || !health.spotify_auth_expires) return null
  const expires = new Date(health.spotify_auth_expires)
  if (expires.getTime() - Date.now() > EXPIRY_WARN_DAYS * DAY_MS) return null
  return { expired: false, text: `Spotify sign-in expires on ${expires.toLocaleDateString()}: run` }
}

export default function HealthBanner() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getHealth()
      .then((h) => !cancelled && setHealth(h))
      .catch((e: unknown) => !cancelled && setError(errorMessage(e)))
    return () => {
      cancelled = true
    }
  }, [])

  if (error) {
    return (
      <div role="alert" className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">
        Backend not reachable ({error}). Start it with{' '}
        <code className="font-mono">uvicorn app.main:app --host 127.0.0.1 --port 8000</code>
      </div>
    )
  }
  if (!health) return null

  const missing = problems(health)
  const notice = signInNotice(health)
  return (
    <div className="space-y-2">
      {notice && (
        <div
          role="alert"
          className={`rounded-lg border p-3 text-sm ${
            notice.expired
              ? 'border-red-500/40 bg-red-500/10 text-red-200'
              : 'border-amber-500/40 bg-amber-500/10 text-amber-100'
          }`}
        >
          {notice.text} <code className="rounded bg-black/30 px-1.5 py-0.5 font-mono">{LOGIN_CMD}</code>
        </div>
      )}
      {missing.length > 0 && (
        <div role="alert" className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-100">
          <p className="mb-1 font-medium text-amber-200">Setup needed</p>
          <ul className="space-y-1">
            {missing.map((p) => (
              <li key={p.what}>
                {p.what}: <code className="rounded bg-black/30 px-1.5 py-0.5 font-mono">{p.fix}</code>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="text-xs text-zinc-500">
        Downloads go to: <span className="font-mono break-all">{health.output_dir}</span>
      </p>
      <p className="text-xs text-zinc-500">
        yt-dlp {health.yt_dlp_version} · cookies {health.cookies ? 'on' : 'off'}
      </p>
      {!health.cookies && (
        <p className="text-xs text-zinc-600">
          Set COOKIES_FILE in backend/.env if downloads hit YouTube bot checks.
        </p>
      )}
    </div>
  )
}
