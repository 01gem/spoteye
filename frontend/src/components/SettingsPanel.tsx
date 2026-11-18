import { useEffect, useId, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../api'
import { SettingsError, fromDraft, saveSettings, toDraft } from '../settingsApi'
import type { FieldErrors, Settings, SettingsForm } from '../settingsApi'
import type { Health } from '../types'
import CopyButton from './CopyButton'
import SettingsFields from './SettingsFields'
import SignInButton from './SignInButton'
import YtDlpSection from './YtDlpSection'

const SAVED_MS = 2000

interface Props {
  settings: Settings
  health: Health
  onClose: () => void
  /** Re-read settings + health (after a save, sign-in or yt-dlp update). */
  onRefresh: () => void
}

/** Right-side slide-over; render it only while open (the draft starts from `settings`). */
export default function SettingsPanel({ settings, health, onClose, onRefresh }: Props) {
  const id = useId()
  const firstField = useRef<HTMLInputElement>(null)
  const [draft, setDraft] = useState(() => toDraft(settings))
  const [errors, setErrors] = useState<FieldErrors>({})
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    firstField.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  function onChange(name: keyof SettingsForm, value: string) {
    setDraft((d) => ({ ...d, [name]: value }))
    setSaved(false)
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setErrors({})
    setError(null)
    try {
      setDraft(toDraft(await saveSettings(fromDraft(draft))))
      setSaved(true)
      setTimeout(() => setSaved(false), SAVED_MS)
      onRefresh()
    } catch (e: unknown) {
      if (e instanceof SettingsError && Object.keys(e.fieldErrors).length > 0) setErrors(e.fieldErrors)
      else setError(errorMessage(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} aria-hidden="true" />
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${id}-title`}
        className="absolute inset-y-0 right-0 flex w-full max-w-md flex-col gap-6 overflow-y-auto border-l border-zinc-800 bg-zinc-900 p-5 shadow-2xl"
      >
        <h2 id={`${id}-title`} className="text-lg font-semibold text-zinc-100">
          Settings
        </h2>
        <form onSubmit={(e) => void onSubmit(e)} className="space-y-4">
          <SettingsFields draft={draft} errors={errors} onChange={onChange} firstRef={firstField} />
          {error && (
            <p role="alert" className="text-sm text-red-400">
              {error}
            </p>
          )}
          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={saving}
              className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-zinc-700 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-800"
            >
              Cancel
            </button>
            {saved && (
              <span role="status" className="text-sm text-green-400">
                Saved
              </span>
            )}
          </div>
        </form>
        <section className="space-y-1">
          <h3 className="text-sm font-semibold text-zinc-200">App data folder</h3>
          <p className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
            <span className="font-mono break-all">{settings.app_home}</span>
            <CopyButton text={settings.app_home} label="app data folder" />
          </p>
        </section>
        <section className="space-y-2">
          <h3 className="text-sm font-semibold text-zinc-200">Spotify</h3>
          <SignInButton onFinished={onRefresh} label="Sign in again" />
        </section>
        <YtDlpSection health={health} onUpdated={onRefresh} />
      </aside>
    </div>
  )
}
