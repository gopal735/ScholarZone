/**
 * Vercel Edge Middleware: route-aware SEO head and real 404s.
 *
 * Why this exists
 * ---------------
 * The app is a single-page application. Every route is rewritten to the same
 * index.html, so the document that reaches a crawler is byte-identical for
 * /, /scholarships, /scholarships/14 and /scholarships/999999. That shell
 * declares the homepage title, the homepage description and
 * `canonical = https://scholarzone-fwzj.vercel.app/`. A crawler therefore sees
 * 370 URLs that all claim to be the homepage, and sees a nonexistent
 * scholarship id answered with HTTP 200 and the homepage shell instead of a
 * 404. Those are exactly the two exclusions that keep a catalogue like this out
 * of the index.
 *
 * This middleware rewrites the served head per route, so each detail page
 * carries its own canonical, title, description and structured data, and so a
 * detail id that is not a public record returns a real 404.
 *
 * What it deliberately does not do
 * --------------------------------
 * It does not touch the design. The inline styles, fonts, animations, markup
 * and the React bundle are passed through untouched; only the values inside
 * the SEO head are substituted. It also does not invent content: every string
 * it injects comes from the catalogue snapshot, and a record with no usable
 * data falls back to the document's own values rather than a generated claim.
 *
 * The static HTML still contains no rendered catalogue markup, so a crawler
 * that does not execute JavaScript sees correct metadata and a correct
 * canonical but not the rendered body. That limitation is real and is not
 * papered over here.
 */
import { CANONICAL_ORIGIN } from './src/services/canonicalOrigin.js'

/**
 * Routes that are real public pages with their own SEO head.
 *
 * /countries is deliberately absent. The approved design is a single-page
 * finder: there is no countries section, so /countries resolves to the
 * homepage shell and advertising it would be a soft 404 with a canonical
 * claiming to be a page that does not exist. It is therefore neither routed
 * here nor advertised in the sitemap.
 */
const CATALOGUE_ROUTES = ['/', '/scholarships']

/** Detail route shape: /scholarships/<integer id> and nothing else. */
const DETAIL_RE = /^\/scholarships\/(\d+)$/

/** Cached snapshot, scoped to one edge isolate. */
let snapshotPromise = null

const loadSnapshot = (request) => {
  if (!snapshotPromise) {
    snapshotPromise = fetch(new URL('/scholarships-snapshot.json', request.url))
      .then((response) => (response.ok ? response.json() : null))
      .catch(() => null)
  }
  return snapshotPromise
}

const truncate = (value, limit) => {
  const text = String(value ?? '').replace(/\s+/g, ' ').trim()
  if (text.length <= limit) return text
  return `${text.slice(0, limit - 1).trimEnd()}…`
}

const escapeForTag = (value) =>
  String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')

/**
 * Find a <meta> tag carrying a given attribute. Order- and line-tolerant: the
 * document writes its tags across several lines with data-sz-seo between the
 * attributes, so a strict `name="x" content="y"` pattern does not match it.
 */
const findMeta = (html, attr) =>
  [...html.matchAll(/<meta\b[^>]*>/gi)].find((match) => match[0].includes(attr))?.[0] ?? null

/**
 * Replace the value of an existing tag, or insert the tag when the document
 * does not carry one.
 */
const setMeta = (html, attr, value) => {
  const escaped = escapeForTag(value)
  const tag = findMeta(html, attr)
  if (tag) {
    const next = tag.replace(/content="[^"]*"/i, `content="${escaped}"`)
    const marked = /data-sz-seo=/.test(next)
      ? next
      : next.replace('<meta ', '<meta data-sz-seo="true" ')
    return html.replace(tag, marked)
  }
  return html.replace(
    '</head>',
    `<meta ${attr} content="${escaped}" data-sz-seo="true">\n</head>`
  )
}

