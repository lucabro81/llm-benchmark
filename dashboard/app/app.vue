<template>
  <div class="app">
    <header class="site-header">
      <NuxtLink to="/" class="logo">🤖 LLM Benchmark</NuxtLink>
    </header>
    <main class="site-main">
      <NuxtPage />
    </main>
    <footer class="site-footer">
      <a href="https://github.com/lucabro81/llm-benchmark" target="_blank" rel="noopener">LLM Benchmark Suite</a>
      <span class="footer-sep">·</span>
      <a href="https://github.com/lucabro81/llm-benchmark/tree/main/results/published" target="_blank" rel="noopener">Published data</a>
    </footer>
  </div>
</template>

<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --color-bg: #f8f9fa;
  --color-surface: #ffffff;
  --color-border: #dee2e6;
  --color-text: #212529;
  --color-text-muted: #6c757d;
  --color-accent: #0d6efd;
  --color-score-great: #198754;
  --color-score-good: #0d6efd;
  --color-score-mid: #fd7e14;
  --color-score-low: #dc3545;
  --radius: 8px;
  --shadow: 0 1px 3px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.06);
}

body {
  font-family: system-ui, -apple-system, sans-serif;
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 15px;
  line-height: 1.5;
}

a { color: var(--color-accent); text-decoration: none; }
a:hover { text-decoration: underline; }

.app { min-height: 100vh; display: flex; flex-direction: column; }

.site-header {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  padding: 0 2rem;
  height: 56px;
  display: flex;
  align-items: center;
}
.logo { font-weight: 700; font-size: 1.1rem; color: var(--color-text); }
.logo:hover { text-decoration: none; }

.site-main { flex: 1; padding: 2rem; max-width: 1200px; margin: 0 auto; width: 100%; }

.site-footer {
  border-top: 1px solid var(--color-border);
  padding: 1rem 2rem;
  text-align: center;
  color: var(--color-text-muted);
  font-size: 0.85rem;
}
code { font-size: 0.85em; background: var(--color-bg); padding: 0.1em 0.3em; border-radius: 3px; }
.footer-sep { margin: 0 0.5rem; }
</style>
