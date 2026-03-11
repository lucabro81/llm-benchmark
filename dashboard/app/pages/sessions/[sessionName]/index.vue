<template>
  <div>
    <Breadcrumb :items="breadcrumb" />

    <div v-if="pending" class="empty-state">Loading…</div>
    <div v-else-if="error" class="empty-state">Failed to load session data.</div>
    <template v-else-if="session">
      <h1 class="page-title">{{ session.displayName }}</h1>

      <!-- Benchmark context -->
      <div class="bench-context">
        <p class="bench-context__lead">
          All tasks ask the model to implement the same component — <code>RegistrationForm.vue</code>, a Vue 3
          form with Zod validation, conditional fields, and controlled inputs from <code>packages/elements</code>.
          What changes across fixtures is <strong>how much help the model gets</strong>: inline docs, tool access,
          RAG, and filesystem exploration — each adding one layer of real-world complexity.
        </p>
        <details class="bench-details">
          <summary class="bench-details__summary">Fixture breakdown</summary>
          <div class="bench-details__body">
            <div class="fixture-legend">
              <div class="fixture-legend__header">
                <span>Task</span><span>Tools available</span><span>Files</span><span>Context source</span><span>Max steps</span>
              </div>
              <div v-for="f in FIXTURE_LEGEND" :key="f.key" class="fixture-legend__row">
                <span><strong>{{ f.letter }}</strong> — {{ f.name }}</span>
                <span class="legend-tools">{{ f.tools.join(', ') || '—' }}</span>
                <span>{{ f.files }}</span>
                <span>{{ f.context }}</span>
                <span>{{ f.maxSteps === 1 ? '—' : f.maxSteps }}</span>
              </div>
            </div>
            <div class="score-legend">
              <span class="score-legend__title">Score (0–10)</span>
              <span class="legend-chip legend-chip--great">≥ 8 excellent</span>
              <span class="legend-chip legend-chip--good">≥ 6 good</span>
              <span class="legend-chip legend-chip--mid">≥ 3 partial</span>
              <span class="legend-chip legend-chip--low">&lt; 3 poor</span>
              <span class="score-legend__formula">= 50% TypeScript compile + 40% AST pattern checks + 10% naming</span>
            </div>
          </div>
        </details>
      </div>

      <!-- Hidden links so SSG crawler pre-renders all model detail pages -->
      <nav aria-hidden="true" class="prerender-links">
        <NuxtLink
          v-for="m in session.models"
          :key="m.modelFolderName"
          :to="`/sessions/${route.params.sessionName}/${m.modelFolderName}`"
        />
      </nav>

      <!-- Model selector pills -->
      <div class="model-pills">
        <button
          v-for="m in session.models"
          :key="m.modelFolderName"
          class="model-pill"
          :class="{ 'model-pill--selected': selectedModels.has(m.modelFolderName) }"
          @click="toggleModel(m.modelFolderName)"
        >
          {{ m.modelName }}
        </button>
      </div>

      <!-- Comparison table -->
      <div class="table-wrap">
        <table class="comparison-table">
          <thead>
            <tr>
              <th class="col-fixture" title="Tasks A→E — each adds one variable vs the previous">Fixture</th>
              <th v-for="m in visibleModels" :key="m.modelFolderName" class="col-model">
                <NuxtLink :to="`/sessions/${route.params.sessionName}/${m.modelFolderName}`">
                  {{ m.modelName }}
                </NuxtLink>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="fixture in session.fixtures" :key="fixture.key">
              <td class="col-fixture">{{ fixture.label }}</td>
              <td v-for="m in visibleModels" :key="m.modelFolderName" class="col-score">
                <template v-if="getFixtureData(m, fixture.key)">
                  <ScoreBar :score="getFixtureData(m, fixture.key)!.avg_final_score" />
                  <div class="cell-chips">
                    <span class="compile-badge" :class="compileClass(getFixtureData(m, fixture.key)!.compile_rate)"
                      title="Fraction of runs where vue-tsc reported no errors">
                      {{ (getFixtureData(m, fixture.key)!.compile_rate * 100).toFixed(0) }}% compile
                    </span>
                    <span class="stat-chip" title="Average output tokens per second across all runs">
                      {{ getFixtureData(m, fixture.key)!.avg_tokens_per_sec?.toFixed(0) ?? '—' }} tok/s
                    </span>
                  </div>
                </template>
                <span v-else class="text-muted">—</span>
              </td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <td class="col-fixture foot-label">Overall avg</td>
              <td v-for="m in visibleModels" :key="m.modelFolderName" class="col-score">
                <ScoreBar :score="overallAvg(m)" />
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      <!-- Per-model stat cards -->
      <div class="stat-cards">
        <div v-for="m in visibleModels" :key="m.modelFolderName" class="stat-card">
          <div class="stat-card__title">{{ m.modelName }}</div>
          <div class="stat-card__grid">
            <div class="stat-card__item">
              <div class="stat-card__label">Compile rate</div>
              <div class="stat-card__value">{{ (avgCompileRate(m) * 100).toFixed(0) }}%</div>
            </div>
            <div class="stat-card__item">
              <div class="stat-card__label">Avg speed</div>
              <div class="stat-card__value">{{ avgSpeed(m).toFixed(1) }} tok/s</div>
            </div>
            <div class="stat-card__item">
              <div class="stat-card__label">Avg duration</div>
              <div class="stat-card__value">{{ avgDuration(m).toFixed(1) }}s</div>
            </div>
            <div v-if="hasAgentData(m)" class="stat-card__item">
              <div class="stat-card__label">Avg steps</div>
              <div class="stat-card__value">{{ avgAgentSteps(m).toFixed(1) }}</div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()

