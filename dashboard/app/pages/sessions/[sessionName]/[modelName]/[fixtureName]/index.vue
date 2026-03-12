<template>
  <div>
    <Breadcrumb :items="breadcrumb" />

    <div v-if="pending" class="empty-state">Loading…</div>
    <div v-else-if="error" class="empty-state">Failed to load fixture data.</div>
    <template v-else-if="data">
      <h1 class="page-title">{{ data.label }}</h1>
      <p v-if="FIXTURE_META[fixtureName]" class="fixture-desc">{{ FIXTURE_META[fixtureName].desc }}</p>

      <div v-for="run in data.runs" :key="run.run_number" class="run-card">
        <!-- Card header -->
        <div class="run-card__header">
          <span class="run-card__title">Run {{ run.run_number }}</span>
          <div class="run-chips">
            <span class="score-chip" :class="scoreClass(run.final_score)">
              {{ (run.final_score ?? 0).toFixed(1) }}
            </span>
            <span class="chip chip--label">Pattern {{ run.pattern_score?.toFixed(1) ?? '—' }}</span>
            <span class="chip chip--label">Naming {{ run.naming_score?.toFixed(1) ?? '—' }}</span>
            <span class="compile-badge" :class="run.compiles ? 'compile-badge--great' : 'compile-badge--low'">
              {{ run.compiles ? '✓ compile' : '✗ compile' }}
            </span>
            <span v-if="run.aborted" class="aborted-badge">⚠ aborted</span>
          </div>
        </div>

        <!-- Agent: tool_call_log timeline -->
        <div v-if="data.type === 'agent' && run.tool_call_log?.length" class="timeline">
          <div v-for="step in run.tool_call_log" :key="step.step" class="timeline__row">
            <div class="timeline__step">{{ step.step }}</div>
            <span class="tool-pill" :class="toolPillClass(step.tool)" :title="TOOL_DESC[step.tool] ?? step.tool">{{ step.tool }}</span>
            <span v-if="step.compile_passed === true" class="icon-ok">✓</span>
            <span v-else-if="step.compile_passed === false" class="icon-fail">✗</span>
            <span v-else class="icon-null">—</span>
            <span class="chip chip--sm">{{ step.duration_sec?.toFixed(1) ?? '—' }}s</span>
            <span class="chip chip--sm">{{ formatCtx(step.context_chars) }}</span>
            <span
              class="timeline__summary"
              :title="step.result_summary"
            >{{ truncate(step.result_summary, 120) }}</span>
          </div>
        </div>

        <!-- Oneshot: checks + violations + errors -->
        <div v-else-if="data.type === 'oneshot'" class="oneshot-detail">
          <div v-if="astChecksArray(run).length" class="checks-list">
            <div v-for="check in astChecksArray(run)" :key="check.name" class="check-row">
              <span v-if="check.passed" class="icon-ok">✓</span>
              <span v-else class="icon-fail">✗</span>
              <span class="check-name">{{ check.name }}</span>
            </div>
          </div>
          <div v-if="run.naming_violations?.length" class="violations-list">
            <div class="violations-title">Naming violations</div>
            <div v-for="(v, i) in run.naming_violations" :key="i" class="violation-item">{{ v }}</div>
          </div>
          <div v-if="run.compilation_errors?.length" class="compile-errors">
            <div class="compile-errors__title">Compilation errors</div>
            <pre v-for="(e, i) in run.compilation_errors" :key="i" class="compile-pre">{{ e }}</pre>
          </div>
        </div>

        <!-- Footer link -->
        <div class="run-card__footer">
          <NuxtLink
            :to="`/sessions/${sessionName}/${modelName}/${fixtureName}/${run.run_number}`"
            class="view-link"
          >View full output →</NuxtLink>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const sessionName = route.params.sessionName as string
const modelName = route.params.modelName as string
const fixtureName = route.params.fixtureName as string

