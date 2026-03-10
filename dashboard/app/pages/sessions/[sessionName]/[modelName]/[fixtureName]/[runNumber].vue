<template>
  <div>
    <Breadcrumb :items="breadcrumb" />

    <div v-if="pending" class="empty-state">Loading…</div>
    <div v-else-if="error" class="empty-state">Failed to load run data.</div>
    <template v-else-if="data">
      <!-- Score summary -->
      <div class="score-summary">
        <ScoreBar :score="data.run.final_score ?? 0" />
        <div class="score-chips">
          <span class="score-chip score-chip--bold" :class="scoreClass(data.run.final_score)">
            {{ (data.run.final_score ?? 0).toFixed(1) }}
          </span>
          <span class="chip chip--label">Pattern {{ data.run.pattern_score?.toFixed(1) ?? '—' }}</span>
          <span class="chip chip--label">Naming {{ data.run.naming_score?.toFixed(1) ?? '—' }}</span>
          <span class="compile-badge" :class="data.run.compiles ? 'compile-badge--great' : 'compile-badge--low'">
            {{ data.run.compiles ? '✓ compile' : '✗ compile' }}
          </span>
        </div>
      </div>

      <!-- Agent meta grid -->
      <template v-if="data.type === 'agent'">
        <div class="meta-grid">
          <div class="meta-item">
            <div class="meta-label">Input tokens</div>
            <div class="meta-value">{{ data.run.total_input_tokens?.toLocaleString() ?? '—' }}</div>
          </div>
          <div class="meta-item">
            <div class="meta-label">Output tokens</div>
            <div class="meta-value">{{ data.run.total_output_tokens?.toLocaleString() ?? '—' }}</div>
          </div>
          <div class="meta-item">
            <div class="meta-label">
              <abbr title="Total smolagents steps consumed. Hard cap defined per task (B:10, C:15, D:20, E:30).">Steps</abbr>
            </div>
            <div class="meta-value">{{ data.run.steps ?? '—' }}</div>
          </div>
          <div class="meta-item">
            <div class="meta-label">
              <abbr title="write_file + run_compilation calls — observational metric, always ≤ steps.">Iterations</abbr>
            </div>
            <div class="meta-value">{{ data.run.iterations ?? '—' }}</div>
          </div>
          <div class="meta-item">
            <div class="meta-label">Compile error recoveries</div>
            <div class="meta-value">{{ data.run.compile_error_recovery_count ?? '—' }}</div>
          </div>
          <div v-if="data.run.rag_queries_count > 0" class="meta-item">
            <div class="meta-label">RAG queries</div>
            <div class="meta-value">{{ data.run.rag_queries_count }}</div>
          </div>
          <div v-if="data.run.read_file_count > 0" class="meta-item">
            <div class="meta-label">File reads</div>
            <div class="meta-value">{{ data.run.read_file_count }}</div>
          </div>
          <div v-if="data.run.list_files_count > 0" class="meta-item">
            <div class="meta-label">List files</div>
            <div class="meta-value">{{ data.run.list_files_count }}</div>
          </div>
          <div v-if="data.run.first_compile_success_step != null" class="meta-item">
            <div class="meta-label">First compile success</div>
            <div class="meta-value">step {{ data.run.first_compile_success_step }}</div>
          </div>
        </div>

        <!-- Full tool_call_log timeline -->
        <div v-if="data.run.tool_call_log?.length" class="section">
          <h2 class="section-title">Tool call log</h2>
          <div class="timeline">
            <div v-for="step in data.run.tool_call_log" :key="step.step" class="timeline__row">
              <div class="timeline__step">{{ step.step }}</div>
              <span class="tool-pill" :class="toolPillClass(step.tool)" :title="TOOL_DESC[step.tool] ?? step.tool">{{ step.tool }}</span>
              <span v-if="step.compile_passed === true" class="icon-ok">✓</span>
              <span v-else-if="step.compile_passed === false" class="icon-fail">✗</span>
              <span v-else class="icon-null">—</span>
              <span class="chip chip--sm">{{ step.duration_sec?.toFixed(1) ?? '—' }}s</span>
              <span class="chip chip--sm">{{ formatCtx(step.context_chars) }}</span>
              <span class="timeline__summary">{{ step.result_summary }}</span>
            </div>
          </div>
        </div>
      </template>

      <!-- AST checks grid -->
      <div v-if="allChecks.length" class="section">
        <h2 class="section-title">AST checks</h2>
        <div class="checks-grid">
          <div
            v-for="check in allChecks"
            :key="check.name"
            class="check-item"
            :class="check.passed ? 'check-item--ok' : 'check-item--fail'"
          >
            <span v-if="check.passed" class="icon-ok">✓</span>
            <span v-else class="icon-fail">✗</span>
            <span class="check-name">{{ formatCheckName(check.name) }}</span>
          </div>
        </div>
      </div>

      <!-- Naming violations -->
      <div v-if="data.run.naming_violations?.length" class="section">
        <h2 class="section-title">Naming violations</h2>
        <div class="violations-box">
          <div v-for="(v, i) in data.run.naming_violations" :key="i" class="violation-item">{{ v }}</div>
        </div>
      </div>

      <!-- Compilation errors -->
      <div v-if="data.run.compilation_errors?.length" class="section">
        <h2 class="section-title">Compilation errors</h2>
        <pre
          v-for="(e, i) in data.run.compilation_errors"
          :key="i"
          class="compile-pre compile-pre--error"
        >{{ e }}</pre>
      </div>

      <!-- Compilation warnings -->
      <div v-if="data.run.compilation_warnings?.length" class="section">
        <h2 class="section-title">Compilation warnings</h2>
        <pre
          v-for="(w, i) in data.run.compilation_warnings"
          :key="i"
          class="compile-pre compile-pre--warn"
        >{{ w }}</pre>
      </div>

      <!-- Output code -->
      <div v-if="data.run.output_code" class="section">
        <details open>
          <summary class="output-summary">Generated output</summary>
          <pre class="code-block"><code>{{ data.run.output_code }}</code></pre>
        </details>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const sessionName = route.params.sessionName as string