const FIXTURE_LEGEND = [
  { key: 'nuxt-form-oneshot',          letter: 'A', name: 'Single-shot',      tools: [],                                                              files: 1, context: 'Inline in prompt',  maxSteps: 1  },
  { key: 'nuxt-form-agent-guided',     letter: 'B', name: 'Agent (guided)',   tools: ['write_file', 'run_compilation'],                               files: 1, context: 'Inline in prompt',  maxSteps: 10 },
  { key: 'nuxt-form-agent-twofiles',   letter: 'C', name: 'Agent (2 files)',  tools: ['write_file', 'run_compilation'],                               files: 2, context: 'Inline in prompt',  maxSteps: 15 },
  { key: 'nuxt-form-agent-rag',        letter: 'D', name: 'Agent + RAG',      tools: ['write_file', 'run_compilation', 'query_rag'],                   files: 2, context: 'RAG only',          maxSteps: 20 },
  { key: 'nuxt-form-agent-full',       letter: 'E', name: 'Agent (full)',     tools: ['list_files', 'read_file', 'write_file', 'run_compilation', 'query_rag'], files: 2, context: 'RAG + filesystem', maxSteps: 30 },
]

const { data: session, pending, error } = await useAsyncData(
  'session-' + route.params.sessionName,
  () => $fetch<any>('/api/sessions/' + route.params.sessionName)
)

const sessionDisplayName = computed(() => {
  const raw = route.params.sessionName as string
  const m = raw.match(/^session__(.+?)(?:__\d+)?$/)
  return m ? m[1]?.replace('__', ':') : raw
})

const breadcrumb = computed(() => [
  { label: 'Sessions', to: '/' },
  { label: session.value?.displayName ?? sessionDisplayName.value }
])

const selectedModels = ref<Set<string>>(new Set())

const MAX_SELECTED = 4

watchEffect(() => {
  if (session.value?.models && selectedModels.value.size === 0) {
    // Select first 2 models by default
    const initial = session.value.models.slice(0, 2).map((m: any) => m.modelFolderName)
    selectedModels.value = new Set(initial)
  }
})

function toggleModel(name: string) {
  const current = selectedModels.value
  if (current.has(name) && current.size === 1) return // keep at least 1
  const next = new Set(current)
  if (next.has(name)) {
    next.delete(name)
  } else {
    if (next.size >= MAX_SELECTED) return // cap at 4
    next.add(name)
  }
  selectedModels.value = next
}

