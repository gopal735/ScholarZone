import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // The GitHub Pages build lives under a repository path, while a Vercel build
  // is served from the root. The base is therefore derived from the deployment
  // target rather than hardcoded, so moving hosts does not silently break every
  // asset URL. GitHub Pages stays the rollback target, so its value is the
  // default and behaviour is unchanged until VITE_DEPLOY_TARGET says otherwise.
  const env = loadEnv(mode, process.cwd(), '')
  const isVercel = env.VITE_DEPLOY_TARGET === 'vercel'

  return {
    plugins: [react()],
    base: isVercel ? '/' : '/ScholarZone/',
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  }
})
