# LLM Benchmark Dashboard

Nuxt 4 SSG app for exploring benchmark results. Reads `../results/published/` at build time — all aggregations happen server-side; the client receives only pre-computed JSON.

Drill-down navigation: sessions → session comparison (up to 4 models) → model detail → fixture detail → run detail.

## Setup

```bash
npm install
```

## Scripts

```bash
npm run dev       # dev server on http://localhost:3000
npm run generate  # static build (output: .output/public/)

# GitHub Pages
NUXT_APP_BASE_URL=/llm-benchmark/ npm run generate
```
