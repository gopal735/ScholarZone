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
 * while the app is served from `https://visionary-cactus-600b38.netlify.app`.
 * Each file was internally consistent and the set was not, so the site
 * advertised URLs on a host that does not serve the catalogue, and told crawlers
 * to consolidate onto it. No single-file test would ever have caught that.
 *
 * The same disagreement recurred once already. The canonical origin was moved to
 * `https://scholarzone-fwzj.vercel.app` while the frontend's primary production
 * deploy from master runs on Netlify. The Vercel project stayed live as a mirror
 * and as the API host, so the set looked
 * plausible and still named a host that is not the primary frontend.
 *
 * It then recurred a third time in a subtler way, and that one is why the
 * literal below names a live host rather than the project's old subdomain. The
 * default was left on the Netlify project's default subdomain after the site was
 * published at `https://schollarzone.netlify.app`, and that subdomain now
 * returns HTTP 404. Every artefact still agreed with each other and with this
 * test, and the site advertised a host that serves nothing at all. The
 * assertions below are therefore driven by CANONICAL_ORIGIN rather than by a
 * literal, so a future move is one deliberate change plus this file's
 * expectation, not a silent four-file drift.
 */
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { CANONICAL_ORIGIN } from './services/canonicalOrigin.js'

const read = (relative) =>
  readFileSync(new URL(relative, import.meta.url), 'utf8')

const ROBOTS = read('../public/robots.txt')
const SITEMAP = read('../public/sitemap.xml')
const INDEX_HTML = read('../index.html')
const SNAPSHOT = JSON.parse(read('../public/scholarships-snapshot.json'))

const locs = [...SITEMAP.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1])

// The public ids the deployed frontend can actually resolve. The detail page
// reads the bundled snapshot and turns a miss into a 404, so a sitemap entry
// for an id the snapshot does not carry is a soft-404 rather than a page.
const SNAPSHOT_IDS = new Set(
  (SNAPSHOT.scholarships || []).map((s) => String(s.id))
)

/**
 * The Google Search Console ownership tokens that must survive into the built
 * document. Google fetches the served URL with a plain GET and reads the token
 * out of the head, so a token that is absent, duplicated or injected at runtime
 * is a property that cannot verify itself.
 */
const VERIFICATION_TOKENS = [
  'mzaQ_MW4nVgMwHhbSOxxTsr46gaV7sanks7vbnE7aaE',
  '5ZF6ps7latuMDIU2UQgz68yePIZy2gw_klo_bQbkhds',
]

