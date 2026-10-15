// @vitest-environment node
/**
 * The crawl contract for the approved production architecture.
 *
 * The site ships the approved single-page design as its own entry document:
 * index.html is the design itself (inline styles, Google fonts, inline
 * scripts), it fetches the public catalogue snapshot at runtime, and the
 * edge middleware rewrites the SEO head per route so detail pages declare
 * their own canonical and unknown ids return a real 404.
 *
 * A previous version of this test asserted that the committed index.html
 * must contain the React root and the /src/main.jsx module entry. That
 * described the retired architecture: with the approved design as the entry,
 * those assertions fail on the file that actually ships, and passing them
 * would require restoring an entry point the design deliberately replaced.
 * The test is therefore rewritten against the architecture that is actually
 * deployed, and it guards that architecture in both directions:
 *
 *   - the approved design survives the build (styles, fonts, scripts)
 *   - the Google verification token is unchanged
 *   - the public snapshot loads from the deployed site origin
 *   - catalogue loading errors stay visible and retryable
 *   - SEO tags are correct for the route actually requested
 *   - no accidental regression to the old React entry
 *
 * The document under test is the one that ships: frontend/index.html on
 * disk, not a committed revision. HEAD may still carry the retired entry,
 * and a test that read HEAD would be asserting against a document the build
 * never serves.
 */
import { readFileSync } from 'node:fs'
import { describe, expect, it, vi, afterEach } from 'vitest'

import middleware from '../middleware.js'

const read = (relative) => readFileSync(new URL(relative, import.meta.url), 'utf8')

const INDEX_HTML = read('../index.html')
const SNAPSHOT = JSON.parse(read('../public/scholarships-snapshot.json'))
const RECORDS = Array.isArray(SNAPSHOT.scholarships) ? SNAPSHOT.scholarships : []
const ORIGIN = 'https://scholarzone-fwzj.vercel.app'

/** The token Google Search Console verification relies on. */
const VERIFICATION_TOKEN = 'mzaQ_MW4nVgMwHhbSOxxTsr46gaV7sanks7vbnE7aaE'

/** A record that is public, so its detail route must serve 200. */
const PUBLIC_ID = 14
const PUBLIC_RECORD = RECORDS.find((entry) => Number(entry.id) === PUBLIC_ID)

/** An id that is not in the public catalogue, so its route must 404. */
const UNKNOWN_ID = 999999

/**
 * Serve the shipped document and the shipped snapshot to the middleware,
 * the same way Vercel's edge serves them. The middleware resolves both from
 * the request origin, so a stubbed fetch that routes by pathname is a
 * faithful stand-in for the deployment.
 */
const serve = (url) => middleware(new Request(url))

const stubFetch = () => {
  vi.stubGlobal('fetch', async (input) => {
    const { pathname } = new URL(input)
    if (pathname === '/index.html') return new Response(INDEX_HTML)
    if (pathname === '/scholarships-snapshot.json') {
      return new Response(JSON.stringify(SNAPSHOT))
    }
    return new Response('not found', { status: 404 })
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

const canonicalOf = (html) =>
  html.match(/<link rel="canonical" href="([^"]+)"/i)?.[1] ?? null

const ogUrlOf = (html) =>
  [...html.matchAll(/<meta\b[^>]*property="og:url"[^>]*content="([^"]*)"/gi)][0]?.[1] ?? null

const jsonLdOf = (html) => {
  const block = html.match(
    /<script type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/i
  )?.[1]
  return block ? JSON.parse(block) : null
}

describe('the served document is the approved design', () => {
  it('carries the design\'s own styles, fonts and scripts', () => {
    // The approved design is a self-contained document: its typography,
    // paper textures, animations and the catalogue script all live inline.
    const styleBlocks = INDEX_HTML.match(/<style/g) || []
    expect(styleBlocks.length).toBeGreaterThan(8)
    expect(INDEX_HTML).toContain('family=Inter')
    expect(INDEX_HTML).toContain('family=Newsreader')
    expect(INDEX_HTML).toContain('.pp{')
    const scriptBlocks = INDEX_HTML.match(/<script\b/g) || []
    expect(scriptBlocks.length).toBeGreaterThan(5)
  })

  it('has not regressed to the retired React entry', () => {
    // The retired architecture rendered everything from /src/main.jsx into
    // an empty #root. Restoring it would ship a page with no catalogue and
    // no design, so its absence is part of the contract.
    expect(INDEX_HTML).not.toContain('id="root"')
    expect(INDEX_HTML).not.toMatch(/<script[^>]*type="module"/i)
    expect(INDEX_HTML).not.toContain('/src/main.jsx')
  })

  it('keeps the Google verification token unchanged', () => {
    const token = INDEX_HTML.match(
      /name="google-site-verification" content="([^"]+)"/
    )?.[1]
    expect(token).toBe(VERIFICATION_TOKEN)
  })

  it('loads the public snapshot from the deployed site origin', () => {
    // The catalogue must work without the database. The loader tries the
    // deployment root first, which is where Vercel serves the snapshot.
    expect(INDEX_HTML).toContain("location.origin+'/scholarships-snapshot.json'")
    expect(INDEX_HTML).toContain('fetchCatalogue')
  })

  it('keeps catalogue loading failures visible and retryable', () => {
    // A failed load must surface as an error the reader can retry, not as
    // an empty catalogue that looks like "no results".
    expect(INDEX_HTML).toContain('Catalogue unavailable')
    expect(INDEX_HTML).toContain('id="retry"')
    expect(INDEX_HTML).toContain('Try again')
  })

  it('carries a head the middleware can rewrite per route', () => {
    for (const marker of [
      'name="description"',
      'name="robots"',
      'rel="canonical"',
      'property="og:url"',
      'application/ld+json',
    ]) {
      expect(INDEX_HTML, `missing ${marker}`).toContain(marker)
    }
    const tags = [...INDEX_HTML.matchAll(/<(meta|link)\b[^>]*>/gi)].map((m) => m[0])
    const seoTags = tags.filter((tag) =>
      /og:|twitter:|robots|description|canonical/.test(tag)
    )
    expect(seoTags.length).toBeGreaterThan(0)
    for (const tag of seoTags) {
      expect(tag, 'a head tag the middleware rewrites lost its marker').toContain(
        'data-sz-seo="true"'
      )
    }
  })
})