const visibleModels = computed(() =>
  (session.value?.models ?? []).filter((m: any) => selectedModels.value.has(m.modelFolderName))
)

function getFixtureData(model: any, fixture: string) {
  return model.fixtures?.[fixture] ?? null
}

function overallAvg(model: any): number {
  const fixtures = Object.values(model.fixtures ?? {}) as any[]
  if (!fixtures.length) return 0
  return fixtures.reduce((s: number, f: any) => s + (f.avg_final_score ?? 0), 0) / fixtures.length
}

function avgCompileRate(model: any): number {
  const fixtures = Object.values(model.fixtures ?? {}) as any[]
  if (!fixtures.length) return 0
  return fixtures.reduce((s: number, f: any) => s + (f.compile_rate ?? 0), 0) / fixtures.length
}

function avgSpeed(model: any): number {
  const fixtures = Object.values(model.fixtures ?? {}) as any[]
  const valid = fixtures.filter((f: any) => f.avg_tokens_per_sec != null)
  if (!valid.length) return 0
  return valid.reduce((s: number, f: any) => s + f.avg_tokens_per_sec, 0) / valid.length
}

function avgDuration(model: any): number {
  const fixtures = Object.values(model.fixtures ?? {}) as any[]
  const valid = fixtures.filter((f: any) => f.avg_duration_sec != null)
  if (!valid.length) return 0
  return valid.reduce((s: number, f: any) => s + f.avg_duration_sec, 0) / valid.length
}

function hasAgentData(model: any): boolean {
  return Object.values(model.fixtures ?? {}).some((f: any) => f.avg_steps != null)
}

function avgAgentSteps(model: any): number {
  const fixtures = Object.values(model.fixtures ?? {}) as any[]
  const valid = fixtures.filter((f: any) => f.avg_steps != null)
  if (!valid.length) return 0
  return valid.reduce((s: number, f: any) => s + f.avg_steps, 0) / valid.length
}

function compileClass(rate: number): string {
  if (rate >= 0.8) return 'compile-badge--great'
  if (rate >= 0.5) return 'compile-badge--mid'
  return 'compile-badge--low'
}
</script>

<style scoped>
.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: .75rem;
}

/* Benchmark context block */
.bench-context {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 1rem 1.25rem;
  margin-bottom: 1.5rem;
}

.bench-context__lead {
  font-size: .88rem;
  color: var(--color-text-muted);
  line-height: 1.6;
  margin: 0 0 .5rem;
}

.bench-context__lead code {
  font-family: monospace;
  font-size: .85rem;
  background: var(--color-bg);
  padding: .1rem .3rem;
  border-radius: 3px;
  border: 1px solid var(--color-border);
}

.bench-details {
  margin-top: .25rem;
}

.bench-details__summary {
  font-size: .83rem;
  font-weight: 600;
  color: var(--color-accent);
  cursor: pointer;
  user-select: none;
  list-style: none;
}

.bench-details__summary::-webkit-details-marker { display: none; }
.bench-details__summary::before { content: '▶ '; font-size: .7rem; }
details[open] .bench-details__summary::before { content: '▼ '; }

.bench-details__body {
  margin-top: .75rem;
  display: flex;
  flex-direction: column;
  gap: .75rem;
}

/* Fixture legend grid */
.fixture-legend {
  display: grid;
  gap: 0;
  font-size: .82rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  overflow: hidden;
}

.fixture-legend__header,
.fixture-legend__row {
  display: grid;
  grid-template-columns: 14rem 1fr 3rem 9rem 5rem;
  gap: 0;
}

.fixture-legend__header {
  background: var(--color-bg);
  font-weight: 600;
  color: var(--color-text-muted);
  font-size: .78rem;
}

.fixture-legend__header span,
.fixture-legend__row span {
  padding: .4rem .65rem;
  border-bottom: 1px solid var(--color-border);
}

