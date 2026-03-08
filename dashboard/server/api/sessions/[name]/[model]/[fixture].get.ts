import { readdirSync, readFileSync, existsSync } from 'node:fs'
import { resolve, join } from 'node:path'

const PUBLISHED_DIR = resolve(process.cwd(), '../results/published')

const FIXTURE_LABELS: Record<string, string> = {
  'nuxt-form-oneshot':         'A — Single-shot',
  'nuxt-form-agent-guided':    'B — Agent guided',
  'nuxt-form-agent-twofiles':  'C — Agent two files',
  'nuxt-form-agent-rag':       'D — Agent + RAG',
  'nuxt-form-agent-full':      'E — Agent full',
}

function findFixtureEntry(
  modelDir: string,
  modelFolderName: string,
  fixtureName: string,
): { type: 'oneshot' | 'agent'; path: string } | null {
  if (!existsSync(modelDir)) return null

  for (const entry of readdirSync(modelDir, { withFileTypes: true })) {
    if (entry.isFile() && entry.name.endsWith('.json')) {
      const withoutModel = entry.name.replace('.json', '').substring(modelFolderName.length + 2)
      const lastIdx = withoutModel.lastIndexOf('__')
      if (lastIdx < 0) continue
      if (withoutModel.substring(0, lastIdx) === fixtureName) {
        return { type: 'oneshot', path: join(modelDir, entry.name) }
      }
    } else if (entry.isDirectory()) {
      const withoutModel = entry.name.substring(modelFolderName.length + 2)
      const m = withoutModel.match(/^(.+)__(\d+)runs__(\d+)$/)
      if (!m) continue
      if (m[1] === fixtureName) {
        return { type: 'agent', path: join(modelDir, entry.name) }
      }
    }
  }
  return null
}

function stripOutputCode(run: any): any {
  const { output_code, ...rest } = run
  return rest
}

export default defineEventHandler((event) => {
  const name        = getRouterParam(event, 'name')
  const model       = getRouterParam(event, 'model')
  const fixtureName = getRouterParam(event, 'fixture')

  if (!name || !model || !fixtureName) {
    throw createError({ statusCode: 400, message: 'Missing parameters' })
  }

  const modelDir = join(PUBLISHED_DIR, name, model)
  const entry = findFixtureEntry(modelDir, model, fixtureName)
  if (!entry) {
    throw createError({ statusCode: 404, message: `Fixture not found: ${fixtureName}` })
  }

  const fixtureLabel = FIXTURE_LABELS[fixtureName] ?? fixtureName

  if (entry.type === 'oneshot') {
    const runs: any[] = JSON.parse(readFileSync(entry.path, 'utf-8'))
    return {
      fixtureName,
      fixtureLabel,
      type: 'oneshot' as const,
      runs: runs.map(stripOutputCode),
    }
  } else {
    const summaryPath = join(entry.path, 'summary.json')
    if (!existsSync(summaryPath)) {
      throw createError({ statusCode: 404, message: 'summary.json not found' })
    }
    const summary = JSON.parse(readFileSync(summaryPath, 'utf-8'))
    return {
      fixtureName,
      fixtureLabel,
      type: 'agent' as const,
      runs: summary.runs.map(stripOutputCode),
    }
  }
})
