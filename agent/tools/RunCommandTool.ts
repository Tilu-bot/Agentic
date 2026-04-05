import { BaseTool, ToolDefinition, ToolInput, ToolResult } from './BaseTool'
import * as child_process from 'child_process'
import * as path from 'path'

const MAX_OUTPUT_BYTES = 50_000
const DEFAULT_TIMEOUT_MS = 30_000

// Commands that are explicitly blocked for safety
const BLOCKED_COMMANDS = new Set([
  'rm -rf /', 'rm -rf /*', 'mkfs', 'dd',
  ':(){:|:&};:', 'format', 'fdisk', 'shutdown', 'reboot', 'halt',
  'deltree', 'del /f /s /q c:'
])

export class RunCommandTool extends BaseTool {
  get definition(): ToolDefinition {
    return {
      name: 'run_command',
      description: 'Run a shell command in the workspace directory. Use this to run tests, build code, install packages, and similar tasks. Output is capped at 50KB.',
      parameters: {
        type: 'object',
        properties: {
          command: {
            type: 'string',
            description: 'The shell command to run. Runs in /bin/bash (or cmd.exe on Windows).'
          },
          timeout: {
            type: 'number',
            description: 'Timeout in seconds. Default is 30. Maximum is 120.'
          },
          cwd: {
            type: 'string',
            description: 'Working directory relative to workspace root. Default is workspace root.'
          }
        },
        required: ['command']
      }
    }
  }

  async execute(input: ToolInput, workspacePath: string): Promise<ToolResult> {
    const command = String(input['command']).trim()
    const timeoutSeconds = Math.min(Number(input['timeout'] ?? 30), 120)
    const cwdRel = input['cwd'] ? String(input['cwd']) : '.'
    const cwd = path.isAbsolute(cwdRel) ? cwdRel : path.join(workspacePath, cwdRel)

    // Reject obviously dangerous commands
    for (const blocked of BLOCKED_COMMANDS) {
      if (command.toLowerCase().includes(blocked.toLowerCase())) {
        return this.err(`Command blocked for safety: ${command}`)
      }
    }

    return new Promise((resolve) => {
      const startTime = Date.now()
      const shell = process.platform === 'win32' ? 'cmd.exe' : '/bin/bash'
      const shellArgs = process.platform === 'win32' ? ['/c', command] : ['-c', command]

      const proc = child_process.spawn(shell, shellArgs, {
        cwd,
        env: { ...process.env },
        timeout: timeoutSeconds * 1000
      })

      const stdoutChunks: Buffer[] = []
      const stderrChunks: Buffer[] = []
      let totalBytes = 0

      proc.stdout.on('data', (chunk: Buffer) => {
        if (totalBytes < MAX_OUTPUT_BYTES) {
          stdoutChunks.push(chunk)
          totalBytes += chunk.length
        }
      })

      proc.stderr.on('data', (chunk: Buffer) => {
        if (totalBytes < MAX_OUTPUT_BYTES) {
          stderrChunks.push(chunk)
          totalBytes += chunk.length
        }
      })

      proc.on('error', (err) => {
        resolve(this.err(`Failed to start command: ${err.message}`))
      })

      proc.on('close', (code, signal) => {
        const elapsed = Date.now() - startTime
        const stdout = Buffer.concat(stdoutChunks).toString('utf-8')
        const stderr = Buffer.concat(stderrChunks).toString('utf-8')

        let output = ''
        if (stdout) output += stdout
        if (stderr) output += (output ? '\nSTDERR:\n' : '') + stderr
        if (totalBytes >= MAX_OUTPUT_BYTES) output += '\n[...output truncated at 50KB]'
        if (!output) output = '(no output)'

        const header = `$ ${command}\n[Exit: ${signal ? `signal ${signal}` : String(code)} | ${elapsed}ms]\n\n`
        resolve({
          success: code === 0,
          output: header + output,
          error: code !== 0 ? `Command exited with code ${code}` : undefined
        })
      })
    })
  }
}
