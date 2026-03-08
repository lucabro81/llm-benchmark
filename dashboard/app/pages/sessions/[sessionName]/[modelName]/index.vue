<template>
  <div>
    <Breadcrumb :items="breadcrumb" />

    <div v-if="pending" class="empty-state">Loading…</div>
    <div v-else-if="error" class="empty-state">Failed to load model data.</div>
    <template v-else-if="data">
      <h1 class="page-title"><code>{{ data.modelName }}</code></h1>

      <div
        v-for="fixtureKey in FIXTURE_ORDER.filter(k => data.fixtures[k])"
        :key="fixtureKey"
        class="fixture-section"
      >
        <div class="fixture-header">
          <span class="fixture-label">{{ data.fixtures[fixtureKey].label }}</span>
          <ScoreBar :score="data.fixtures[fixtureKey].aggregate?.avg_final_score ?? 0" />
          <span class="compile-badge" :class="compileClass(data.fixtures[fixtureKey].aggregate?.compile_rate ?? 0)">
            {{ ((data.fixtures[fixtureKey].aggregate?.compile_rate ?? 0) * 100).toFixed(0) }}% compile
          </span>
        </div>

        <div class="table-wrap">
          <table class="runs-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Score</th>
                <th>Compile</th>
                <th>Pattern</th>
                <th>Naming</th>
                <th>tok/s</th>
                <th>Duration</th>
                <th v-if="data.fixtures[fixtureKey].type === 'agent'">Steps</th>
                <th v-if="data.fixtures[fixtureKey].type === 'agent'">Succeeded</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="run in data.fixtures[fixtureKey].runs"
                :key="run.run_number"
                class="run-row"
                @click="navigateTo(`/sessions/${sessionName}/${modelName}/${fixtureKey}/${run.run_number}`)"
              >
                <td class="cell-num">{{ run.run_number }}</td>
                <td>
                  <span class="score-val" :class="scoreClass(run.final_score)">{{ (run.final_score ?? 0).toFixed(1) }}</span>
                </td>
                <td>
                  <span v-if="run.compiles" class="icon-ok">✓</span>
                  <span v-else class="icon-fail">✗</span>
                </td>
                <td class="cell-num">{{ run.pattern_score?.toFixed(1) ?? '—' }}</td>
                <td class="cell-num">{{ run.naming_score?.toFixed(1) ?? '—' }}</td>
                <td class="cell-num">{{ run.tokens_per_sec?.toFixed(0) ?? '—' }}</td>
                <td class="cell-num">{{ run.duration_sec?.toFixed(1) ?? '—' }}s</td>
                <td v-if="data.fixtures[fixtureKey].type === 'agent'" class="cell-num">
                  {{ run.steps ?? '—' }}
                </td>
                <td v-if="data.fixtures[fixtureKey].type === 'agent'">
                  <span v-if="run.succeeded === true" class="icon-ok">✓</span>
                  <span v-else-if="run.succeeded === false" class="icon-fail">✗</span>
                  <span v-else class="text-muted">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const sessionName = route.params.sessionName as string
const modelName = route.params.modelName as string

const { data, pending, error } = await useAsyncData(
  `model-${sessionName}-${modelName}`,
  () => $fetch<any>(`/api/sessions/${sessionName}/${modelName}`)
)

const FIXTURE_ORDER = [
  'nuxt-form-oneshot',
  'nuxt-form-agent-guided',
  'nuxt-form-agent-twofiles',
  'nuxt-form-agent-rag',
  'nuxt-form-agent-full',
]

const sessionDisplayName = computed(() => {
  const m = sessionName.match(/^session__(.+?)(?:__\d+)?$/)
  return m ? m[1].replace('__', ':') : sessionName
})

const modelDisplayName = computed(() => modelName.replace('__', ':'))

const breadcrumb = computed(() => [
  { label: 'Sessions', to: '/' },
  { label: sessionDisplayName.value, to: '/sessions/' + sessionName },
  { label: data.value?.modelName ?? modelDisplayName.value },
])

function scoreClass(score: number): string {
  if (score >= 8) return 'score--great'
  if (score >= 6) return 'score--good'
  if (score >= 3) return 'score--mid'
  return 'score--low'
}

function compileClass(rate: number): string {
  if (rate >= 0.8) return 'compile-badge--great'
  if (rate >= 0.5) return 'compile-badge--mid'
  return 'compile-badge--low'
}
</script>

<style scoped>
.page-title {
  font-size: 1.4rem;
  font-weight: 700;
  margin-bottom: 1.5rem;
}

.page-title code {
  font-family: monospace;
  font-size: 1.2rem;
}

.empty-state {
  text-align: center;
  padding: 3rem;
  color: var(--color-text-muted);
}

.text-muted {
  color: var(--color-text-muted);
}

/* Fixture section */
.fixture-section {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  margin-bottom: 1.5rem;
  overflow: hidden;
}

.fixture-header {
  display: flex;
  align-items: center;
  gap: .75rem;
  padding: .85rem 1rem;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg);
  flex-wrap: wrap;
}

.fixture-label {
  font-size: .9rem;
  font-family: monospace;
  font-weight: 600;
  color: var(--color-text);
  margin-right: auto;
}

.compile-badge {
  display: inline-block;
  font-size: .75rem;
  padding: .15rem .5rem;
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

/* Table */
.table-wrap {
  overflow-x: auto;
}

.runs-table {
  width: 100%;
  border-collapse: collapse;
  font-size: .875rem;
}

.runs-table th,
.runs-table td {
  padding: .55rem .75rem;
  border-bottom: 1px solid var(--color-border);
  text-align: left;
  vertical-align: middle;
  white-space: nowrap;
}

.runs-table thead th {
  font-weight: 600;
  color: var(--color-text-muted);
  font-size: .8rem;
  background: var(--color-surface);
}

.runs-table tbody tr:last-child td {
  border-bottom: none;
}

.run-row {
  cursor: pointer;
  transition: background .12s;
}

.run-row:hover td {
  background: var(--color-bg);
}

.cell-num {
  font-variant-numeric: tabular-nums;
  color: var(--color-text-muted);
}

/* Score coloring */
.score-val {
  font-weight: 700;
  font-size: .9rem;
}

.score--great { color: var(--color-score-great); }
.score--good  { color: var(--color-score-good); }
.score--mid   { color: var(--color-score-mid); }
.score--low   { color: var(--color-score-low); }

/* Icons */
.icon-ok   { color: var(--color-score-great); font-weight: 700; }
.icon-fail { color: var(--color-score-low);   font-weight: 700; }
</style>