const modelName = route.params.modelName as string
const fixtureName = route.params.fixtureName as string
const runNumber = route.params.runNumber as string

const { data, pending, error } = await useAsyncData(
  `run-${sessionName}-${modelName}-${fixtureName}-${runNumber}`,
  () => $fetch<any>(`/api/sessions/${sessionName}/${modelName}/${fixtureName}/${runNumber}`)
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
  { label: `${data.value?.fixtureLabel ?? fixtureName} — Run ${runNumber}` },
])

// ast_checks is a dict { checkName: boolean } — convert to sorted array
const allChecks = computed(() => {
  const checks = data.value?.run?.ast_checks
  if (!checks || typeof checks !== 'object') return []
  return Object.entries(checks).map(([name, passed]) => ({ name, passed: Boolean(passed) }))
})

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

const TOOL_DESC: Record<string, string> = {
  write_file:       'Write or overwrite a file in the target project',
  run_compilation:  'Run vue-tsc type-check and return errors/warnings',
  query_rag:        'BM25 search over component API documentation',
  read_file:        'Read any file from the project filesystem',
  list_files:       'List directory contents to explore project structure',
}

function formatCtx(chars: number | null | undefined): string {
  if (chars == null) return '—'
  if (chars >= 1000) return (chars / 1000).toFixed(1) + 'k ctx'
  return chars + ' ctx'
}

function formatCheckName(name: string): string {
  return name.replace(/([A-Z])/g, ' $1').trim()
}
</script>

<style scoped>
.empty-state {
  text-align: center;
  padding: 3rem;
  color: var(--color-text-muted);
}

/* Score summary */
.score-summary {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1.5rem;
  padding: 1rem 1.25rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}

