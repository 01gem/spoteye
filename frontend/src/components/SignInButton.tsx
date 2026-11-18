import { useEffect, useRef, useState } from 'react'
import { cancelLogin, errorMessage, getLoginStatus, startLogin } from '../api'
import type { LoginStatus } from '../types'
import Spinner from './Spinner'

const POLL_MS = 1000

const sleep = (ms: number) => new Promise<void>((done) => setTimeout(done, ms))

/**
 * "Sign in with Spotify": the backend opens Spotify's page and waits for approval; we poll
 * /api/auth/status. Clicking again restarts (the backend replaces the pending attempt).
 * onFinished runs when a sign-in ends without an error (the caller re-reads health).
 */
export default function SignInButton({ onFinished }: { onFinished: () => void }) {
  const [waiting, setWaiting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Bumped by every start, cancel and unmount: a poll from an older attempt is ignored.
  const attempt = useRef(0)

  useEffect(() => {
    return () => {
      attempt.current += 1
    }
  }, [])

  async function start() {
    const id = ++attempt.current
    setError(null)
    try {
      await startLogin()
    } catch (e: unknown) {
      if (id === attempt.current) {
        setError(errorMessage(e))
        setWaiting(false)
      }
      return
    }
    if (id !== attempt.current) return
    setWaiting(true)
    for (;;) {
      await sleep(POLL_MS)
      if (id !== attempt.current) return
      let status: LoginStatus
      try {
        status = await getLoginStatus()
      } catch (e: unknown) {
        if (id === attempt.current) {
          setError(errorMessage(e))
          setWaiting(false)
        }
        return
      }
      if (id !== attempt.current) return
      if (!status.running) {
        setWaiting(false)
        if (status.last_error) setError(status.last_error)
        else onFinished()
        return
      }
    }
  }

  async function cancel() {
    attempt.current += 1
    setWaiting(false)
    try {
      await cancelLogin()
    } catch (e: unknown) {
      setError(errorMessage(e))
    }
  }

  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={() => void start()}
        className="rounded-md bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-500"
      >
        Sign in with Spotify
      </button>
      {waiting && (
        <>
          <span role="status" className="inline-flex items-center gap-1.5 text-sm text-zinc-300">
            <Spinner />
            Waiting for you to approve in the browser…
          </span>
          <button
            type="button"
            onClick={() => void cancel()}
            className="rounded-md border border-zinc-700 px-3 py-1.5 text-sm font-medium text-zinc-200 hover:bg-zinc-800"
          >
            Cancel
          </button>
        </>
      )}
      {error && (
        <span role="alert" className="text-sm text-red-400">
          {error}
        </span>
      )}
    </span>
  )
}
