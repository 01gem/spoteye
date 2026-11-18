import { useEffect, useState } from 'react'
import { errorMessage, openFolder } from '../api'

const COPIED_MS = 2000

interface Props {
  path: string
  /** When given, an "Open folder" button opens the job's folder in Explorer. */
  jobId?: number
  label?: string
}

function FolderIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-4 w-4 shrink-0 text-zinc-500"
    >
      <path d="M2 5.5A1.5 1.5 0 0 1 3.5 4h4.09a1.5 1.5 0 0 1 1.06.44L10.2 6h6.3A1.5 1.5 0 0 1 18 7.5v7a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 2 14.5v-9Z" />
    </svg>
  )
}

const BUTTON =
  'rounded border border-zinc-700 px-2 py-0.5 text-xs text-zinc-300 hover:bg-zinc-800 disabled:opacity-50'

export default function SaveLocation({ path, jobId, label = 'Saved to' }: Props) {
  const [copied, setCopied] = useState(false)
  const [opening, setOpening] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!copied) return
    const timer = window.setTimeout(() => setCopied(false), COPIED_MS)
    return () => window.clearTimeout(timer)
  }, [copied])

  async function copy() {
    try {
      await navigator.clipboard.writeText(path)
      setCopied(true)
    } catch (e: unknown) {
      setError(`Could not copy: ${errorMessage(e)}`)
    }
  }

  async function open() {
    if (jobId === undefined) return
    setOpening(true)
    setError(null)
    try {
      await openFolder(jobId)
    } catch (e: unknown) {
      setError(errorMessage(e))
    } finally {
      setOpening(false)
    }
  }

  return (
    <div className="space-y-1 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <FolderIcon />
        <span className="text-zinc-400">{label}</span>
        <span className="min-w-0 font-mono break-all text-zinc-200">{path}</span>
        <button
          type="button"
          onClick={() => void copy()}
          aria-label={copied ? 'Path copied' : `Copy path ${path}`}
          className={BUTTON}
        >
          {copied ? 'Copied' : 'Copy path'}
        </button>
        {jobId !== undefined && (
          <button
            type="button"
            onClick={() => void open()}
            disabled={opening}
            aria-label="Open folder in File Explorer"
            className={BUTTON}
          >
            {opening ? 'Opening…' : 'Open folder'}
          </button>
        )}
      </div>
      {error && (
        <p role="alert" className="text-red-400">
          {error}
        </p>
      )}
    </div>
  )
}
