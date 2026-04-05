import { BaseTool, ToolDefinition, ToolInput, ToolResult } from './BaseTool'
import * as fs from 'fs'
import * as path from 'path'

export class ApplyDiffTool extends BaseTool {
  get definition(): ToolDefinition {
    return {
      name: 'apply_edit',
      description: 'Apply a targeted edit to a file using search/replace. Finds the exact text block to replace and substitutes it with new content. More precise than write_file for partial edits.',
      parameters: {
        type: 'object',
        properties: {
          path: {
            type: 'string',
            description: 'Path to the file to edit, relative to workspace root or absolute.'
          },
          search: {
            type: 'string',
            description: 'The exact text block to find in the file. Must match exactly, including whitespace and indentation.'
          },
          replace: {
            type: 'string',
            description: 'The text to replace the found block with. Use empty string to delete.'
          },
          description: {
            type: 'string',
            description: 'Short description of this change (e.g., "Fix null pointer in login handler").'
          }
        },
        required: ['path', 'search', 'replace']
      }
    }
  }

  async execute(input: ToolInput, workspacePath: string): Promise<ToolResult> {
    const filePath = this.resolvePath(String(input['path']), workspacePath)
    const searchText = String(input['search'])
    const replaceText = String(input['replace'])

    // Security: ensure the file is inside the workspace
    const resolvedWorkspace = path.resolve(workspacePath)
    const resolvedFile = path.resolve(filePath)
    if (!resolvedFile.startsWith(resolvedWorkspace + path.sep) && resolvedFile !== resolvedWorkspace) {
      return this.err(`Refusing to edit outside workspace: ${filePath}`)
    }

    try {
      let content: string
      if (fs.existsSync(filePath)) {
        content = fs.readFileSync(filePath, 'utf-8')
      } else {
        // File doesn't exist; create it if search is empty
        if (searchText.trim() === '') {
          fs.mkdirSync(path.dirname(filePath), { recursive: true })
          fs.writeFileSync(filePath, replaceText, 'utf-8')
          return this.ok(`Created new file: ${path.relative(workspacePath, filePath)}`)
        }
        return this.err(`File not found: ${filePath}`)
      }

      const occurrences = this.countOccurrences(content, searchText)
      if (occurrences === 0) {
        return this.err(
          `Search text not found in ${path.relative(workspacePath, filePath)}.\n\n` +
          `Searched for:\n${searchText}\n\n` +
          `Tip: Use read_file first to verify the exact content.`
        )
      }
      if (occurrences > 1) {
        return this.err(
          `Search text found ${occurrences} times in ${path.relative(workspacePath, filePath)}. ` +
          `Please make the search text more specific to match exactly one location.`
        )
      }

      const newContent = content.replace(searchText, replaceText)
      fs.writeFileSync(filePath, newContent, 'utf-8')

      const relPath = path.relative(workspacePath, filePath)
      const linesRemoved = searchText.split('\n').length
      const linesAdded = replaceText.split('\n').length
      return this.ok(
        `Applied edit to ${relPath}:\n` +
        `  - Removed ${linesRemoved} lines\n` +
        `  + Added ${linesAdded} lines`
      )
    } catch (err) {
      return this.err(`Failed to apply edit: ${String(err)}`)
    }
  }

  private countOccurrences(text: string, search: string): number {
    if (!search) return 0
    let count = 0
    let pos = 0
    while ((pos = text.indexOf(search, pos)) !== -1) {
      count++
      pos += search.length
    }
    return count
  }

  private resolvePath(filePath: string, workspacePath: string): string {
    if (path.isAbsolute(filePath)) return filePath
    return path.join(workspacePath, filePath)
  }
}
