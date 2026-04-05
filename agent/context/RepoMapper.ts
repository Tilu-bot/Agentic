import * as fs from 'fs'
import * as path from 'path'

const SKIP_DIRS = new Set(['node_modules', '.git', '__pycache__', 'dist', 'dist-electron', '.next', 'build', 'coverage', '.cache', 'venv', '.venv', '.DS_Store'])
const MAX_FILES = 200

interface FileInfo {
  relPath: string
  ext: string
  size: number
}

export class RepoMapper {
  buildMap(workspacePath: string): string {
    const files: FileInfo[] = []
    this.walkDir(workspacePath, workspacePath, files, 0)

    const lines: string[] = []
    lines.push(`Workspace: ${workspacePath}`)
    lines.push(`Files: ${files.length}`)
    lines.push('')

    // Group by directory
    const byDir = new Map<string, FileInfo[]>()
    for (const f of files) {
      const dir = path.dirname(f.relPath) || '.'
      if (!byDir.has(dir)) byDir.set(dir, [])
      byDir.get(dir)!.push(f)
    }

    // Language stats
    const langCounts = new Map<string, number>()
    for (const f of files) {
      const ext = f.ext || 'other'
      langCounts.set(ext, (langCounts.get(ext) ?? 0) + 1)
    }
    const topLangs = Array.from(langCounts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([ext, count]) => `  ${ext}: ${count} files`)
      .join('\n')

    lines.push('Language breakdown:')
    lines.push(topLangs)
    lines.push('')
    lines.push('Directory structure:')

    for (const [dir, dirFiles] of byDir) {
      lines.push(`  ${dir}/`)
      for (const f of dirFiles.slice(0, 20)) {
        lines.push(`    ${path.basename(f.relPath)} (${this.formatSize(f.size)})`)
      }
      if (dirFiles.length > 20) {
        lines.push(`    ... and ${dirFiles.length - 20} more files`)
      }
    }

    // Key files
    const keyFiles = ['package.json', 'README.md', 'pyproject.toml', 'Cargo.toml', 'go.mod', 'composer.json', 'Gemfile', 'requirements.txt', 'setup.py']
    const foundKeyFiles = files.filter((f) => keyFiles.includes(path.basename(f.relPath)))
    if (foundKeyFiles.length > 0) {
      lines.push('')
      lines.push('Key project files:')
      for (const f of foundKeyFiles) {
        lines.push(`  ${f.relPath}`)
      }
    }

    return lines.join('\n')
  }

  private walkDir(dirPath: string, workspacePath: string, files: FileInfo[], depth: number): void {
    if (depth > 5 || files.length >= MAX_FILES) return
    try {
      const entries = fs.readdirSync(dirPath, { withFileTypes: true })
      for (const entry of entries) {
        if (files.length >= MAX_FILES) break
        if (SKIP_DIRS.has(entry.name)) continue

        const fullPath = path.join(dirPath, entry.name)
        if (entry.isDirectory()) {
          this.walkDir(fullPath, workspacePath, files, depth + 1)
        } else {
          try {
            const stat = fs.statSync(fullPath)
            files.push({
              relPath: path.relative(workspacePath, fullPath),
              ext: path.extname(entry.name).replace('.', '') || 'noext',
              size: stat.size
            })
          } catch {
            // Skip inaccessible files
          }
        }
      }
    } catch {
      // Skip inaccessible directories
    }
  }

  private formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes}B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
    return `${(bytes / 1024 / 1024).toFixed(1)}MB`
  }
}
