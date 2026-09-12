/**
 * V2.1.0 全局应用状态骨架（T2-c）。
 *
 * 只承载跨页面的最小共享状态，避免在 T3-T7 页面重做前过度设计：
 * 1. runtime：应用级 readiness（首启拉一次 system.status + 手动刷新）；
 * 2. notices：统一通知通道（info/ok/warn/error）——先有状态，呈现形式
 *    （toast 等）随 T3 壳层落地，但状态不与 UI 耦合。
 *
 * 错误边界语义：refreshRuntime 失败会暴露 error（fail closed），不会把
 * 页面降级为假"就绪"。
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useServices } from '../services'
import type { SystemStatus } from '../api/types'

export type NoticeTone = 'info' | 'ok' | 'warn' | 'error'

export interface AppNotice {
  id: number
  tone: NoticeTone
  text: string
}

export interface RuntimeState {
  /** true=迁移与索引就绪；false=明确未就绪；null=尚未取得真实状态 */
  ready: boolean | null
  loading: boolean
  status: SystemStatus | null
  error: string | null
}

interface AppStateValue {
  runtime: RuntimeState
  refreshRuntime(): Promise<void>
  notices: AppNotice[]
  notify(tone: NoticeTone, text: string): void
  dismissNotice(id: number): void
}

const AppStateContext = createContext<AppStateValue | null>(null)

export function AppStateProvider({ children }: { children: ReactNode }) {
  const services = useServices()
  const [runtime, setRuntime] = useState<RuntimeState>({
    ready: null,
    loading: false,
    status: null,
    error: null,
  })
  const [notices, setNotices] = useState<AppNotice[]>([])
  const nextNoticeId = useRef(1)

  const refreshRuntime = useCallback(async () => {
    setRuntime((s) => ({ ...s, loading: true, error: null }))
    try {
      const status = await services.system.status()
      setRuntime({ ready: status.ready, loading: false, status, error: null })
    } catch (e) {
      setRuntime((s) => ({
        ...s,
        loading: false,
        ready: false,
        error: e instanceof Error ? e.message : String(e),
      }))
    }
  }, [services])

  useEffect(() => {
    void refreshRuntime()
  }, [refreshRuntime])

  const notify = useCallback((tone: NoticeTone, text: string) => {
    const id = nextNoticeId.current++
    setNotices((n) => [...n, { id, tone, text }])
  }, [])

  const dismissNotice = useCallback((id: number) => {
    setNotices((n) => n.filter((item) => item.id !== id))
  }, [])

  const value = useMemo<AppStateValue>(
    () => ({ runtime, refreshRuntime, notices, notify, dismissNotice }),
    [runtime, refreshRuntime, notices, notify, dismissNotice],
  )

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>
}

export function useAppState(): AppStateValue {
  const state = useContext(AppStateContext)
  if (!state) {
    throw new Error('AppStateProvider 未包裹应用：请先在根部挂载 <AppStateProvider>。')
  }
  return state
}
