import type { Health } from '../types'
import SignInButton from './SignInButton'

interface Problem {
  what: string
  fix: string
  /** Show `fix` as a command (source mode) rather than as plain text. */
  command: boolean
}

function problems(health: Health): Problem[] {
  const tool = (what: string, winget: string): Problem =>
    health.frozen
      ? { what, fix: 'Bundled tool missing: reinstall Spoteye', command: false }
      : { what, fix: winget, command: true }
  const list: Problem[] = []
  if (!health.ffmpeg) list.push(tool('FFmpeg not found', 'winget install Gyan.FFmpeg'))
  if (!health.deno) list.push(tool('Deno not found', 'winget install DenoLand.Deno'))
  return list
}

const EXPIRY_WARN_DAYS = 14
const DAY_MS = 86_400_000

type Tone = 'red' | 'amber' | 'zinc'

const TONE_CLASS: Record<Tone, string> = {
  red: 'border-red-500/40 bg-red-500/10 text-red-200',
  amber: 'border-amber-500/40 bg-amber-500/10 text-amber-100',
  zinc: 'border-zinc-700 bg-zinc-800/60 text-zinc-300',
}

interface SignInNotice {
  tone: Tone
  text: string
  /** Show the "Sign in with Spotify" button after the text. */
  login: boolean
}

/** Amber before the first sign-in and in its last two weeks, red once expired, gray offline. */
function signInNotice(health: Health): SignInNotice | null {
  if (health.spotify_auth === 'missing') {
    return { tone: 'amber', text: 'Sign in to Spotify to read playlists.', login: true }
  }
  if (health.spotify_auth === 'expired') return { tone: 'red', text: 'Spotify sign-in expired.', login: true }
  if (health.spotify_auth === 'offline') {
    return { tone: 'zinc', text: "Can't reach Spotify right now (offline?)", login: false }
  }
  if (health.spotify_auth !== 'ok' || !health.spotify_auth_expires) return null
  const expires = new Date(health.spotify_auth_expires)
  if (expires.getTime() - Date.now() > EXPIRY_WARN_DAYS * DAY_MS) return null
  return { tone: 'amber', text: `Spotify sign-in expires on ${expires.toLocaleDateString()}.`, login: true }
}

interface Props {
  health: Health | null
  /** The backend could not be reached. */
  error: string | null
  /** SetupCard is showing its own sign-in step: skip the "missing" notice. */
  hideMissingSignIn: boolean
  onRefresh: () => void
}

export default function HealthBanner({ health, error, hideMissingSignIn, onRefresh }: Props) {
  if (error) {
    return (
      <div role="alert" className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">
        {import.meta.env.DEV ? (
          <>
            Backend not reachable ({error}). Start it with{' '}
            <code className="font-mono">uvicorn app.main:app --host 127.0.0.1 --port 8000</code>
          </>
        ) : (
          "Spoteye isn't running. Start Spoteye.exe again."
        )}
      </div>
    )
  }
  if (!health) return null

  const missing = problems(health)
  const notice = signInNotice(health)
  const showNotice = notice !== null && !(hideMissingSignIn && health.spotify_auth === 'missing')
  return (
    <div className="space-y-2">
      {showNotice && notice && (
        <div
          role={notice.tone === 'zinc' ? 'status' : 'alert'}
          className={`flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border p-3 text-sm ${TONE_CLASS[notice.tone]}`}
        >
          <span>{notice.text}</span>
          {notice.login && <SignInButton onFinished={onRefresh} />}
        </div>
      )}
      {missing.length > 0 && (
        <div role="alert" className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-100">
          <p className="mb-1 font-medium text-amber-200">Setup needed</p>
          <ul className="space-y-1">
            {missing.map((p) => (
              <li key={p.what}>
                {p.what}:{' '}
                {p.command ? <code className="rounded bg-black/30 px-1.5 py-0.5 font-mono">{p.fix}</code> : p.fix}
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
    </div>
  )
}