describe('route-aware SEO on the routes that actually exist', () => {
  it('serves the homepage with its own canonical', async () => {
    stubFetch()
    const response = await serve(`${ORIGIN}/`)
    expect(response.status).toBe(200)
    const html = await response.text()
    expect(canonicalOf(html)).toBe(`${ORIGIN}/`)
    expect(ogUrlOf(html)).toBe(`${ORIGIN}/`)
  })

  it('serves the catalogue route with its own canonical', async () => {
    stubFetch()
    const response = await serve(`${ORIGIN}/scholarships`)
    expect(response.status).toBe(200)
    const html = await response.text()
    expect(canonicalOf(html)).toBe(`${ORIGIN}/scholarships`)
    expect(ogUrlOf(html)).toBe(`${ORIGIN}/scholarships`)
  })

  it('gives a public detail route record-specific SEO, not the homepage', async () => {
    stubFetch()
    const url = `${ORIGIN}/scholarships/${PUBLIC_ID}`
    const response = await serve(url)
    expect(response.status).toBe(200)
    const html = await response.text()

    const title = html.match(/<title>([^<]*)<\/title>/i)?.[1]
    // The title is HTML-escaped inside the tag, so compare against the
    // escaped form of the record name.
    expect(title).toContain(
      PUBLIC_RECORD.name.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    )

    const description = [...html.matchAll(/<meta\b[^>]*name="description"[^>]*content="([^"]*)"/gi)][0]?.[1]
    expect(description).toBeTruthy()
    expect(description.length).toBeGreaterThan(20)

    // The defect this replaced: every route declared the homepage as its
    // canonical, so every detail page collapsed onto one indexable URL.
    expect(canonicalOf(html)).toBe(url)
    expect(canonicalOf(html)).not.toBe(`${ORIGIN}/`)
    expect(ogUrlOf(html)).toBe(url)
    expect(html.match(/rel="canonical"/gi)?.length).toBe(1)

    const jsonLd = jsonLdOf(html)
    expect(jsonLd['@type']).toBe('ScholarshipProgram')
    expect(jsonLd.url).toBe(url)
    expect(jsonLd.name).toContain(PUBLIC_RECORD.name)
    // No provider is invented: the snapshot names no awarding body, so the
    // structured data must not fabricate one from the country.
    expect(jsonLd.provider).toBeUndefined()
  })

  it('returns a real 404 for an id that is not a public record', async () => {
    stubFetch()
    const response = await serve(`${ORIGIN}/scholarships/${UNKNOWN_ID}`)
    expect(response.status).toBe(404)
    const html = await response.text()
    expect(html).toMatch(/name="robots"\s+content="noindex/i)
    expect(canonicalOf(html)).toBe(`${ORIGIN}/scholarships`)
  })

  it('does not claim /countries is a page, because the design has none', async () => {
    stubFetch()
    // The approved design is a single-page finder with no countries
    // section, so the middleware must pass the route through rather than
    // stamp a canonical onto a shell that duplicates the homepage.
    expect(await serve(`${ORIGIN}/countries`)).toBeUndefined()
    expect(await serve(`${ORIGIN}/countries/germany`)).toBeUndefined()
  })
})

describe('the rewrite leaves the approved design untouched', () => {
  it('preserves every style block, font and script on a detail route', async () => {
    stubFetch()
    const response = await serve(`${ORIGIN}/scholarships/${PUBLIC_ID}`)
    const html = await response.text()

    const stylesBefore = (INDEX_HTML.match(/<style/g) || []).length
    const stylesAfter = (html.match(/<style/g) || []).length
    expect(stylesAfter).toBe(stylesBefore)

    expect(html).toContain('family=Inter')
    expect(html).toContain('family=Newsreader')
    expect(html).toContain('.pp{')
    expect(html).toContain('scholarships-snapshot.json')
    expect(html).not.toContain('id="root"')
  })

  it('keeps the verification token and the SEO markers through the rewrite', async () => {
    stubFetch()
    const response = await serve(`${ORIGIN}/scholarships/${PUBLIC_ID}`)
    const html = await response.text()
    expect(html).toContain(VERIFICATION_TOKEN)
    const tags = [...html.matchAll(/<(meta|link)\b[^>]*>/gi)].map((m) => m[0])
    const seoTags = tags.filter((tag) =>
      /og:|twitter:|robots|description|canonical/.test(tag)
    )
    for (const tag of seoTags) {
      expect(tag).toContain('data-sz-seo="true"')
    }
  })
})

describe('the public record under test is real', () => {
  it('is a public record the catalogue will serve', () => {
    expect(PUBLIC_RECORD).toBeTruthy()
    expect(PUBLIC_RECORD.status).not.toBe('closed')
    expect(RECORDS.some((entry) => Number(entry.id) === UNKNOWN_ID)).toBe(false)
  })
})
