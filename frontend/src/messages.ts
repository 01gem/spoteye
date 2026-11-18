/**
 * Download errors whose backend wording points at backend/.env or pip: say where to fix them
 * in the app instead (the Settings panel). Other messages are shown unchanged.
 */
const RULES: readonly (readonly [RegExp, string])[] = [
  [/bot check/i, 'YouTube bot check: add a cookies file under Settings → YouTube cookies file.'],
  [/refused the download \(403\)/i, 'YouTube refused the download (403): use Update yt-dlp in Settings.'],
]

export function trackErrorText(error: string): string {
  const rule = RULES.find(([pattern]) => pattern.test(error))
  return rule ? rule[1] : error
}
