import { BaseTool, ToolDefinition, ToolInput, ToolResult } from './BaseTool'

const MAX_RESPONSE_BYTES = 100_000
const REQUEST_TIMEOUT_MS = 15_000

export class WebFetchTool extends BaseTool {
  get definition(): ToolDefinition {
    return {
      name: 'web_fetch',
      description: 'Fetch content from a URL. Useful for reading documentation, package READMEs, or API references. Returns the page content as plain text.',
      parameters: {
        type: 'object',
        properties: {
          url: {
            type: 'string',
            description: 'The URL to fetch. Must be a valid http or https URL.'
          },
          extract: {
            type: 'string',
            description: 'Optional: What to extract from the page (e.g., "code examples", "API reference"). Not used in fetching but helps remind you what to look for.'
          }
        },
        required: ['url']
      }
    }
  }

  async execute(input: ToolInput, _workspacePath: string): Promise<ToolResult> {
    const url = String(input['url'])

    // Only allow http/https
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      return this.err(`Only http/https URLs are supported. Got: ${url}`)
    }

    try {
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

      let response: Response
      try {
        response = await fetch(url, {
          signal: controller.signal,
          headers: {
            'User-Agent': 'NexusAgent/0.1 (documentation fetcher)',
            'Accept': 'text/html,text/plain,application/json,*/*'
          }
        })
      } finally {
        clearTimeout(timer)
      }

      if (!response.ok) {
        return this.err(`HTTP ${response.status} ${response.statusText}: ${url}`)
      }

      const contentType = response.headers.get('content-type') ?? ''
      const rawBytes = await response.arrayBuffer()
      const bytes = Buffer.from(rawBytes)

      if (bytes.byteLength > MAX_RESPONSE_BYTES) {
        const truncated = bytes.subarray(0, MAX_RESPONSE_BYTES).toString('utf-8')
        return this.ok(
          `URL: ${url}\nContent-Type: ${contentType}\nSize: ${bytes.byteLength} bytes (truncated to 100KB)\n\n${this.stripHtml(truncated)}`
        )
      }

      const text = bytes.toString('utf-8')
      const content = contentType.includes('html') ? this.stripHtml(text) : text

      return this.ok(`URL: ${url}\nContent-Type: ${contentType}\nSize: ${text.length} bytes\n\n${content}`)
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return this.err(`Request timed out after ${REQUEST_TIMEOUT_MS / 1000}s: ${url}`)
      }
      return this.err(`Failed to fetch URL: ${String(err)}`)
    }
  }

  private stripHtml(html: string): string {
    // Basic HTML-to-text stripping:
    // Remove script and style blocks
    let text = html
      .replace(/<script[\s\S]*?<\/script>/gi, '')
      .replace(/<style[\s\S]*?<\/style>/gi, '')
      .replace(/<head[\s\S]*?<\/head>/gi, '')
      .replace(/<!--[\s\S]*?-->/g, '')
      // Convert block elements to newlines
      .replace(/<(br|p|div|h[1-6]|li|tr|blockquote)[^>]*>/gi, '\n')
      // Remove all remaining tags
      .replace(/<[^>]+>/g, '')
      // Decode common HTML entities
      .replace(/&amp;/g, '&')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"')
      .replace(/&#039;/g, "'")
      .replace(/&nbsp;/g, ' ')
      // Collapse excessive whitespace
      .replace(/[ \t]+/g, ' ')
      .replace(/\n{3,}/g, '\n\n')
      .trim()

    return text
  }
}