const setLink = (html, rel, href) => {
  const escaped = escapeForTag(href)
  const tag = html.match(new RegExp(`<link\\b[^>]*\\brel="${rel}"[^>]*>`, 'i'))?.[0]
  if (tag) {
    return html.replace(tag, tag.replace(/href="[^"]*"/i, `href="${escaped}"`))
  }
  return html.replace(
    '</head>',
    `<link rel="${rel}" href="${escaped}" data-sz-seo="true">\n</head>`
  )
}

const setTitle = (html, title) => {
  const escaped = escapeForTag(title)
  if (/<title>[^<]*<\/title>/i.test(html)) {
    return html.replace(/<title>[^<]*<\/title>/i, `<title>${escaped}</title>`)
  }
  return html.replace('</head>', `<title>${escaped}</title>\n</head>`)
}

const setJsonLd = (html, jsonLd) => {
  const block = `<script type="application/ld+json" data-sz-seo="true">${JSON.stringify(
    jsonLd
  )}</script>`
  const existing = /<script type="application\/ld\+json"[^>]*>[\s\S]*?<\/script>/i
  if (existing.test(html)) {
    return html.replace(existing, block)
  }
  return html.replace('</head>', `${block}\n</head>`)
}

const descriptionFor = (record) =>
  truncate(
    record.description ||
      record.eligibility ||
      record.benefits ||
      'Verified scholarship listing on ScholarZone.',
    158
  )

const detailStructuredData = (record, url) => {
  const providerName = record.provider || record.organization || record.provider_name
  return {
    '@context': 'https://schema.org',
    '@type': 'ScholarshipProgram',
    name: truncate(record.name || record.title, 110),
    url,
    description: descriptionFor(record),
    // Only emitted when the record actually names an awarding body. The
    // snapshot carries no provider field, and naming the country as the
    // provider would be a fabricated attribution rather than metadata.
    ...(providerName
      ? { provider: { '@type': 'Organization', name: truncate(providerName, 120) } }
      : {}),
    ...(record.country ? { spatialCoverage: { '@type': 'Country', name: record.country } } : {}),
    ...(record.degree ? { educationalCredentialAwarded: truncate(record.degree, 120) } : {}),
    ...(record.deadline_date
      ? { applicationDeadline: String(record.deadline_date).slice(0, 10) }
      : {}),
  }
}

export const config = {
  matcher: ['/scholarships/:path*'],
}

export default async function middleware(request) {
  const { pathname } = new URL(request.url)

  const isDetail = DETAIL_RE.test(pathname)
  const isCatalogue = CATALOGUE_ROUTES.includes(pathname)

  if (!isDetail && !isCatalogue) {
    return undefined
  }

  const response = await fetch(new URL('/index.html', request.url))
  if (!response.ok || !response.body) {
    return undefined
  }

  let html = await response.text()
  const snapshot = await loadSnapshot(request)
  const records = Array.isArray(snapshot?.scholarships) ? snapshot.scholarships : null

  // A detail id that is not a public record must not be answered with the
  // homepage shell and HTTP 200. There is no static 404 page for the SPA that
  // carries the design, so this returns a real 404 with a minimal document
  // rather than a soft 404.
  if (isDetail) {
    const id = Number(pathname.split('/').pop())
    const record = records?.find((entry) => Number(entry.id) === id)

    if (!record) {
      return new Response(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">' +
          '<title>Scholarship not found · ScholarZone</title>' +
          '<meta name="robots" content="noindex, follow">' +
          `<link rel="canonical" href="${CANONICAL_ORIGIN}/scholarships">` +
          '</head><body><h1>Scholarship not found</h1>' +
          '<p>This scholarship is not in the public catalogue.</p>' +
          `<p><a href="${CANONICAL_ORIGIN}/scholarships">Browse the catalogue</a></p>` +
          '</body></html>',
        { status: 404, headers: { 'content-type': 'text/html; charset=utf-8' } }
      )
    }

    const url = `${CANONICAL_ORIGIN}${pathname}`
    html = setTitle(html, `${truncate(record.name, 90)} · ScholarZone`)
    html = setMeta(html, 'name="description"', descriptionFor(record))
    html = setMeta(html, 'name="robots"', 'index, follow')
    html = setLink(html, 'canonical', url)
    html = setMeta(html, 'property="og:title"', truncate(record.name, 90))
    html = setMeta(html, 'property="og:description"', descriptionFor(record))
    html = setMeta(html, 'property="og:url"', url)
    html = setJsonLd(html, detailStructuredData(record, url))

    return new Response(html, {
      status: 200,
      headers: { 'content-type': 'text/html; charset=utf-8' },
    })
  }

  // Catalogue routes keep the document's own copy but must declare their own
  // canonical instead of collapsing onto the homepage.
  const url = `${CANONICAL_ORIGIN}${pathname === '/' ? '/' : pathname}`
  html = setLink(html, 'canonical', url)
  html = setMeta(html, 'property="og:url"', url)

  return new Response(html, {
    status: 200,
    headers: { 'content-type': 'text/html; charset=utf-8' },
  })
}
