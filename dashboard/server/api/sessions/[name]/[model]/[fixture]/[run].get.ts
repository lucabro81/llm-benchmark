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

export default defineEventHandler((event) => {
  const name        = getRouterParam(event, 'name')
  const model       = getRouterParam(event, 'model')
  const fixtureName = getRouterParam(event, 'fixture')
  const runParam    = getRouterParam(event, 'run')

  if (!name || !model || !fixtureName || !runParam) {
    throw createError({ statusCode: 400, message: 'Missing parameters' })
  }

  const runNumber = parseInt(runParam, 10)
  if (isNaN(runNumber)) {
    throw createError({ statusCode: 400, message: 'Invalid run number' })
  }

  const modelDir = join(PUBLISHED_DIR, name, model)
  const entry = findFixtureEntry(modelDir, model, fixtureName)
  if (!entry) {
    throw createError({ statusCode: 404, message: `Fixture not found: ${fixtureName}` })
  }

  const fixtureLabel = FIXTURE_LABELS[fixtureName] ?? fixtureName

  let runs: any[]
  let type: 'oneshot' | 'agent'

  if (entry.type === 'oneshot') {
    runs = JSON.parse(readFileSync(entry.path, 'utf-8'))
    type = 'oneshot'
  } else {
    const summaryPath = join(entry.path, 'summary.json')
    if (!existsSync(summaryPath)) {
      throw createError({ statusCode: 404, message: 'summary.json not found' })
    }
    const summary = JSON.parse(readFileSync(summaryPath, 'utf-8'))
    runs = summary.runs
    type = 'agent'
  }

  const run = runs.find(r => r.run_number === runNumber)
  if (!run) {
    throw createError({ statusCode: 404, message: `Run ${runNumber} not found` })
  }

  return {
    fixtureName,
    fixtureLabel,
    type,
    run,
  }
})
