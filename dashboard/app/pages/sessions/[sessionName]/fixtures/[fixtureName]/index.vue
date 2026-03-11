<template>
  <div>
    <Breadcrumb :items="breadcrumb" />

    <div v-if="pending" class="empty-state">Loading…</div>
    <div v-else-if="error" class="empty-state">Failed to load fixture data.</div>
    <template v-else-if="data">
      <h1 class="page-title">{{ data.fixtureLabel }}</h1>
      <p v-if="data.fixtureDesc" class="fixture-desc">{{ data.fixtureDesc }}</p>

      <!-- Cross-model comparison table -->
      <div class="table-wrap">
        <table class="model-table">
          <thead>
            <tr>
              <th class="col-model">Model</th>
              <th class="col-score">Avg Score</th>
              <th class="col-stat">Compile</th>
              <th class="col-stat">Speed</th>
              <th class="col-stat">Duration</th>
              <th class="col-stat">Steps</th>
              <th class="col-stat">Runs</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in data.models" :key="m.modelFolderName">
              <td class="col-model">
                <NuxtLink
                  :to="`/sessions/${sessionName}/${m.modelFolderName}/${fixtureName}`"
                  class="model-link"
                >{{ m.modelName }}</NuxtLink>
              </td>
              <td class="col-score">
                <template v-if="m.aggregate">
                  <ScoreBar :score="m.aggregate.avg_final_score" />
                </template>
                <span v-else class="text-muted">—</span>
              </td>
              <td class="col-stat">
                <template v-if="m.aggregate">
                  <span class="compile-badge" :class="compileClass(m.aggregate.compile_rate)">
                    {{ (m.aggregate.compile_rate * 100).toFixed(0) }}%
                  </span>
                </template>
                <span v-else class="text-muted">—</span>
              </td>
              <td class="col-stat">
                <span v-if="m.aggregate?.avg_tokens_per_sec != null" class="chip">
                  {{ m.aggregate.avg_tokens_per_sec.toFixed(0) }} tok/s
                </span>
                <span v-else class="text-muted">—</span>
              </td>
              <td class="col-stat">
                <span v-if="m.aggregate?.avg_duration_sec != null" class="chip">
                  {{ m.aggregate.avg_duration_sec.toFixed(1) }}s
                </span>
                <span v-else class="text-muted">—</span>
              </td>
              <td class="col-stat">
                <span v-if="m.aggregate?.avg_steps != null" class="chip">
                  {{ m.aggregate.avg_steps.toFixed(1) }}
                </span>
                <span v-else class="text-muted">—</span>
              </td>
              <td class="col-stat">
                <span v-if="m.aggregate" class="text-muted">{{ m.aggregate.n_runs }}</span>
                <span v-else class="text-muted">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Prompt section -->
      <div class="prompt-section">
        <div class="prompt-section__title">Prompt</div>
        <template v-if="data.prompt">
          <details class="prompt-details">
            <summary class="prompt-details__summary">View prompt</summary>
            <pre class="prompt-pre">{{ data.prompt }}</pre>
          </details>
        </template>
        <p v-else class="text-muted prompt-unavailable">Prompt non disponibile</p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const sessionName  = route.params.sessionName  as string
const fixtureName  = route.params.fixtureName  as string

const { data, pending, error } = await useAsyncData(
  `fixture-cross-${sessionName}-${fixtureName}`,
  () => $fetch<any>(`/api/sessions/${sessionName}/fixtures/${fixtureName}`)
)

const sessionDisplayName = computed(() => {
  const m = sessionName.match(/^session__(.+?)(?:__\d+)?$/)
  return m ? m[1].replace('__', ':') : sessionName
})

const breadcrumb = computed(() => [
  { label: 'Sessions', to: '/' },
  { label: sessionDisplayName.value, to: '/sessions/' + sessionName },
  { label: data.value?.fixtureLabel ?? fixtureName },
])

function compileClass(rate: number): string {
  if (rate >= 0.8) return 'compile-badge--great'
  if (rate >= 0.5) return 'compile-badge--mid'
  return 'compile-badge--low'
}
</script>

<style scoped>
.page-title {
  font-size: 1.3rem;
  font-weight: 700;
  margin-bottom: .35rem;
  font-family: monospace;
}

.fixture-desc {
  font-size: .88rem;
  color: var(--color-text-muted);
  line-height: 1.5;
  margin-bottom: 1.25rem;
  max-width: 680px;
}

.empty-state {
  text-align: center;
  padding: 3rem;
  color: var(--color-text-muted);
}

.text-muted {
  color: var(--color-text-muted);
}

/* Table */
.table-wrap {
  overflow-x: auto;
  margin-bottom: 2rem;
}

.model-table {
  width: 100%;
  border-collapse: collapse;
  font-size: .88rem;
}

.model-table th,
.model-table td {
  padding: .65rem .75rem;
  border-bottom: 1px solid var(--color-border);
  text-align: left;
  vertical-align: middle;
}

.model-table thead th {
  background: var(--color-surface);
  font-weight: 600;
  white-space: nowrap;
  color: var(--color-text-muted);
  font-size: .8rem;
}

.col-model {
  min-width: 180px;
}

.col-score {
  min-width: 160px;
}

.col-stat {
  white-space: nowrap;
}

.model-link {
  color: var(--color-accent);
  text-decoration: none;
  font-family: monospace;
  font-size: .85rem;
}

.model-link:hover {
  text-decoration: underline;
}

/* Compile badge */
.compile-badge {
  display: inline-block;
  font-size: .75rem;
  padding: .1rem .45rem;
  border-radius: 4px;
  font-weight: 600;
}

.compile-badge--great { background: #d1fae5; color: #065f46; }
.compile-badge--mid   { background: #fff3cd; color: #856404; }
.compile-badge--low   { background: #fee2e2; color: #991b1b; }

/* Generic chip */
.chip {
  display: inline-block;
  font-size: .78rem;
  padding: .1rem .45rem;
  border-radius: 4px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  color: var(--color-text-muted);
}

/* Prompt section */
.prompt-section {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 1rem 1.25rem;
}

.prompt-section__title {
  font-size: .82rem;
  font-weight: 600;
  color: var(--color-text-muted);
  margin-bottom: .5rem;
  text-transform: uppercase;
  letter-spacing: .04em;
}

.prompt-details__summary {
  font-size: .83rem;
  font-weight: 600;
  color: var(--color-accent);
  cursor: pointer;
  user-select: none;
  list-style: none;
}

.prompt-details__summary::-webkit-details-marker { display: none; }
.prompt-details__summary::before { content: '▶ '; font-size: .7rem; }
details[open] .prompt-details__summary::before { content: '▼ '; }

.prompt-pre {
  margin-top: .75rem;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 1rem;
  font-size: .8rem;
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-x: auto;
  line-height: 1.55;
  color: var(--color-text);
}

.prompt-unavailable {
  font-size: .85rem;
  font-style: italic;
}
</style>
