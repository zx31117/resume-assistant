import { useEffect, useState } from 'react'
import { systemApi } from '../api/endpoints'
import type { OperationDetail } from '../api/types'

const TERMINAL = new Set(['SUCCEEDED', 'FAILED', 'TIMED_OUT', 'INTERRUPTED'])

/**
 * 轮询单次操作的实时阶段（PLAN §3.4 短轮询，约 1 秒）。
 *
 * - operationId 为空或非活动时不轮询；
 * - 到终态（SUCCEEDED/FAILED/TIMED_OUT/INTERRUPTED）停止；
 * - 页面不可见时降频（3 秒），可见时恢复 1 秒。
 */
export function useOperation(operationId: string | null, active: boolean) {
  const [operation, setOperation] = useState<OperationDetail | null>(null)

  useEffect(() => {
    if (!operationId || !active) {
      setOperation(null)
      return
    }
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined

    async function poll() {
      if (cancelled) return
      try {
        const res = await systemApi.getOperation(operationId!)
        if (cancelled) return
        setOperation(res.operation)
        if (TERMINAL.has(res.operation.status)) return
      } catch {
        // 404（已被轮转/清理）或瞬断：保留上一快照，稍后重试而非静默停止
      }
      const interval = document.visibilityState === 'hidden' ? 3000 : 1000
      timer = setTimeout(poll, interval)
    }

    poll()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [operationId, active])

  return operation
}

/** 操作状态 → 徽标色调。 */
export function statusTone(status: string): 'neutral' | 'ok' | 'warn' | 'danger' | 'accent' {
  switch (status) {
    case 'SUCCEEDED':
      return 'ok'
    case 'FAILED':
    case 'INTERRUPTED':
      return 'danger'
    case 'TIMED_OUT':
      return 'warn'
    case 'RUNNING':
      return 'accent'
    default:
      return 'neutral'
  }
}

/** 操作状态中文名。 */
export function statusLabel(status: string): string {
  switch (status) {
    case 'RUNNING':
      return '执行中'
    case 'SUCCEEDED':
      return '成功'
    case 'FAILED':
      return '失败'
    case 'TIMED_OUT':
      return '超时'
    case 'INTERRUPTED':
      return '已中断'
    default:
      return status
  }
}

/** 毫秒 → 人类可读耗时。 */
export function fmtMs(ms: number | null | undefined): string {
  if (ms == null) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

/** 稳定时间戳（后端返回 ISO8601 UTC）的可读化。 */
export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleTimeString()
}