import { BaseTool, ToolDefinition, ToolInput, ToolResult } from './BaseTool'
import * as fs from 'fs'
import * as path from 'path'

export class WriteFileTool extends BaseTool {
  get definition(): ToolDefinition {
    return {
      name: 'write_file',
      description: 'Write content to a file. Creates the file and any parent directories if they do not exist. Overwrites existing content.',
      parameters: {
        type: 'object',
        properties: {
          path: {
            type: 'string',
            description: 'Path to the file, relative to the workspace root or absolute.'
          },
          content: {
            type: 'string',
            description: 'The full content to write to the file.'
          }
        },
        required: ['path', 'content']
      }
    }
  }

  async execute(input: ToolInput, workspacePath: string): Promise<ToolResult> {
    const filePath = this.resolvePath(String(input['path']), workspacePath)
    const content = String(input['content'])

    // Security: ensure the file is inside the workspace
    const resolvedWorkspace = path.resolve(workspacePath)
    const resolvedFile = path.resolve(filePath)
    if (!resolvedFile.startsWith(resolvedWorkspace + path.sep) && resolvedFile !== resolvedWorkspace) {
      return this.err(`Refusing to write outside workspace: ${filePath}`)
    }

    try {
      fs.mkdirSync(path.dirname(filePath), { recursive: true })
      fs.writeFileSync(filePath, content, 'utf-8')
      const relativePath = path.relative(workspacePath, filePath)
      return this.ok(`Wrote ${content.length} bytes to ${relativePath} (${content.split('\n').length} lines)`)
    } catch (err) {
      return this.err(`Failed to write file: ${String(err)}`)
    }
  }

  private resolvePath(filePath: string, workspacePath: string): string {
    if (path.isAbsolute(filePath)) return filePath
    return path.join(workspacePath, filePath)
  }
}
