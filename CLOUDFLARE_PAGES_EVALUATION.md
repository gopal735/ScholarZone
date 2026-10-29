# Cloudflare Pages Configuration for ScholarZone

## Project Settings
- **Project name**: scholarzone
- **Production branch**: master
- **Build command**: `cd frontend && npm run build`
- **Build output directory**: `frontend/dist`
- **Root directory**: `/` (repository root)

## Environment Variables (Production)
```
VITE_API_BASE_URL = https://scholarzone-api.example.com/api
VITE_CANONICAL_ORIGIN = https://scholarzone.example.com
VITE_DEPLOY_TARGET = cloudflare-pages
VITE_STATIC_CATALOGUE = true
```

## Environment Variables (Preview)
```
VITE_API_BASE_URL = https://scholarzone-api-staging.example.com/api
VITE_CANONICAL_ORIGIN = https://preview-scholarzone.pages.dev
VITE_DEPLOY_TARGET = cloudflare-pages
VITE_STATIC_CATALOGUE = true
```

## Build Configuration (wrangler.toml)
See `wrangler.toml` in this directory.

## Redirects (_redirects)
```
/*    /index.html   200
```

## Headers (_headers)
```
/*
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()

/scholarships-snapshot.json
  Cache-Control: public, max-age=3600, stale-while-revalidate=86400

/sitemap.xml
  Cache-Control: public, max-age=86400

/assets/*
  Cache-Control: public, max-age=31536000, immutable

/*.js
  Cache-Control: public, max-age=31536000, immutable

/*.css
  Cache-Control: public, max-age=31536000, immutable

/*.woff2
  Cache-Control: public, max-age=31536000, immutable
```

## Limits & Considerations

### Free Tier Limits (as of 2024)
| Resource | Limit |
|----------|-------|
| Builds/month | 500 |
| Concurrent builds | 1 |
| Build time | 20 minutes |
| Requests/month | Unlimited (fair use) |
| Bandwidth | Unlimited (fair use) |
| Custom domains | Unlimited |
| Pages Functions | 100,000 requests/day |
| Functions CPU time | 10 ms/request |
| Functions duration | 30 seconds |
| KV namespace | 1 GB |
| D1 database | 5 GB |
| R2 storage | 10 GB |

### Advantages over GitHub Pages
1. **No Jekyll processing** - pure static hosting
2. **Better cache control** - custom headers per path
3. **Pages Functions** - optional serverless functions for dynamic features
4. **Instant cache purge** - via API or dashboard
5. **Preview deployments** - automatic for every PR
6. **No bandwidth limits** - truly unlimited (fair use)
7. **Edge network** - 300+ locations worldwide

### Disadvantages
1. **Build minute limit** - 500/month (but we only build on master pushes)
2. **Concurrent build limit** - 1 at a time
3. **No GitHub Pages integration** - separate platform
4. **Functions not needed** - our static catalogue doesn't need them

## Migration Plan
1. Create Cloudflare Pages project connected to GitHub repo
2. Configure build settings as above
3. Add custom domain (scholarzone.example.com)
4. Test preview deployments
5. Switch DNS from GitHub Pages to Cloudflare Pages
6. Keep GitHub Pages as backup (can be re-enabled instantly)

## Cost Analysis
- **GitHub Pages**: $0 (unlimited for public repos)
- **Cloudflare Pages**: $0 (within free tier limits for our use case)
- **Both are genuinely free** - no hidden costs for static hosting

## Recommendation
Keep GitHub Pages as primary (already configured, working, truly unlimited for public repos).
Cloudflare Pages is a viable alternative with better cache control and edge performance,
but offers no significant advantage for our static-first architecture.
The build minute limit (500/month) is sufficient for ~16 builds/day, which is more than enough.