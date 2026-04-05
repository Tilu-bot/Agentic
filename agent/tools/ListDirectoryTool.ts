import { BaseTool, ToolDefinition, ToolInput, ToolResult } from './BaseTool'
import * as fs from 'fs'
import * as path from 'path'

export class ListDirectoryTool extends BaseTool {
  get definition(): ToolDefinition {
    return {
      name: 'list_directory',
      description: 'List the contents of a directory (files and subdirectories). Use this to explore the project structure.',
      parameters: {
        type: 'object',
        properties: {
          path: {
            type: 'string',
            description: 'Directory path, relative to workspace root or absolute. Use "." for workspace root.'
          },
          recursive: {
            type: 'boolean',
            description: 'If true, list contents recursively up to depth 3. Default is false.'
          }
        },
        required: ['path']
      }
    }
  }

  async execute(input: ToolInput, workspacePath: string): Promise<ToolResult> {
    const inputPath = String(input['path'] ?? '.')
    const recursive = Boolean(input['recursive'] ?? false)
    const dirPath = path.isAbsolute(inputPath) ? inputPath : path.join(workspacePath, inputPath)

    try {
      if (!fs.existsSync(dirPath)) {
        return this.err(`Directory not found: ${dirPath}`)
      }
      const stat = fs.statSync(dirPath)
      if (!stat.isDirectory()) {
        return this.err(`Not a directory: ${dirPath}`)
      }

      const lines: string[] = []
      this.walkDir(dirPath, workspacePath, lines, recursive ? 0 : -1, 3)

      return this.ok(lines.join('\n'))
    } catch (err) {
      return this.err(`Failed to list directory: ${String(err)}`)
    }
  }

  private walkDir(dirPath: string, workspacePath: string, lines: string[], depth: number, maxDepth: number): void {
    try {
      const entries = fs.readdirSync(dirPath, { withFileTypes: true })
      const sorted = entries.sort((a, b) => {
        if (a.isDirectory() !== b.isDirectory()) return a.isDirectory() ? -1 : 1
        return a.name.localeCompare(b.name)
      })

      const SKIP = new Set(['node_modules', '.git', '__pycache__', 'dist', 'dist-electron', '.next', 'build', 'coverage', '.cache'])

      for (const entry of sorted) {
        if (SKIP.has(entry.name)) continue

        const relPath = path.relative(workspacePath, path.join(dirPath, entry.name))
        const indent = '  '.repeat(Math.max(0, depth))
        const marker = entry.isDirectory() ? '📁' : '📄'
        lines.push(`${indent}${marker} ${relPath}`)

        if (entry.isDirectory() && depth < maxDepth) {
          this.walkDir(path.join(dirPath, entry.name), workspacePath, lines, depth + 1, maxDepth)
        }
      }
    } catch {
      // Skip inaccessible dirs
    }
  }
}
