import type { StreamEvent } from './types'

const headers = { 'Content-Type': 'application/json', 'X-Agent-Client': 'web' }

export async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, body === undefined ? {} : { method: 'POST', headers, body: JSON.stringify(body) })
  const data = await response.json()
  if (!response.ok) throw new Error(data.error || '请求失败，请重试。')
  return data as T
}

export async function stream(path: string, body: unknown, receive: (event: StreamEvent) => void) {
  const response = await fetch(path, { method: 'POST', headers, body: JSON.stringify(body) })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.error || '请求失败。')
  }
  if (!response.body) throw new Error('浏览器不支持流式响应。')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let complete = false
  try {
    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n')
      let boundary: number
      // 网络分片不等于事件边界；保留半个 UTF-8 字符和半个事件，直到完整再解析。
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        const event = frame.split('\n').find(line => line.startsWith('event:'))?.slice(6).trim()
        const data = frame.split('\n').filter(line => line.startsWith('data:')).map(line => line.slice(5).trim()).join('\n')
        if (event && data) {
          receive({ event, data: JSON.parse(data) })
          if (event === 'done') complete = true
        }
      }
      if (done) break
    }
    if (!complete) throw new Error('连接已中断，回复可能不完整。请恢复页面状态后重试。')
  } finally {
    reader.releaseLock()
  }
}
