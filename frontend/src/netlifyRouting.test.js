/**
 * The Netlify routing contract.
 *
 * This site ships the frontend only, and its catch-all rule sends every
 * unmatched path to index.html. That is right for a deep link and wrong for
 * /api/...: a request the SPA fallback answers is a 200 with an HTML body, and a
 * client asking for JSON cannot distinguish that from a working API. The
 * supervisor panel read exactly that way while the fault was a routing rule, and
 * the symptom was "Supervisor information is unavailable right now."
 *
 * So the rules below are pinned as a contract rather than as formatting. The two
 * properties that actually matter: API paths reach the backend before the
 * fallback sees them, and the fallback keeps its scope so assets, deep links and
 * the static snapshot still resolve from disk.
 */

import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/* jsdom replaces the global URL, and its implementation resolves a relative
   reference against the document's base rather than the base it is handed - so
   `new URL('../netlify.toml', import.meta.url)` yields
   http://localhost:3000/netlify.toml and readFileSync rejects it as the wrong
   scheme. Deriving the path with Node's own parser sidesteps the environment
   entirely. */
const HERE = dirname(fileURLToPath(import.meta.url))
const NETLIFY_TOML = readFileSync(resolve(HERE, '..', 'netlify.toml'), 'utf8')

/** One `[[redirects]]` block's key/value pairs, plus its position in the file. */
function parseRedirects(source) {
  const blocks = []
  const lines = source.split(/\r?\n/)
  let current = null

  lines.forEach((line, index) => {
    const trimmed = line.trim()
    if (trimmed === '[[redirects]]') {
      current = { order: index, fields: {} }
      blocks.push(current)
      return
    }
    // A new TOML section ends the current redirect block.
    if (/^\[/.test(trimmed)) {
      current = null
      return
    }
    if (current === null) return

    const match = trimmed.match(/^([A-Za-z0-9_-]+)\s*=\s*(.+)$/)
    if (!match) return
    const [, key, rawValue] = match
    let value = rawValue.trim()
    const quoted = value.match(/^"(.*)"$/)
    if (quoted) {
      value = quoted[1]
    } else if (value === 'true' || value === 'false') {
      value = value === 'true'
    } else if (/^\d+$/.test(value)) {
      value = Number(value)
    }
    current.fields[key] = value
  })

  return blocks.filter((block) => 'from' in block.fields)
}

const redirects = parseRedirects(NETLIFY_TOML)

const apiRule = redirects.find((rule) => rule.fields.from === '/api/*')
const spaRule = redirects.find((rule) => rule.fields.from === '/*')

describe('netlify.toml API routing', () => {
  it('proxies /api/* rather than letting the SPA fallback answer it', () => {
    /* The defect: no API rule existed, so the fallback served index.html for
       every API call. The absence of a rule is the failure, so this asserts the
       rule is present. */
    expect(apiRule, 'netlify.toml has no [[redirects]] rule for /api/*').toBeTruthy()
  })

  it('sends API traffic to the backend, not back to index.html', () => {
    expect(apiRule.fields.to).toMatch(/^https:\/\/[^/]+\/api\/:splat$/)
    // The exact regression: a rule that "fixes" the symptom by proxying /api to
    // the SPA shell, which keeps HTML where JSON was asked for.
    expect(apiRule.fields.to).not.toMatch(/index\.html/)
  })

  it('proxies as a rewrite so the request stays same-origin', () => {
    /* status 200 is a server-side proxy and leaves the browser URL on this
       origin, which is what keeps it a same-origin request: no preflight, no
       CORS change, and the session cookie rides along. A 301/302 would send the
       browser to another origin, where its cookie for that host is not sent. */
    expect(apiRule.fields.status).toBe(200)
    expect(apiRule.fields.to).not.toMatch(/^\/index\.html$/)
  })

  it('places the API rule before the SPA fallback', () => {
    /* Netlify applies the first matching rule, so precedence is the whole
       mechanism. If the fallback came first, /api/* would still be answered with
       the shell and the proxy would be dead config. */
    expect(apiRule.order).toBeLessThan(spaRule.order)
  })

  it('carries the whole matched path through :splat', () => {
    /* The supervisor route is /scholarships/{id}/supervisors, two segments deep
       under /api. A single `*` capture keeps the nesting; the placeholder name is
       what Netlify substitutes it into. */
    expect(apiRule.fields.to).toContain(':splat')
    expect(apiRule.fields.to).toMatch(/\/api\/:splat$/)
  })

  it('captures only API paths, leaving assets and deep links to the fallback', () => {
    /* A rule written as `/*` with an /api condition, or with a leading wildcard,
       would swallow hashed assets and the static snapshot. The `from` prefix is
       what bounds it. */
    expect(apiRule.fields.from).toBe('/api/*')

    const captured = (path) => new RegExp('^/api(/.*)?$').test(path)
    expect(captured('/api/scholarships/1/supervisors')).toBe(true)
    expect(captured('/api/health')).toBe(true)
    expect(captured('/assets/index-abc123.js')).toBe(false)
    expect(captured('/scholarships/12')).toBe(false)
    expect(captured('/sitemap.xml')).toBe(false)
    expect(captured('/scholarships-snapshot.json')).toBe(false)
  })

  it('keeps the SPA fallback without force, so real files still resolve', () => {
    /* `force = true` on a catch-all tells Netlify to ignore the filesystem, so
       index.html would be returned for a request that has a real file. Assets,
       robots.txt and the snapshot are those files. */
    expect(spaRule.fields.force).toBeUndefined()
    expect(spaRule.fields.to).toBe('/index.html')
    expect(spaRule.fields.status).toBe(200)
  })

  it('keeps exactly one rule per concern, so routing has a single source', () => {
    /* Two competing API routes, or a second fallback, make precedence depend on
       a reader's memory rather than on the file. */
    expect(redirects.filter((rule) => rule.fields.from === '/api/*')).toHaveLength(1)
    expect(redirects.filter((rule) => rule.fields.from === '/*')).toHaveLength(1)
    expect(redirects).toHaveLength(2)
  })
})
