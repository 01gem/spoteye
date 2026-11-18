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
  if (!health.spotify_auth) {
    list.push({
      what: 'Spotify sign-in needed (run in backend)',
      fix: 'python cli.py info <any spotify url>',
    })
  }
  return list
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
  return (
    <div className="space-y-2">
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
