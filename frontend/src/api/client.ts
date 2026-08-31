import type { DomainErrorBody } from './types'

/**
 * 统一 API 客户端：所有请求走同源 `/api` 前缀，
 * 非 2xx 响应统一解析为 DomainError 结构并抛 ApiError。
 */
export class ApiError extends Error {
  readonly status: number
  readonly error_code?: string
  readonly stage?: string
  readonly retryable?: boolean
  readonly details?: Record<string, unknown>
  readonly body?: unknown

  constructor(status: number, body: unknown) {
    const parsed = (body ?? {}) as Partial<DomainErrorBody> & {
      detail?: unknown
    }
    const message =
      typeof parsed.message === 'string'
        ? parsed.message
        : typeof parsed.detail === 'string'
          ? parsed.detail
          : `请求失败（HTTP ${status}）`
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.error_code = parsed.error_code
    this.stage = parsed.stage
    this.retryable = parsed.retryable
    this.details = parsed.details
    this.body = body
  }
}

const BASE_URL = '/api'

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, init)
  const text = await res.text()
  let body: unknown
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = undefined
    }
  }
  if (!res.ok) {
    throw new ApiError(res.status, body ?? { detail: text })
  }
  return body as T
}

const jsonHeaders: HeadersInit = { 'Content-Type': 'application/json' }

export const api = {
  get<T>(path: string): Promise<T> {
    return request<T>(path)
  },

  post<T>(path: string, data?: unknown): Promise<T> {
    return request<T>(path, {
      method: 'POST',
      headers: jsonHeaders,
      body: data === undefined ? undefined : JSON.stringify(data),
    })
  },

  put<T>(path: string, data: unknown): Promise<T> {
    return request<T>(path, {
      method: 'PUT',
      headers: jsonHeaders,
      body: JSON.stringify(data),
    })
  },

  del<T>(path: string): Promise<T> {
    return request<T>(path, { method: 'DELETE' })
  },

  postForm<T>(path: string, form: FormData): Promise<T> {
    return request<T>(path, { method: 'POST', body: form })
  },
}