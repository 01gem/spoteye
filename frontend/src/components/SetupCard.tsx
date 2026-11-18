import { useId, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { errorMessage } from '../api'
import { SettingsError, saveSettings, toForm } from '../settingsApi'
import type { Settings } from '../settingsApi'
import type { Health } from '../types'
import CopyButton from './CopyButton'
import SignInButton from './SignInButton'

const DASHBOARD_URL = 'https://developer.spotify.com/dashboard'
const REDIRECT_URI = 'http://127.0.0.1:8765/callback'

interface Props {
  settings: Settings
  health: Health
  onRefresh: () => void
}

function Step({ n, title, done, children }: { n: number; title: string; done: boolean; children: ReactNode }) {
  return (
    <li className="flex gap-3">
      <span
        aria-label={done ? 'done' : `step ${n}`}
        className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
          done ? 'bg-green-600 text-white' : 'bg-zinc-800 text-zinc-300'
        }`}
      >
        {done ? '✓' : n}
      </span>
      <div className="min-w-0 flex-1 space-y-2">
        <p className="font-medium text-zinc-100">{title}</p>
        {children}
      </div>
    </li>
  )
}

/** First-run guide: Spotify app -> Client ID -> sign in. Hidden by App once both are done. */
export default function SetupCard({ settings, health, onRefresh }: Props) {
  const id = useId()
  const [clientId, setClientId] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const hasClientId = settings.spotify_client_id !== ''
  const signedIn = health.spotify_auth === 'ok'

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await saveSettings({ ...toForm(settings), spotify_client_id: clientId.trim() })
      onRefresh()
    } catch (e: unknown) {
      setError(e instanceof SettingsError ? (e.fieldErrors.spotify_client_id ?? e.message) : errorMessage(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section
      aria-labelledby={`${id}-title`}
      className="space-y-4 rounded-lg border border-sky-500/30 bg-sky-500/5 p-4 text-sm text-zinc-300"
    >
      <h2 id={`${id}-title`} className="text-base font-semibold text-zinc-100">
        Set up Spoteye
      </h2>
      <ol className="space-y-4">
        <Step n={1} title="Create a Spotify app" done={hasClientId}>
          <p>
            Open the{' '}
            <a href={DASHBOARD_URL} target="_blank" rel="noreferrer" className="text-sky-400 underline">
              Spotify developer dashboard
            </a>
            , create an app and add this Redirect URI:
          </p>
          <p className="flex flex-wrap items-center gap-2">
            <code className="rounded bg-black/40 px-1.5 py-0.5 font-mono">{REDIRECT_URI}</code>
            <CopyButton text={REDIRECT_URI} label="Redirect URI" />
          </p>
          <p className="text-xs text-zinc-500">Your Spotify account needs Premium. Spotify allows 5 users per app.</p>
        </Step>
        <Step n={2} title="Paste the Client ID" done={hasClientId}>
          {hasClientId ? (
            <p>A Client ID is already set (change it in Settings).</p>
          ) : (
            <form onSubmit={(e) => void onSubmit(e)} className="flex flex-wrap items-start gap-2">
              <label htmlFor={`${id}-client`} className="sr-only">
                Spotify Client ID
              </label>
              <input
                id={`${id}-client`}
                value={clientId}
                onChange={(e) => setClientId(e.target.value)}
                placeholder="32 characters, from your app's Basic Information"
                autoComplete="off"
                spellCheck={false}
                aria-invalid={error !== null}
                aria-describedby={error ? `${id}-client-error` : undefined}
                className="min-w-0 flex-1 rounded-md border border-zinc-700 bg-zinc-950 px-3 py-1.5 font-mono text-sm placeholder:font-sans placeholder:text-zinc-600"
              />
              <button
                type="submit"
                disabled={saving || clientId.trim() === ''}
                className="rounded-md bg-zinc-800 px-3 py-1.5 font-medium hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {saving ? 'Saving…' : 'Save'}
              </button>
              {error && (
                <p id={`${id}-client-error`} role="alert" className="w-full text-red-400">
                  {error}
                </p>
              )}
            </form>
          )}
        </Step>
        <Step n={3} title="Sign in" done={signedIn}>
          <SignInButton onFinished={onRefresh} disabled={!hasClientId} />
          {!hasClientId && <p className="text-xs text-zinc-500">Save a Client ID first.</p>}
        </Step>
      </ol>
    </section>
  )
}
