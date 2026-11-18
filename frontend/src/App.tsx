import { useCallback, useEffect, useRef, useState } from 'react'
import { errorMessage, getHealth } from './api'
import HealthBanner from './components/HealthBanner'
import JobHistory from './components/JobHistory'
import JobView from './components/JobView'
import LinkForm from './components/LinkForm'
import SettingsPanel from './components/SettingsPanel'
import SetupCard from './components/SetupCard'
import TrackPreview from './components/TrackPreview'
import { getSettings } from './settingsApi'
import type { Settings } from './settingsApi'
import type { Health, Resolved } from './types'

export default function App() {
  const [preview, setPreview] = useState<Resolved | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [historyKey, setHistoryKey] = useState(0)
  const [health, setHealth] = useState<Health | null>(null)
  const [settings, setSettings] = useState<Settings | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const gear = useRef<HTMLButtonElement>(null)

  /** One fetch of health + settings, shared by the banner, setup card and settings panel. */
  const refreshNow = useCallback(() => {
    Promise.all([getHealth(), getSettings()])
      .then(([h, s]) => {
        setHealth(h)
        setSettings(s)
        setLoadError(null)
      })
      .catch((e: unknown) => setLoadError(errorMessage(e)))
  }, [])

  useEffect(refreshNow, [refreshNow])

  const closeSettings = useCallback(() => {
    setSettingsOpen(false)
    gear.current?.focus()
  }, [])

  const refreshHistory = useCallback(() => setHistoryKey((k) => k + 1), [])
  const onCreated = useCallback(
    (jobId: number) => {
      setSelectedId(jobId)
      refreshHistory()
    },
    [refreshHistory],
  )

  const onDeleted = useCallback(
    (jobId: number) => {
      setSelectedId((current) => (current === jobId ? null : current))
      refreshHistory()
    },
    [refreshHistory],
  )

  const setupVisible =
    settings !== null &&
    health !== null &&
    (settings.spotify_client_id === '' || health.spotify_auth === 'missing')

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-6">
      <header className="space-y-3">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold tracking-tight">
            Spot<span className="text-green-500">eye</span>
          </h1>
          <button
            ref={gear}
            type="button"
            aria-label="Settings"
            title="Settings"
            disabled={settings === null || health === null}
            onClick={() => setSettingsOpen(true)}
            className="rounded-md p-2 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100 disabled:opacity-40"
          >
            <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
            </svg>
          </button>
        </div>
        {setupVisible && <SetupCard settings={settings} health={health} onRefresh={refreshNow} />}
        <HealthBanner health={health} error={loadError} hideMissingSignIn={setupVisible} onRefresh={refreshNow} />
      </header>
      <main className="grid gap-6 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
        <div className="space-y-6">
          <LinkForm onPreview={setPreview} onCreated={onCreated} />
          {preview && <TrackPreview resolved={preview} />}
          <JobHistory
            selectedId={selectedId}
            onSelect={setSelectedId}
            onDeleted={onDeleted}
            refreshKey={historyKey}
          />
        </div>
        <div className="min-w-0">
          {selectedId === null ? (
            <p className="rounded-lg border border-dashed border-zinc-800 p-10 text-center text-sm text-zinc-500">
              Paste a link and press Download, or pick a job from the history.
            </p>
          ) : (
            <JobView key={selectedId} jobId={selectedId} onStatusChange={refreshHistory} />
          )}
        </div>
      </main>
      {settingsOpen && settings && health && (
        <SettingsPanel settings={settings} health={health} onClose={closeSettings} onRefresh={refreshNow} />
      )}
    </div>
  )
}