describe('canonical origin', () => {
  it('is the published production host, not the legacy deployment', () => {
    // The host the Netlify deployment actually answers on. The previous default
    // was that project's default subdomain, which now returns HTTP 404, so this
    // assertion is what stops the set drifting back onto a host that serves
    // nothing.
    expect(CANONICAL_ORIGIN).toBe('https://schollarzone.netlify.app')
    expect(CANONICAL_ORIGIN).not.toContain('github.io')
  })

  it('names no host that is a mirror, an API-only deployment, or a dead host', () => {
    // The Vercel project still serves the frontend and hosts the API under
    // /api. Advertising it as canonical would consolidate every page onto the
    // mirror, which is the defect the previous default introduced. The
    // visionary-cactus-600b38 subdomain is excluded because it no longer
    // resolves: naming it publishes canonicals nothing can fetch.
    expect(CANONICAL_ORIGIN).not.toContain('vercel.app')
    expect(CANONICAL_ORIGIN).not.toContain('visionary-cactus-600b38')
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

  it('advertises no detail url the deployed snapshot cannot resolve', () => {
    // 21 sitemap entries named records the free-first snapshot no longer
    // carries. Each one resolved to the shell's not-found state on the public
    // site, so the sitemap was advertising 21 soft-404s.
    const unresolvable = locs
      .filter((loc) => /\/scholarships\/\d+$/.test(loc))
      .map((loc) => loc.match(/\/scholarships\/(\d+)$/)[1])
      .filter((id) => !SNAPSHOT_IDS.has(id))
    expect(unresolvable).toEqual([])
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
    //
    // The link tag is matched as a whole element rather than as one literal
    // string, because the requirement is about the document and not about how
    // the author happened to wrap the attributes. A single-line regex silently
    // returned undefined for the multi-line tag this file ships, which is the
    // same as the tag being absent: a false "missing" that would have been
    // "fixed" by reformatting the HTML rather than by anything about SEO.
    const canonicalTag = [...INDEX_HTML.matchAll(/<link\b[^>]*>/g)]
      .map((match) => match[0])
      .find((tag) => /\brel=("|')canonical\1/.test(tag))
    const canonical = canonicalTag?.match(/\bhref=("|')([^"']+)\1/)?.[2]
    expect(canonicalTag).toBeTruthy()
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

  it('names no host other than the canonical one', () => {
    // The previous canonical host is still live as a mirror. Leaving it in the
    // served document - a canonical, an og:url or a JSON-LD url - puts a second
    // origin in front of the crawler, which is exactly the disagreement the
    // canonical link exists to prevent.
    //
    // Scoped to the attributes that declare where the page lives, not to every
    // URL in the file: the head legitimately preconnects to the font CDN and
    // the sitemap carries its XML namespace. Neither is a site origin.
    const seoUrlSources = [
      ...[...INDEX_HTML.matchAll(/<link\s+rel="canonical"\s+href="([^"]+)"/g)].map((m) => m[1]),
      ...[...INDEX_HTML.matchAll(/<meta\s+property="og:url"\s+content="([^"]+)"/g)].map((m) => m[1]),
      ...[...INDEX_HTML.matchAll(/<meta\s+property="og:image"\s+content="([^"]+)"/g)].map((m) => m[1]),
      ...[...INDEX_HTML.matchAll(/<script type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/g)]
        .flatMap((m) => [...JSON.stringify(JSON.parse(m[1])).matchAll(/https?:\/\/[a-z0-9.-]+/gi)].map((u) => u[0])),
      ...locs,
      ...(ROBOTS.match(/^Sitemap:\s*(\S+)$/m) ? [ROBOTS.match(/^Sitemap:\s*(\S+)$/m)[1]] : []),
    ]
    const foreign = seoUrlSources
      .filter((url) => /^https?:\/\//.test(url))
      .map((url) => url.match(/^https?:\/\/[^/?#]+/)[0].replace(/\/$/, ''))
      .filter((origin) => origin !== CANONICAL_ORIGIN && origin !== 'https://schema.org')
    expect([...new Set(foreign)]).toEqual([])
  })
})

describe('Google Search Console verification tokens', () => {
  const tokenTags = (html) =>
    [...html.matchAll(/<meta\s+name="google-site-verification"[^>]*>/g)].map((m) => m[0])

  it('ships both tokens in the source document', () => {
    const tags = tokenTags(INDEX_HTML)
    const contents = tags.map((tag) => tag.match(/content="([^"]+)"/)?.[1])
    expect(contents).toEqual(expect.arrayContaining(VERIFICATION_TOKENS))
  })

  it('ships each token exactly once', () => {
    // A duplicate tag is not a harmless redundancy: Google reads the first
    // match and ignores the rest, so a second copy of the same token is dead
    // markup that looks like coverage.
    for (const token of VERIFICATION_TOKENS) {
      const count = tokenTags(INDEX_HTML).filter((tag) => tag.includes(`content="${token}"`)).length
      expect(count, `token ${token} appears ${count} times`).toBe(1)
    }
  })

  it('places the tokens inside head, so they are in the raw HTTP response', () => {
    // Google performs an ordinary GET and parses the head. A token placed after
    // the root div, or injected by a page effect, is invisible to that fetch.
    const head = INDEX_HTML.slice(INDEX_HTML.indexOf('<head>'), INDEX_HTML.indexOf('</head>'))
    expect(head).toContain('<head>')
    for (const token of VERIFICATION_TOKENS) {
      expect(head, `token ${token} is outside the head`).toContain(`content="${token}"`)
      expect(INDEX_HTML.slice(INDEX_HTML.indexOf('</head>'))).not.toContain(`content="${token}"`)
    }
  })

  it('does not mark the tokens data-sz-seo, so no page effect can remove them', () => {
    // Every page effect in this app opens by deleting every [data-sz-seo] node
    // before writing its own. Marking a token would delete it on the first
    // render of every route, and the property would stop verifying itself.
    for (const tag of tokenTags(INDEX_HTML)) {
      expect(tag).not.toContain('data-sz-seo')
    }
  })

  it('survives the runtime SEO sweep that deletes [data-sz-seo] nodes', () => {
    // The failure this pins is a runtime deletion, not a missing tag: the tag
    // is present in the document and gone by the time anything renders.
    document.head.innerHTML = INDEX_HTML
      .slice(INDEX_HTML.indexOf('<head>') + '<head>'.length, INDEX_HTML.indexOf('</head>'))
    for (const node of [...document.head.querySelectorAll('[data-sz-seo]')]) {
      node.remove()
    }
    for (const token of VERIFICATION_TOKENS) {
      expect(
        document.head.querySelector(`meta[name="google-site-verification"][content="${token}"]`),
        `token ${token} was removed at runtime`
      ).not.toBeNull()
    }
  })

  it('is not swept up by the SEO tag matcher the head contract uses', () => {
    // The contract above asserts every og/twitter/robots/description/canonical
    // tag carries data-sz-seo. A token that ever matched that pattern would be
    // forced to carry the attribute that gets it deleted.
    const seoTags = tokenTags(INDEX_HTML).filter((tag) =>
      /og:|twitter:|robots|description|canonical/.test(tag)
    )
    expect(seoTags).toEqual([])
  })
})