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
  const validRuns = runs.filter(r => !r.aborted)
  const n = validRuns.length
  if (n === 0) return null
  const isAgent = 'tool_call_log' in validRuns[0]
  return {
    n_runs:             n,
    n_aborted:          runs.length - n,
    avg_final_score:    round2(avg(validRuns.map(r => r.final_score))),
    avg_pattern_score:  round2(avg(validRuns.map(r => r.pattern_score))),
    avg_naming_score:   round2(avg(validRuns.map(r => r.naming_score))),
    compile_rate:       round2(validRuns.filter(r => r.compiles).length / n),
    avg_tokens_per_sec: round2(avg(validRuns.map(r => r.tokens_per_sec))),
    avg_duration_sec:   round2(avg(validRuns.map(r => r.duration_sec))),
    is_agent:           isAgent,
    avg_steps:          isAgent ? round2(avg(validRuns.map(r => r.steps ?? 0))) : null,
    succeed_rate:       isAgent ? round2(validRuns.filter(r => r.succeeded).length / n) : null,
  }
}

export default defineEventHandler((event) => {
  const name = getRouterParam(event, 'name')
  if (!name) throw createError({ statusCode: 400, message: 'Missing session name' })

  const sessionDir = join(PUBLISHED_DIR, name)
  if (!existsSync(sessionDir)) {
    throw createError({ statusCode: 404, message: `Session not found: ${name}` })
  }

  const modelEntries = readdirSync(sessionDir, { withFileTypes: true }).filter(e => e.isDirectory())
  const allFixtures = new Set<string>()
  const models = []

  for (const modelEntry of modelEntries) {
    const modelDir = join(sessionDir, modelEntry.name)
    const modelName = modelEntry.name.replace('__', ':')
    const fixtures: Record<string, any> = {}

    for (const entry of readdirSync(modelDir, { withFileTypes: true })) {
      const entryPath = join(modelDir, entry.name)

      if (entry.isFile() && entry.name.endsWith('.json')) {
        // Single-shot: strip model prefix + timestamp suffix
        const withoutModel = entry.name.replace('.json', '').substring(modelEntry.name.length + 2)
        const lastIdx = withoutModel.lastIndexOf('__')
        if (lastIdx < 0) continue
        const fixtureName = withoutModel.substring(0, lastIdx)
        try {
          const runs = JSON.parse(readFileSync(entryPath, 'utf-8'))
          fixtures[fixtureName] = { type: 'oneshot', ...aggregateRuns(runs) }
          allFixtures.add(fixtureName)
        } catch {}

      } else if (entry.isDirectory()) {
        // Agent: strip model prefix, parse fixture__Nruns__ts
        const withoutModel = entry.name.substring(modelEntry.name.length + 2)
        const m = withoutModel.match(/^(.+)__(\d+)runs__(\d+)$/)
        if (!m) continue
        const fixtureName = m[1]
        const summaryPath = join(entryPath, 'summary.json')
        if (!existsSync(summaryPath)) continue
        try {
          const summary = JSON.parse(readFileSync(summaryPath, 'utf-8'))
          fixtures[fixtureName] = { type: 'agent', ...aggregateRuns(summary.runs) }
          allFixtures.add(fixtureName)
        } catch {}
      }
    }

    models.push({ modelName, modelFolderName: modelEntry.name, fixtures })
  }

  const sessionMatch = name.match(/^session__(.+?)(?:__(\d+))?$/)
  const orderedFixtures = [...allFixtures].sort(
    (a, b) => (FIXTURE_ORDER.indexOf(a) ?? 99) - (FIXTURE_ORDER.indexOf(b) ?? 99)
  )

  return {
    folder: name,
    displayName: sessionMatch?.[1] ?? name,
    timestamp: sessionMatch?.[2] ? parseInt(sessionMatch[2]) : null,
    models,
    fixtures: orderedFixtures.map(f => ({ key: f, label: FIXTURE_LABELS[f] ?? f })),
  }
})
