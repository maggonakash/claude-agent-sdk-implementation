import { AgentEvent } from '../types';

export async function* parseSSEStream(response: Response): AsyncGenerator<AgentEvent> {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() ?? '';

      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith('data: ')) continue;
        try {
          const json = line.slice(6).trim();
          if (json) yield JSON.parse(json) as AgentEvent;
        } catch {
          // Skip malformed events
        }
      }
    }

    // Handle any remaining buffer
    if (buffer.trim().startsWith('data: ')) {
      try {
        const json = buffer.trim().slice(6).trim();
        if (json) yield JSON.parse(json) as AgentEvent;
      } catch {
        // ignore
      }
    }
  } finally {
    reader.releaseLock();
  }
}
