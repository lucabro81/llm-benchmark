<template>
  <div>
    <Breadcrumb :items="breadcrumb" />

    <div v-if="pending" class="empty-state">Loading…</div>
    <div v-else-if="error" class="empty-state">Failed to load session data.</div>
    <template v-else-if="session">
      <h1 class="page-title">{{ session.displayName }}</h1>

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
              <th class="col-fixture">Fixture</th>
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
                    <span class="compile-badge" :class="compileClass(getFixtureData(m, fixture.key)!.compile_rate)">
                      {{ (getFixtureData(m, fixture.key)!.compile_rate * 100).toFixed(0) }}% compile
                    </span>
                    <span class="stat-chip">{{ getFixtureData(m, fixture.key)!.avg_tokens_per_sec?.toFixed(0) ?? '—' }} tok/s</span>
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

const { data: session, pending, error } = await useAsyncData(
  'session-' + route.params.sessionName,
  () => $fetch<any>('/api/sessions/' + route.params.sessionName)
)

const sessionDisplayName = computed(() => {
  const raw = route.params.sessionName as string
  const m = raw.match(/^session__(.+?)(?:__\d+)?$/)
  return m ? m[1].replace('__', ':') : raw
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
  margin-bottom: 1.25rem;
}

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
</style>
