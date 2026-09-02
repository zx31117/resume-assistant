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

  post<T>(path: string, data?: unknown, headers?: HeadersInit): Promise<T> {
    return request<T>(path, {
      method: 'POST',
      headers: { ...jsonHeaders, ...(headers ?? {}) },
      body: data === undefined ? undefined : JSON.stringify(data),
    })
  },

  put<T>(path: string, data: unknown, headers?: HeadersInit): Promise<T> {
    return request<T>(path, {
      method: 'PUT',
      headers: { ...jsonHeaders, ...(headers ?? {}) },
      body: JSON.stringify(data),
    })
  },

  del<T>(path: string, headers?: HeadersInit): Promise<T> {
    return request<T>(path, { method: 'DELETE', headers: headers ?? {} })
  },

  postForm<T>(path: string, form: FormData): Promise<T> {
    return request<T>(path, { method: 'POST', body: form })
  },
}

/** 生成合法 UUID（PLAN §3.3：前端发起请求前生成 X-Operation-ID）。 */
export function newOperationId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

export function operationHeaders(operationId?: string, groupId?: string): HeadersInit {
  const h: Record<string, string> = {}
  if (operationId) h['X-Operation-ID'] = operationId
  if (groupId) h['X-Operation-Group-ID'] = groupId
  return h
}