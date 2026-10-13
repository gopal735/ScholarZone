// Preview server for the strategist E2E spec.
//
// Self-contained and cross-platform: it builds the frontend with the strategist
// flag ON (so the flag-gated route exists) and then serves the production build on
// a fixed port. Playwright's webServer runs this, waits for the port, and kills it
// when the run ends. The spec navigates with ?fixture=1 so it renders captured data
// deterministically without the (separately flag-gated) backend.
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

// Always build/serve from the frontend package root, regardless of the caller's cwd.
process.chdir(join(dirname(fileURLToPath(import.meta.url)), '..'))

const run = (cmd, args, env) =>
  new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { env, stdio: 'inherit', shell: true })
    child.on('exit', (code) => (code === 0 ? resolve() : reject(new Error(`${cmd} exited ${code}`))))
    child.on('error', reject)
  })

const env = { ...process.env, VITE_STRATEGIST_ENABLED: 'true' }

try {
  await run('npx', ['vite', 'build'], env)
} catch {
  process.exit(1)
}

const preview = spawn('npx', ['vite', 'preview', '--port', '4173', '--strictPort'], {
  env, stdio: 'inherit', shell: true,
})
preview.on('error', (e) => process.exit(1))
preview.on('exit', (code) => process.exit(code ?? 0))
for (const signal of ['SIGTERM', 'SIGINT']) {
  process.on(signal, () => preview.kill(signal))
}
