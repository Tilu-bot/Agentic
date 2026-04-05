import { BaseTool, ToolDefinition, ToolInput, ToolResult } from './BaseTool'
import * as fs from 'fs'
import * as path from 'path'

const MAX_RESULTS = 100
const SKIP_DIRS = new Set(['node_modules', '.git', '__pycache__', 'dist', 'dist-electron', '.next', 'build', 'coverage', '.cache', 'venv', '.venv'])

export class SearchFilesTool extends BaseTool {
  get definition(): ToolDefinition {
    return {
      name: 'search_files',
      description: 'Search for a text pattern in files across the workspace. Returns matching lines with file paths and line numbers. Useful for finding usages, definitions, or specific strings.',
      parameters: {
        type: 'object',
        properties: {
          pattern: {
            type: 'string',
            description: 'Text or regex pattern to search for.'
          },
          regex: {
            type: 'boolean',
            description: 'If true, treat pattern as a regular expression. Default is false (literal text search).'
          },
          case_sensitive: {
            type: 'boolean',
            description: 'If false, perform case-insensitive search. Default is false.'
          },
          file_pattern: {
            type: 'string',
            description: 'Comma-separated list of file extensions to search in (e.g., "ts,js,py"). If omitted, searches all text files.'
          },
          directory: {
            type: 'string',
            description: 'Subdirectory to search in (relative to workspace root). Default is workspace root.'
          }
        },
        required: ['pattern']
      }
    }
  }

  async execute(input: ToolInput, workspacePath: string): Promise<ToolResult> {
    const pattern = String(input['pattern'])
    const isRegex = Boolean(input['regex'] ?? false)
    const caseSensitive = Boolean(input['case_sensitive'] ?? false)
    const filePatternRaw = input['file_pattern'] ? String(input['file_pattern']) : null
    const dirRel = input['directory'] ? String(input['directory']) : '.'
    const searchDir = path.isAbsolute(dirRel) ? dirRel : path.join(workspacePath, dirRel)

    const allowedExts = filePatternRaw
      ? new Set(filePatternRaw.split(',').map((e) => e.trim().replace(/^\./, '')))
      : null

    let searchRegex: RegExp
    try {
      const flags = caseSensitive ? 'g' : 'gi'
      searchRegex = isRegex
        ? new RegExp(pattern, flags)
        : new RegExp(pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), flags)
    } catch (err) {
      return this.err(`Invalid regex pattern: ${err}`)
    }

    const results: string[] = []

    const walkDir = (dirPath: string): void => {
      if (results.length >= MAX_RESULTS) return
      try {
        const entries = fs.readdirSync(dirPath, { withFileTypes: true })
        for (const entry of entries) {
          if (results.length >= MAX_RESULTS) break
          if (SKIP_DIRS.has(entry.name)) continue

          const fullPath = path.join(dirPath, entry.name)
          if (entry.isDirectory()) {
            walkDir(fullPath)
          } else {
            if (allowedExts) {
              const ext = path.extname(entry.name).replace('.', '')
              if (!allowedExts.has(ext)) continue
            }
            this.searchInFile(fullPath, workspacePath, searchRegex, results)
          }
        }
      } catch {
        // Skip inaccessible
      }
    }

    walkDir(searchDir)

    if (results.length === 0) {
      return this.ok(`No matches found for "${pattern}"`)
    }

    const header = `Found ${results.length}${results.length >= MAX_RESULTS ? '+' : ''} matches for "${pattern}":\n\n`
    return this.ok(header + results.join('\n'))
  }

  private searchInFile(filePath: string, workspacePath: string, regex: RegExp, results: string[]): void {
    try {
      const content = fs.readFileSync(filePath, 'utf-8')
      // Skip binary files
      if (content.includes('\x00')) return

      const lines = content.split('\n')
      const relPath = path.relative(workspacePath, filePath)

      for (let i = 0; i < lines.length && results.length < MAX_RESULTS; i++) {
        regex.lastIndex = 0
        if (regex.test(lines[i])) {
          results.push(`${relPath}:${i + 1}: ${lines[i].trim()}`)
        }
      }
    } catch {
      // Skip unreadable files
    }
  }
}