const FIXTURE_META: Record<string, { desc: string }> = {
  'nuxt-form-oneshot':        { desc: 'One shot, no tools. The model must produce a correct RegistrationForm.vue in a single response. Full component API documented inline in the prompt.' },
  'nuxt-form-agent-guided':   { desc: 'Agentic loop with write_file + run_compilation. Iterate on TypeScript compiler feedback until the code passes or the step budget (10) runs out.' },
  'nuxt-form-agent-twofiles': { desc: 'Same as B, but must produce two coordinated files in order: registration/types/index.ts (Zod schema + types) then RegistrationForm.vue importing from it.' },
  'nuxt-form-agent-rag':      { desc: 'No inline API docs in the prompt. The model must call query_rag to look up component usage examples from a BM25 document store before writing.' },
  'nuxt-form-agent-full':     { desc: 'Full tool access: list_files, read_file, write_file, run_compilation, query_rag. The model can explore the project freely — closest to real-world agentic coding.' },
}

const TOOL_DESC: Record<string, string> = {
  write_file:       'Write or overwrite a file in the target project',
  run_compilation:  'Run vue-tsc type-check and return errors/warnings',
  query_rag:        'BM25 search over component API documentation',
  read_file:        'Read any file from the project filesystem',
  list_files:       'List directory contents to explore project structure',
}

const { data, pending, error } = await useAsyncData(
  `fixture-${sessionName}-${modelName}-${fixtureName}`,
  () => $fetch<any>(`/api/sessions/${sessionName}/${modelName}/${fixtureName}`)
)

const sessionDisplayName = computed(() => {
  const m = sessionName.match(/^session__(.+?)(?:__\d+)?$/)
  return m ? m[1].replace('__', ':') : sessionName
})

const modelDisplayName = computed(() => modelName.replace('__', ':'))

const breadcrumb = computed(() => [
  { label: 'Sessions', to: '/' },
  { label: sessionDisplayName.value, to: '/sessions/' + sessionName },
  { label: modelDisplayName.value, to: `/sessions/${sessionName}/${modelName}` },
  { label: data.value?.label ?? fixtureName },
])

function astChecksArray(run: any): { name: string; passed: boolean }[] {
  const checks = run?.ast_checks
  if (!checks || typeof checks !== 'object') return []
  return Object.entries(checks).map(([name, passed]) => ({ name, passed: Boolean(passed) }))
}

function scoreClass(score: number): string {
  if (score >= 8) return 'score-chip--great'
  if (score >= 6) return 'score-chip--good'
  if (score >= 3) return 'score-chip--mid'
  return 'score-chip--low'
}

function toolPillClass(tool: string): string {
  if (tool === 'write_file') return 'tool-pill--blue'
  if (tool === 'run_compilation') return 'tool-pill--orange'
  if (tool === 'query_rag') return 'tool-pill--purple'
  return 'tool-pill--gray'
}

function truncate(text: string | null | undefined, max: number): string {
  if (!text) return ''
  return text.length <= max ? text : text.slice(0, max) + '…'
}

function formatCtx(chars: number | null | undefined): string {
  if (chars == null) return '—'
  if (chars >= 1000) return (chars / 1000).toFixed(1) + 'k ctx'
  return chars + ' ctx'
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

/* Run card */
.run-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  margin-bottom: 1.25rem;
  overflow: hidden;
}

.run-card__header {
  display: flex;
  align-items: center;
  gap: .75rem;
  padding: .75rem 1rem;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg);
  flex-wrap: wrap;
}

.run-card__title {
  font-weight: 700;
  font-size: .95rem;
  margin-right: auto;
}

.run-chips {
  display: flex;
  align-items: center;
  gap: .4rem;
  flex-wrap: wrap;
}

/* Score chips */
.score-chip {
  display: inline-block;
  font-size: .8rem;
  font-weight: 700;
  padding: .15rem .5rem;
  border-radius: 4px;
}

