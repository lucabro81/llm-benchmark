<template>
  <div>
    <h1 class="page-title">Sessions</h1>

    <div v-if="pending" class="empty-state">Loading…</div>
    <div v-else-if="!manifest?.sessions?.length" class="empty-state">
      No published sessions yet.<br>
      <small>Run a benchmark with <code>--session-name</code> and copy results to <code>results/published/</code>.</small>
    </div>

    <div v-else class="sessions-grid">
      <NuxtLink
        v-for="s in manifest.sessions"
        :key="s.folder"
        :to="`/sessions/${s.folder}`"
        class="session-card"
      >
        <div class="session-card__name">{{ s.displayName }}</div>
        <div class="session-card__meta">
          {{ s.modelCount }} {{ s.modelCount === 1 ? 'model' : 'models' }} ·
          {{ s.fixtureCount }} {{ s.fixtureCount === 1 ? 'fixture' : 'fixtures' }}
        </div>
        <ul class="session-card__models">
          <li v-for="m in s.modelNames" :key="m">{{ m }}</li>
        </ul>
        <div v-if="s.timestamp" class="session-card__date">
          {{ new Date(s.timestamp * 1000).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) }}
        </div>
      </NuxtLink>
    </div>
  </div>
</template>

<script setup lang="ts">
const { data: manifest, pending } = await useAsyncData('manifest', () =>
  $fetch<{ sessions: any[] }>('/api/manifest')
)
</script>

<style scoped>
.page-title { font-size: 1.5rem; font-weight: 700; margin-bottom: 1.5rem; }

.empty-state {
  text-align: center;
  padding: 3rem;
  color: var(--color-text-muted);
  line-height: 2;
}

.sessions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.session-card {
  display: block;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 1.25rem;
  box-shadow: var(--shadow);
  transition: border-color .15s, box-shadow .15s;
  color: var(--color-text);
}
.session-card:hover {
  border-color: var(--color-accent);
  box-shadow: 0 4px 12px rgba(13,110,253,.12);
  text-decoration: none;
}

.session-card__name {
  font-size: 1.05rem;
  font-weight: 600;
  margin-bottom: .35rem;
}
.session-card__meta {
  font-size: .85rem;
  color: var(--color-text-muted);
  margin-bottom: .75rem;
}
.session-card__models {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: .25rem;
}
.session-card__models li {
  font-size: .8rem;
  font-family: monospace;
  background: var(--color-bg);
  padding: .2rem .5rem;
  border-radius: 4px;
  border: 1px solid var(--color-border);
}
.session-card__date {
  margin-top: .75rem;
  font-size: .8rem;
  color: var(--color-text-muted);
}
</style>
