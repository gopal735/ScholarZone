/**
 * The crawl contract for the public site, asserted as one file.
 *
 * Every assertion here corresponds to a defect that was actually live in
 * production, because these three artefacts - the canonical origin the app
 * stamps into every page, robots.txt, and sitemap.xml - are generated separately
 * and shipped separately, so nothing in the build was checking that they agreed.
 *
 * The failure they had in common is the important part. robots.txt, sitemap.xml
 * and every canonical link all named `https://gopal735.github.io/ScholarZone`,
 * while the app is served from `https://scholarzone-fwzj.vercel.app`. Each file
 * was internally consistent and the set was not, so the site advertised URLs on
 * a host that does not serve the catalogue, and told crawlers to consolidate
 * onto it. No single-file test would ever have caught that.
 */
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { CANONICAL_ORIGIN } from './services/canonicalOrigin.js'

const read = (relative) =>
  readFileSync(new URL(relative, import.meta.url), 'utf8')

const ROBOTS = read('../public/robots.txt')
const SITEMAP = read('../public/sitemap.xml')
const INDEX_HTML = read('../index.html')

const locs = [...SITEMAP.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1])

describe('canonical origin', () => {
  it('is the canonical production host, not the legacy deployment', () => {
    expect(CANONICAL_ORIGIN).toBe('https://scholarzone-fwzj.vercel.app')
    expect(CANONICAL_ORIGIN).not.toContain('github.io')
  })

  it('has no trailing slash, so path joining cannot produce a double slash', () => {
    expect(CANONICAL_ORIGIN.endsWith('/')).toBe(false)
  })
})

describe('robots.txt', () => {
  it('points at the sitemap on the canonical host', () => {
    const declared = ROBOTS.match(/^Sitemap:\s*(\S+)$/m)?.[1]
    expect(declared).toBe(`${CANONICAL_ORIGIN}/sitemap.xml`)
  })

  it('writes its rules for the deployed base path, not the legacy project-page base', () => {
    // Every prefixed rule silently matched nothing on the canonical host, so
    // /admin was never actually blocked while the file claimed it was.
    expect(ROBOTS).not.toContain('/ScholarZone')
  })

  it('blocks the private and per-user surfaces', () => {
    for (const path of ['/admin', '/dashboard', '/applications', '/login', '/register', '/saved', '/compare', '/api/']) {
      expect(ROBOTS).toMatch(new RegExp(`^Disallow:\\s*${path.replace(/\/$/, '\\/')}\\s*$`, 'm'))
    }
  })

  it('blocks filter, search, sort and pagination variants', () => {
    expect(ROBOTS).toMatch(/^Disallow:\s*\/\*\?\*\s*$/m)
  })

  it('does not block the pages that are the product', () => {
    expect(ROBOTS).not.toMatch(/^Disallow:\s*\/(scholarships|countries|match|mentor)/m)
  })

  it('does not block the render-blocking assets the pages need', () => {
    expect(ROBOTS).not.toMatch(/^Disallow:.*\.(css|js)$/m)
  })
})

describe('sitemap.xml', () => {
  it('is well formed and advertises at least one url', () => {
    expect(SITEMAP).toMatch(/^<\?xml version="1\.0" encoding="UTF-8"\?>/)
    expect(SITEMAP).toContain('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    expect(SITEMAP.trimEnd().endsWith('</urlset>')).toBe(true)
    expect(locs.length).toBeGreaterThan(0)
  })

  it('puts every url on the canonical host', () => {
    const foreign = locs.filter((loc) => !loc.startsWith(`${CANONICAL_ORIGIN}/`))
    expect(foreign).toEqual([])
  })

  it('advertises no filtered or paginated variants', () => {
    expect(locs.filter((loc) => loc.includes('?'))).toEqual([])
  })

  it('has no duplicate urls', () => {
    expect(locs.length).toBe(new Set(locs).size)
  })

  it('advertises no private, admin or api surface', () => {
    const privatePaths = locs.filter((loc) => /\/(admin|dashboard|applications|login|register|saved|compare|match|mentor|api)(\/|$)/.test(loc))
    expect(privatePaths).toEqual([])
  })

  it('covers the indexable routes the router actually serves', () => {
    // These three are the only non-detail routes in App.jsx that are public.
    expect(locs).toContain(`${CANONICAL_ORIGIN}/`)
    expect(locs).toContain(`${CANONICAL_ORIGIN}/scholarships`)
    expect(locs).toContain(`${CANONICAL_ORIGIN}/countries`)
  })

  it('covers more scholarship detail urls than any single catalogue page can show', () => {
    // useScholarshipDirectory fetches limit=100, and the directory paginates at
    // 12. A sitemap no larger than one catalogue page would leave the rest of
    // the catalogue reachable only by clicking.
    const detail = locs.filter((loc) => /\/scholarships\/\d+$/.test(loc))
    expect(detail.length).toBeGreaterThan(100)
  })
})

describe('the served document', () => {
  it('carries a canonical for the homepage before any script runs', () => {
    // A crawler receives this HTML first. With an empty <div id="root"> and no
    // head metadata, everything indexable depended on the bundle running.
    const canonical = INDEX_HTML.match(/<link rel="canonical" href="([^"]+)"/)?.[1]
    expect(canonical).toBe(`${CANONICAL_ORIGIN}/`)
  })

  it('carries a description and an indexing directive before any script runs', () => {
    expect(INDEX_HTML).toMatch(/<meta\s+name="description"[\s\S]*?content="[^"]{50,}"/)
    expect(INDEX_HTML).toMatch(/<meta\s+name="robots"\s+content="index, follow"/)
  })

  it('carries WebSite structured data before any script runs', () => {
    const block = INDEX_HTML.match(/<script type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/)?.[1]
    expect(block).toBeTruthy()
    const parsed = JSON.parse(block)
    expect(parsed['@type']).toBe('WebSite')
    expect(parsed.url).toBe(`${CANONICAL_ORIGIN}/`)
  })

  it('marks every head tag it ships so the runtime replaces rather than duplicates it', () => {
    const tags = [...INDEX_HTML.matchAll(/<(meta|link)\b[^>]*>/g)].map((m) => m[0])
    const seoTags = tags.filter((tag) => /og:|twitter:|robots|description|canonical/.test(tag))
    expect(seoTags.length).toBeGreaterThan(0)
    for (const tag of seoTags) {
      expect(tag).toContain('data-sz-seo="true"')
    }
  })

  it('names no asset the build does not produce', () => {
    // The project ships no social preview image, so an og:image pointing at one
    // is a broken reference rather than metadata.
    expect(INDEX_HTML).not.toContain('og-image')
    expect(INDEX_HTML).not.toContain('og:image')
  })

  it('does not carry the legacy host anywhere', () => {
    for (const [name, content] of [['index.html', INDEX_HTML], ['robots.txt', ROBOTS], ['sitemap.xml', SITEMAP]]) {
      expect(content, `${name} still names the legacy host`).not.toContain('github.io')
    }
  })
})