import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: { 
        ecmaVersion: 2022,
        ecmaFeatures: { jsx: true },
        sourceType: 'module'
      },
    },
  },
  // Build tooling runs in Node, not the browser. vite.config.js reads
  // process.cwd() to decide whether the deployment target is GitHub Pages or a
  // root-hosted platform, and a browser-only global list flags it as undefined -
  // which is a true statement about the browser and a false one about the file.
  // Scoped to tooling so application code is still held to browser globals.
  {
    files: ['vite.config.js', 'eslint.config.js', 'scripts/**/*.{js,mjs,cjs}'],
    languageOptions: {
      globals: { ...globals.node },
    },
  },
])
