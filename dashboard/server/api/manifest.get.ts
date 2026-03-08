import { readdirSync, existsSync, statSync } from 'node:fs'
import { resolve, join } from 'node:path'

const PUBLISHED_DIR = resolve(process.cwd(), '../results/published')

function parseSessionFolder(name: string) {
  const match = name.match(/^session__(.+?)(?:__(\d+))?$/)
  if (!match) return null
  return {
    folder: name,
    displayName: match[1],
    timestamp: match[2] ? parseInt(match[2]) : null,
  }
}

export default defineEventHandler(() => {
  if (!existsSync(PUBLISHED_DIR)) {
    return { sessions: [] }
  }

  const sessions = readdirSync(PUBLISHED_DIR, { withFileTypes: true })
    .filter(e => e.isDirectory() && e.name.startsWith('session__'))
    .map(e => {
      const meta = parseSessionFolder(e.name)
      if (!meta) return null

      const sessionDir = join(PUBLISHED_DIR, e.name)
      const modelDirs = readdirSync(sessionDir, { withFileTypes: true })
        .filter(m => m.isDirectory())

      const modelNames = modelDirs.map(m => m.name.replace('__', ':'))
      const fixtureSet = new Set<string>()

      for (const modelEntry of modelDirs) {
        const modelDir = join(sessionDir, modelEntry.name)
        for (const entry of readdirSync(modelDir, { withFileTypes: true })) {
          if (entry.isFile() && entry.name.endsWith('.json')) {
            const withoutModel = entry.name.replace('.json', '').substring(modelEntry.name.length + 2)
            const lastIdx = withoutModel.lastIndexOf('__')
            if (lastIdx > 0) fixtureSet.add(withoutModel.substring(0, lastIdx))
          } else if (entry.isDirectory()) {
            const withoutModel = entry.name.substring(modelEntry.name.length + 2)
            const m = withoutModel.match(/^(.+)__\d+runs__\d+$/)
            if (m) fixtureSet.add(m[1])
          }
        }
      }

      // Use folder mtime as fallback timestamp
      const ts = meta.timestamp ?? Math.floor(statSync(join(PUBLISHED_DIR, e.name)).mtimeMs / 1000)

      return {
        folder: meta.folder,
        displayName: meta.displayName,
        timestamp: ts,
        modelCount: modelNames.length,
        fixtureCount: fixtureSet.size,
        modelNames,
      }
    })
    .filter(Boolean)
    .sort((a, b) => (b!.timestamp ?? 0) - (a!.timestamp ?? 0))

  return { sessions }
})
