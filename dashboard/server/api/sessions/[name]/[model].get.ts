import { readdirSync, readFileSync, existsSync } from 'node:fs'
import { resolve, join } from 'node:path'

const PUBLISHED_DIR = resolve(process.cwd(), '../results/published')

const FIXTURE_ORDER = [
  'nuxt-form-oneshot',
  'nuxt-form-agent-guided',
  'nuxt-form-agent-twofiles',
  'nuxt-form-agent-rag',
  'nuxt-form-agent-full',
]

const FIXTURE_LABELS: Record<string, string> = {
  'nuxt-form-oneshot':         'A — Single-shot',
  'nuxt-form-agent-guided':    'B — Agent guided',
  'nuxt-form-agent-twofiles':  'C — Agent two files',
  'nuxt-form-agent-rag':       'D — Agent + RAG',
  'nuxt-form-agent-full':      'E — Agent full',
}

function avg(arr: number[]): number {
  return arr.reduce((a, b) => a + b, 0) / arr.length
}
function round2(n: number): number {
  return Math.round(n * 100) / 100
}

function aggregateRuns(runs: any[]) {
  const n = runs.length
  if (n === 0) return null
  const isAgent = 'tool_call_log' in runs[0]
  return {
    n_runs: n,
    avg_final_score:    round2(avg(runs.map(r => r.final_score))),
    avg_pattern_score:  round2(avg(runs.map(r => r.pattern_score))),
    avg_naming_score:   round2(avg(runs.map(r => r.naming_score))),
    compile_rate:       round2(runs.filter(r => r.compiles).length / n),
    avg_tokens_per_sec: round2(avg(runs.map(r => r.tokens_per_sec))),
    avg_duration_sec:   round2(avg(runs.map(r => r.duration_sec))),
    is_agent:           isAgent,
    avg_steps:          isAgent ? round2(avg(runs.map(r => r.steps ?? 0))) : null,
    succeed_rate:       isAgent ? round2(runs.filter(r => r.succeeded).length / n) : null,
  }
}

interface RunSummary {
  run_number: number
  compiles: boolean
  final_score: number
  pattern_score: number
  naming_score: number
  tokens_per_sec: number
  duration_sec: number
  steps?: number
  succeeded?: boolean
  iterations?: number
}

function toRunSummary(r: any): RunSummary {
  const s: RunSummary = {
    run_number:    r.run_number,
    compiles:      r.compiles,
    final_score:   r.final_score,
    pattern_score: r.pattern_score,
    naming_score:  r.naming_score,
    tokens_per_sec: r.tokens_per_sec,
    duration_sec:  r.duration_sec,
  }
  if ('steps' in r)      s.steps = r.steps
  if ('succeeded' in r)  s.succeeded = r.succeeded
  if ('iterations' in r) s.iterations = r.iterations
  return s
}

export default defineEventHandler((event) => {
  const name  = getRouterParam(event, 'name')
  const model = getRouterParam(event, 'model')
  if (!name)  throw createError({ statusCode: 400, message: 'Missing session name' })
  if (!model) throw createError({ statusCode: 400, message: 'Missing model' })

  const modelDir = join(PUBLISHED_DIR, name, model)
  if (!existsSync(modelDir)) {
    throw createError({ statusCode: 404, message: `Model not found: ${model}` })
  }

  const modelName = model.replace('__', ':')
  const fixtures: Record<string, any> = {}

  for (const entry of readdirSync(modelDir, { withFileTypes: true })) {
    const entryPath = join(modelDir, entry.name)

    if (entry.isFile() && entry.name.endsWith('.json')) {
      const withoutModel = entry.name.replace('.json', '').substring(model.length + 2)
      const lastIdx = withoutModel.lastIndexOf('__')
      if (lastIdx < 0) continue
      const fixtureName = withoutModel.substring(0, lastIdx)
      try {
        const runs: any[] = JSON.parse(readFileSync(entryPath, 'utf-8'))
        fixtures[fixtureName] = {
          type: 'oneshot',
          aggregate: aggregateRuns(runs),
          runs: runs.map(toRunSummary),
        }
      } catch {}

    } else if (entry.isDirectory()) {
      const withoutModel = entry.name.substring(model.length + 2)
      const m = withoutModel.match(/^(.+)__(\d+)runs__(\d+)$/)
      if (!m) continue
      const fixtureName = m[1]
      const summaryPath = join(entryPath, 'summary.json')
      if (!existsSync(summaryPath)) continue
      try {
        const summary = JSON.parse(readFileSync(summaryPath, 'utf-8'))
        fixtures[fixtureName] = {
          type: 'agent',
          aggregate: aggregateRuns(summary.runs),
          runs: summary.runs.map(toRunSummary),
        }
      } catch {}
    }
  }

  const orderedFixtures: Record<string, any> = {}
  for (const key of FIXTURE_ORDER) {
    if (key in fixtures) orderedFixtures[key] = { ...fixtures[key], label: FIXTURE_LABELS[key] ?? key }
  }
  // append any not in FIXTURE_ORDER
  for (const key of Object.keys(fixtures)) {
    if (!(key in orderedFixtures)) orderedFixtures[key] = { ...fixtures[key], label: FIXTURE_LABELS[key] ?? key }
  }

  return {
    modelName,
    modelFolderName: model,
    fixtures: orderedFixtures,
  }
})