.score-chip--great { background: #d1fae5; color: #065f46; }
.score-chip--good  { background: #dbeafe; color: #1e40af; }
.score-chip--mid   { background: #fff3cd; color: #856404; }
.score-chip--low   { background: #fee2e2; color: #991b1b; }

/* Generic chips */
.chip {
  display: inline-block;
  font-size: .78rem;
  padding: .1rem .45rem;
  border-radius: 4px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  color: var(--color-text-muted);
}

.chip--sm {
  font-size: .75rem;
  padding: .08rem .35rem;
}

.chip--label {
  color: var(--color-text);
}

/* Compile badge */
.compile-badge {
  display: inline-block;
  font-size: .75rem;
  padding: .15rem .5rem;
  border-radius: 4px;
  font-weight: 600;
}

.compile-badge--great { background: #d1fae5; color: #065f46; }
.compile-badge--low   { background: #fee2e2; color: #991b1b; }

/* Aborted badge */
.aborted-badge {
  display: inline-block;
  font-size: .72rem;
  padding: .1rem .45rem;
  border-radius: 4px;
  background: #fee2e2;
  color: #991b1b;
  font-weight: 600;
}

/* Tool pills */
.tool-pill {
  display: inline-block;
  font-size: .75rem;
  font-family: monospace;
  padding: .1rem .45rem;
  border-radius: 4px;
  font-weight: 600;
  white-space: nowrap;
}

.tool-pill--blue   { background: #dbeafe; color: #1e40af; }
.tool-pill--orange { background: #ffedd5; color: #9a3412; }
.tool-pill--purple { background: #ede9fe; color: #5b21b6; }
.tool-pill--gray   { background: var(--color-bg); color: var(--color-text-muted); border: 1px solid var(--color-border); }

/* Icons */
.icon-ok   { color: var(--color-score-great); font-weight: 700; }
.icon-fail { color: var(--color-score-low);   font-weight: 700; }
.icon-null { color: var(--color-text-muted); }

/* Timeline */
.timeline {
  padding: .75rem 1rem;
  display: flex;
  flex-direction: column;
  gap: .45rem;
}

.timeline__row {
  display: flex;
  align-items: center;
  gap: .5rem;
  flex-wrap: wrap;
}

.timeline__step {
  width: 1.5rem;
  height: 1.5rem;
  border-radius: 50%;
  background: var(--color-border);
  color: var(--color-text-muted);
  font-size: .72rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.timeline__summary {
  font-size: .8rem;
  color: var(--color-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 400px;
  cursor: default;
}

/* Oneshot detail */
.oneshot-detail {
  padding: .75rem 1rem;
  display: flex;
  flex-direction: column;
  gap: .75rem;
}

.checks-list {
  display: flex;
  flex-direction: column;
  gap: .3rem;
}

.check-row {
  display: flex;
  align-items: center;
  gap: .5rem;
  font-size: .85rem;
}

.check-name {
  color: var(--color-text);
}

.violations-list {
  background: #fffbeb;
  border: 1px solid #fcd34d;
  border-radius: var(--radius);
  padding: .6rem .75rem;
}

.violations-title {
  font-size: .8rem;
  font-weight: 600;
  color: #92400e;
  margin-bottom: .4rem;
}

.violation-item {
  font-size: .82rem;
  font-family: monospace;
  color: #78350f;
}

.compile-errors__title {
  font-size: .8rem;
  font-weight: 600;
  color: #991b1b;
  margin-bottom: .4rem;
}

.compile-pre {
  background: #fef2f2;
  color: #7f1d1d;
  font-size: .82rem;
  padding: .5rem .75rem;
  border-radius: var(--radius);
  overflow-x: auto;
  white-space: pre;
  margin: 0;
}

/* Footer */
.run-card__footer {
  padding: .6rem 1rem;
  border-top: 1px solid var(--color-border);
  text-align: right;
}

.view-link {
  font-size: .83rem;
  color: var(--color-accent);
  text-decoration: none;
}

.view-link:hover {
  text-decoration: underline;
}
</style>
