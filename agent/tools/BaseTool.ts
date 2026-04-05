export interface ToolInput {
  [key: string]: unknown
}

export interface ToolResult {
  success: boolean
  output: string
  error?: string
}

export interface ToolDefinition {
  name: string
  description: string
  parameters: {
    type: 'object'
    properties: Record<string, {
      type: string
      description: string
      enum?: string[]
      default?: unknown
    }>
    required: string[]
  }
}

export abstract class BaseTool {
  abstract get definition(): ToolDefinition

  get name(): string {
    return this.definition.name
  }

  abstract execute(input: ToolInput, workspacePath: string): Promise<ToolResult>

  protected ok(output: string): ToolResult {
    return { success: true, output }
  }

  protected err(error: string): ToolResult {
    return { success: false, output: '', error }
  }
}
