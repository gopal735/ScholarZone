/**
 * Canonical origin for SEO output.
 *
 * Canonical URLs, the sitemap host, robots.txt and JSON-LD must all agree, and
 * they must not be changed ahead of production validation. The current canonical
 * host is therefore the default here, so building today produces byte-identical
 * SEO output. Once the Vercel deployment is proven, setting
 * VITE_CANONICAL_ORIGIN in that project's environment switches every consumer to
 * the new host in one place rather than by editing four pages.
 */
export const CANONICAL_ORIGIN = (
  import.meta.env.VITE_CANONICAL_ORIGIN || 'https://gopal735.github.io/ScholarZone'
).replace(/\/$/, '')
