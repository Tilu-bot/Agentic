import { BaseTool, ToolDefinition, ToolInput, ToolResult } from './BaseTool'
import * as fs from 'fs'
import * as path from 'path'

export class ReadFileTool extends BaseTool {
  get definition(): ToolDefinition {
    return {
      name: 'read_file',
      description: 'Read the contents of a file. Returns the full content as text.',
      parameters: {
        type: 'object',
        properties: {
          path: {
            type: 'string',
            description: 'Path to the file, relative to the workspace root or absolute.'
          }
        },
        required: ['path']
      }
    }
  }

  async execute(input: ToolInput, workspacePath: string): Promise<ToolResult> {
    const filePath = this.resolvePath(String(input['path']), workspacePath)
    try {
      const content = fs.readFileSync(filePath, 'utf-8')
      const lines = content.split('\n').length
      return this.ok(
        `File: ${filePath}\nLines: ${lines}\nSize: ${content.length} bytes\n\n${content}`
      )
    } catch (err) {
      return this.err(`Failed to read file: ${String(err)}`)
    }
  }

  private resolvePath(filePath: string, workspacePath: string): string {
    if (path.isAbsolute(filePath)) return filePath
    return path.join(workspacePath, filePath)
  }
}
