import { BaseProvider } from './BaseProvider'
import { AnthropicProvider } from './AnthropicProvider'
import { OpenAIProvider } from './OpenAIProvider'
import { OllamaProvider } from './OllamaProvider'

export class ProviderRegistry {
  private providers = new Map<string, BaseProvider>()

  constructor() {
    this.register(new AnthropicProvider())
    this.register(new OpenAIProvider())
    this.register(new OllamaProvider())
  }

  register(provider: BaseProvider): void {
    this.providers.set(provider.name, provider)
  }

  get(name: string): BaseProvider {
    const provider = this.providers.get(name)
    if (!provider) {
      throw new Error(`Unknown LLM provider: "${name}". Available: ${Array.from(this.providers.keys()).join(', ')}`)
    }
    return provider
  }

  list(): string[] {
    return Array.from(this.providers.keys())
  }
}
