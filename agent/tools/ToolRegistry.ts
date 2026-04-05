import { BaseTool, ToolDefinition } from './BaseTool'
import { ReadFileTool } from './ReadFileTool'
import { WriteFileTool } from './WriteFileTool'
import { ListDirectoryTool } from './ListDirectoryTool'
import { RunCommandTool } from './RunCommandTool'
import { SearchFilesTool } from './SearchFilesTool'
import { ApplyDiffTool } from './ApplyDiffTool'
import { WebFetchTool } from './WebFetchTool'

export class ToolRegistry {
  private tools = new Map<string, BaseTool>()

  constructor() {
    this.register(new ReadFileTool())
    this.register(new WriteFileTool())
    this.register(new ListDirectoryTool())
    this.register(new RunCommandTool())
    this.register(new SearchFilesTool())
    this.register(new ApplyDiffTool())
    this.register(new WebFetchTool())
  }

  register(tool: BaseTool): void {
    this.tools.set(tool.name, tool)
  }

  get(name: string): BaseTool | undefined {
    return this.tools.get(name)
  }

  getDefinitions(): ToolDefinition[] {
    return Array.from(this.tools.values()).map((t) => t.definition)
  }

  list(): string[] {
    return Array.from(this.tools.keys())
  }
}
