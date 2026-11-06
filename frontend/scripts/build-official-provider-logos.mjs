import { readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url))
const repositoryRoot = path.resolve(scriptDirectory, '..', '..')
const sourcePath = path.join(repositoryRoot, 'backend', 'config', 'official_logo_overrides.json')
const outputPath = path.join(scriptDirectory, '..', 'src', 'data', 'officialProviderLogos.json')

const overrides = JSON.parse(await readFile(sourcePath, 'utf8'))
const logos = Object.fromEntries(
  Object.entries(overrides)
    .filter(([host, logo]) =>
      !host.startsWith('_') &&
      logo?.validation_result === 'verified' &&
      logo?.image_kind === 'official_logo' &&
      logo?.official_host === true &&
      typeof logo?.url === 'string' &&
      /^https:\/\//i.test(logo.url),
    )
    .map(([host, logo]) => [
      host.toLowerCase().replace(/^www\./, ''),
      { url: logo.url, altText: logo.alt_text },
    ]),
)

await writeFile(outputPath, `${JSON.stringify(logos, null, 2)}\n`, 'utf8')
console.log(`Generated ${Object.keys(logos).length} verified official provider logos.`)