.fixture-legend__row:last-child span {
  border-bottom: none;
}

.legend-tools {
  font-family: monospace;
  font-size: .78rem;
  color: var(--color-text-muted);
}

/* Score legend */
.score-legend {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: .4rem;
  font-size: .8rem;
}

.score-legend__title {
  font-weight: 600;
  color: var(--color-text-muted);
  margin-right: .15rem;
}

.score-legend__formula {
  color: var(--color-text-muted);
  font-size: .78rem;
  margin-left: .35rem;
}

.legend-chip {
  display: inline-block;
  font-size: .75rem;
  font-weight: 600;
  padding: .1rem .4rem;
  border-radius: 4px;
}

.legend-chip--great { background: #d1fae5; color: #065f46; }
.legend-chip--good  { background: #dbeafe; color: #1e40af; }
.legend-chip--mid   { background: #fff3cd; color: #856404; }
.legend-chip--low   { background: #fee2e2; color: #991b1b; }

.empty-state {
  text-align: center;
  padding: 3rem;
  color: var(--color-text-muted);
}

.text-muted {
  color: var(--color-text-muted);
}

/* Model pills */
.model-pills {
  display: flex;
  flex-wrap: wrap;
  gap: .5rem;
  margin-bottom: 1.5rem;
}

.model-pill {
  padding: .35rem .85rem;
  border-radius: 999px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-muted);
  font-size: .82rem;
  font-family: monospace;
  cursor: pointer;
  transition: background .15s, color .15s, border-color .15s;
}

.model-pill:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.model-pill--selected {
  background: var(--color-accent);
  color: #fff;
  border-color: var(--color-accent);
}

/* Table */
.table-wrap {
  overflow-x: auto;
  margin-bottom: 2rem;
}

.comparison-table {
  width: 100%;
  border-collapse: collapse;
  font-size: .88rem;
}

.comparison-table th,
.comparison-table td {
  padding: .65rem .75rem;
  border-bottom: 1px solid var(--color-border);
  text-align: left;
  vertical-align: middle;
}

.comparison-table thead th {
  background: var(--color-surface);
  font-weight: 600;
  white-space: nowrap;
}

.comparison-table thead th a {
  color: var(--color-accent);
  text-decoration: none;
  font-family: monospace;
  font-size: .82rem;
}

.comparison-table thead th a:hover {
  text-decoration: underline;
}

.comparison-table tfoot td {
  font-weight: 600;
  background: var(--color-surface);
}

.col-fixture {
  font-size: .82rem;
  font-family: monospace;
  color: var(--color-text-muted);
  white-space: nowrap;
  min-width: 200px;
}

.col-model {
  min-width: 180px;
}

.col-score {
  min-width: 180px;
}

.foot-label {
  color: var(--color-text);
}

/* Compile badge */
.cell-chips {
  display: flex;
  flex-wrap: wrap;
  gap: .3rem;
  margin-top: .35rem;
}

.compile-badge {
  display: inline-block;
  font-size: .75rem;
  padding: .1rem .45rem;
  border-radius: 4px;
  font-weight: 600;
}

.compile-badge--great {
  background: #d1fae5;
  color: #065f46;
}

.compile-badge--mid {
  background: #fff3cd;
  color: #856404;
}

.compile-badge--low {
  background: #fee2e2;
  color: #991b1b;
}

.stat-chip {
  display: inline-block;
  font-size: .75rem;
  padding: .1rem .45rem;
  border-radius: 4px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  color: var(--color-text-muted);
}

/* Stat cards */
.stat-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}

.stat-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 1rem 1.25rem;
  box-shadow: var(--shadow);
}

.stat-card__title {
  font-size: .85rem;
  font-family: monospace;
  font-weight: 600;
  margin-bottom: .75rem;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stat-card__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: .6rem;
}

.stat-card__label {
  font-size: .75rem;
  color: var(--color-text-muted);
  margin-bottom: .1rem;
}

.stat-card__value {
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-text);
}

.prerender-links {
  display: none;
}
</style>
