# Zero-Paid Architecture - Provider Limits

## GitHub Pages (Frontend Hosting)
- **Build minutes**: Unlimited for public repos
- **Storage**: 1 GB per repo (soft limit)
- **Bandwidth**: 100 GB/month (soft limit)
- **Custom domains**: Supported (free)
- **HTTPS**: Automatic (free)
- **Limitations**: Static sites only, no server-side code

## Cloudflare Pages (Alternative Frontend Hosting)
- **Build minutes**: 500/month free
- **Build concurrency**: 1 concurrent build
- **Storage**: Unlimited for assets
- **Bandwidth**: Unlimited (fair use)
- **Custom domains**: Supported (free)
- **HTTPS**: Automatic (free)
- **Functions**: 100,000 requests/day free (Pages Functions)
- **Limitations**: Build time limit 20 min, 1 build at a time

## GitHub Actions (CI/CD & Scheduled Jobs)
- **Public repos**: Unlimited minutes
- **Private repos**: 2,000 minutes/month free
- **Concurrent jobs**: 20 (public), varies (private)
- **Scheduled workflows**: Can be delayed by platform load, disabled after 60 days inactivity
- **Artifact storage**: 90 days retention, 500 MB/repo
- **Self-hosted runners**: Unlimited

## Neon PostgreSQL (Database - Current)
- **Free tier**: 0.5 GB storage, 190 compute hours/month
- **Branching**: 10 branches
- **Point-in-time restore**: 7 days
- **Limitations**: Auto-suspend after 5 min inactivity, cold start ~1-5s
- **Paid features**: Larger storage, more compute hours, no auto-suspend, read replicas

## GitHub Container Registry / Docker Hub
- **GHCR**: 500 MB free, then $0.008/GB/day
- **Docker Hub**: 1 private repo free, rate limits on pulls

## Cloudflare Workers (Alternative Backless API)
- **Free tier**: 100,000 requests/day
- **CPU time**: 10 ms/request
- **Duration**: 30 seconds max
- **KV storage**: 1 GB free
- **D1 (SQLite)**: 5 GB free
- **R2 (Object storage)**: 10 GB free

## Resend (Email - Current)
- **Free tier**: 3,000 emails/month
- **Rate limit**: 2 requests/second
- **Paid**: $20/month for 50,000 emails

## Verdict
- Frontend: GitHub Pages or Cloudflare Pages - both genuinely free for static sites
- Database: Neon free tier has compute hour limits - static snapshot removes this dependency for public browsing
- Backend API: Current host free tier sleeps - acceptable for admin/match features
- Email: Resend free tier sufficient for verification emails
- Scheduled maintenance: GitHub Actions cron - free but can be delayed/disabled