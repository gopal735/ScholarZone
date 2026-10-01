import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // The GitHub Pages build lives under a repository path, while a Vercel build
  // is served from the root. The base is therefore derived from the deployment
  // target rather than hardcoded, so moving hosts does not silently break every
  // asset URL.
  //
  // Vercel is detected from VERCEL, which the platform sets on every build,
  // rather than only from VITE_DEPLOY_TARGET. Requiring an env var that someone
  // has to remember to add is what served this build a blank white page: with
  // base left at /ScholarZone/, every asset URL resolved one directory too deep
  // on a root domain, the entry script 404ed, and nothing rendered. The explicit
  // variable still wins so a deliberate override is possible.
  //
  // loadEnv reads from this file's directory rather than process.cwd(), which
  // under a multi-service build is the service root and not guaranteed to be the
  // frontend directory.
  const projectDir = fileURLToPath(new URL('.', import.meta.url))
  const env = loadEnv(mode, projectDir, '')
  const isVercel =
    env.VITE_DEPLOY_TARGET === 'vercel' ||
    process.env.VERCEL === '1' ||
    process.env.VERCEL === 'true'

  return {
    plugins: [react()],
    base: isVercel ? '/' : '/ScholarZone/',
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': {
          target: 'http://0.0.0.0:8000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  }
})