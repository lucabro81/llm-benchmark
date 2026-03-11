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

const FIXTURE_DESCS: Record<string, string> = {
  'nuxt-form-oneshot':        'One shot, no tools. The model must produce a correct RegistrationForm.vue in a single response. Full component API documented inline in the prompt.',
  'nuxt-form-agent-guided':   'Agentic loop with write_file + run_compilation. Iterate on TypeScript compiler feedback until the code passes or the step budget (10) runs out.',
  'nuxt-form-agent-twofiles': 'Same as B, but must produce two coordinated files in order: registration/types/index.ts (Zod schema + types) then RegistrationForm.vue importing from it.',
  'nuxt-form-agent-rag':      'No inline API docs in the prompt. The model must call query_rag to look up component usage examples from a BM25 document store before writing.',
  'nuxt-form-agent-full':     'Full tool access: list_files, read_file, write_file, run_compilation, query_rag. The model can explore the project freely — closest to real-world agentic coding.',
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
    compile_rate:       round2(runs.filter(r => r.compiles).length / n),
    avg_tokens_per_sec: round2(avg(runs.map(r => r.tokens_per_sec))),
    avg_duration_sec:   round2(avg(runs.map(r => r.duration_sec))),
    avg_steps:          isAgent ? round2(avg(runs.map(r => r.steps ?? 0))) : null,
  }
}

function readPrompt(entry: { type: 'oneshot' | 'agent'; path: string }): string | null {
  try {
    if (entry.type === 'agent') {
      const summaryPath = join(entry.path, 'summary.json')
      if (!existsSync(summaryPath)) return null
      const summary = JSON.parse(readFileSync(summaryPath, 'utf-8'))
      return summary.prompt ?? null
    } else {
      const promptPath = entry.path.replace(/\.json$/, '.prompt.md')
      if (!existsSync(promptPath)) return null
      return readFileSync(promptPath, 'utf-8')
    }
  } catch {
    return null
  }
}

export default defineEventHandler((event) => {
  const name        = getRouterParam(event, 'name')
  const fixtureName = getRouterParam(event, 'fixture')

  if (!name || !fixtureName) {
    throw createError({ statusCode: 400, message: 'Missing parameters' })
  }

  const sessionDir = join(PUBLISHED_DIR, name)
  if (!existsSync(sessionDir)) {
    throw createError({ statusCode: 404, message: `Session not found: ${name}` })
  }

  const modelEntries = readdirSync(sessionDir, { withFileTypes: true }).filter(e => e.isDirectory())

  let prompt: string | null = null
  const models = []

  for (const modelEntry of modelEntries) {
    const modelDir = join(sessionDir, modelEntry.name)
    const modelName = modelEntry.name.replace('__', ':')
    const entry = findFixtureEntry(modelDir, modelEntry.name, fixtureName)
    if (!entry) continue

    // Read prompt from the first model that has it
    if (prompt === null) {
      prompt = readPrompt(entry)
    }

    let runs: any[]
    try {
      if (entry.type === 'oneshot') {
        runs = JSON.parse(readFileSync(entry.path, 'utf-8'))
      } else {
        const summaryPath = join(entry.path, 'summary.json')
        if (!existsSync(summaryPath)) continue
        const summary = JSON.parse(readFileSync(summaryPath, 'utf-8'))
        runs = summary.runs
      }
    } catch {
      continue
    }

    models.push({
      modelName,
      modelFolderName: modelEntry.name,
      aggregate: aggregateRuns(runs),
    })
  }

  if (models.length === 0) {
    throw createError({ statusCode: 404, message: `Fixture not found in any model: ${fixtureName}` })
  }

  return {
    fixtureName,
    fixtureLabel: FIXTURE_LABELS[fixtureName] ?? fixtureName,
    fixtureDesc:  FIXTURE_DESCS[fixtureName] ?? '',
    prompt,
    models,
  }
})