.score-chips {
  display: flex;
  align-items: center;
  gap: .5rem;
  flex-wrap: wrap;
}

.score-chip {
  display: inline-block;
  font-size: .82rem;
  padding: .15rem .5rem;
  border-radius: 4px;
}

.score-chip--bold {
  font-weight: 700;
  font-size: .95rem;
}

.score-chip--great { background: #d1fae5; color: #065f46; }
.score-chip--good  { background: #dbeafe; color: #1e40af; }
.score-chip--mid   { background: #fff3cd; color: #856404; }
.score-chip--low   { background: #fee2e2; color: #991b1b; }

.chip {
  display: inline-block;
  font-size: .78rem;
  padding: .1rem .45rem;
  border-radius: 4px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  color: var(--color-text-muted);
}

.chip--sm    { font-size: .75rem; padding: .08rem .35rem; }
.chip--label { color: var(--color-text); }

.compile-badge {
  display: inline-block;
  font-size: .78rem;
  padding: .15rem .5rem;
  border-radius: 4px;
  font-weight: 600;
}

.compile-badge--great { background: #d1fae5; color: #065f46; }
.compile-badge--low   { background: #fee2e2; color: #991b1b; }

/* Meta grid */
.meta-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: .75rem;
  margin-bottom: 1.5rem;
}

.meta-item {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: .65rem .85rem;
}

.meta-label {
  font-size: .75rem;
  color: var(--color-text-muted);
  margin-bottom: .2rem;
}

.meta-label abbr {
  text-decoration: underline dotted;
  cursor: help;
}

.meta-value {
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
}

/* Sections */
.section {
  margin-bottom: 1.5rem;
}

.section-title {
  font-size: .95rem;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: .75rem;
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
  display: flex;
  flex-direction: column;
  gap: .5rem;
}

.timeline__row {
  display: flex;
  align-items: center;
  gap: .5rem;
  flex-wrap: wrap;
  padding: .4rem .75rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
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
  flex: 1;
  min-width: 0;
  word-break: break-word;
}

/* AST checks grid */
.checks-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: .4rem;
}

.check-item {
  display: flex;
  align-items: center;
  gap: .5rem;
  font-size: .85rem;
  padding: .35rem .6rem;
  border-radius: 4px;
}

.check-item--ok      { background: #f0fdf4; }
.check-item--fail    { background: #fef2f2; }
.check-item--missing { background: #fef2f2; }

.check-name { color: var(--color-text); }

/* Violations */
.violations-box {
  background: #fffbeb;
  border: 1px solid #fcd34d;
  border-radius: var(--radius);
  padding: .75rem 1rem;
}

.violation-item {
  font-size: .85rem;
  font-family: monospace;
  color: #78350f;
  padding: .1rem 0;
}

/* Compilation pre blocks */
.compile-pre {
  font-size: .85rem;
  padding: .75rem;
  border-radius: var(--radius);
  overflow-x: auto;
  white-space: pre;
  margin: 0 0 .5rem;
}

.compile-pre--error {
  background: #fef2f2;
  color: #7f1d1d;
}

.compile-pre--warn {
  background: #fffbeb;
  color: #78350f;
}

/* Output code */
.output-summary {
  cursor: pointer;
  font-size: .9rem;
  font-weight: 600;
  color: var(--color-text);
  padding: .4rem 0;
  list-style: none;
  user-select: none;
}

.output-summary::-webkit-details-marker { display: none; }

.output-summary::before {
  content: '▶ ';
  font-size: .75rem;
}

details[open] .output-summary::before {
  content: '▼ ';
}

.code-block {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 1rem;
  border-radius: var(--radius);
  overflow-x: auto;
  font-size: .82rem;
  line-height: 1.5;
  white-space: pre;
  margin-top: .5rem;
}

.code-block code {
  background: transparent;
  color: inherit;
  font-size: inherit;
  padding: 0;
  border: none;
  border-radius: 0;
  display: block;
}
</style>
