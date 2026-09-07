import { useCallback, useRef } from 'react'
import type { OperationDetail } from '../api/types'

/**
 * V2.1.0 T12-R4：4 阶段流程列表（生成处理 / 后续可复用上传解析视图）。
 *
 * - 阶段项使用 radio 语义（role="radiogroup" / role="radio" / aria-checked），
 *   roving tabindex + 方向键 + Home/End 切换，符合 WAI-ARIA Radio Group 模式；
 * - 阶段状态由真实 operation.stages 计算（STARTED/COMPLETED/FAILED/ROLLED_BACK），
 *   只允许「已开始或已完成」的阶段可选，未开始阶段 disabled 且无占位明细；
 * - 「当前查看」≠「当前运行」必须可区分（aria-checked vs aria-current）。
 */

export interface StageFlowPhase {
  key: string
  label: string
  detail: string
  /** 触发本阶段亮亮的真实 stage_code 集合（来自 backend OperationProjection.stage_code）。 */
  codes: string[]
}

export type PhaseStatus = 'pending' | 'active' | 'done' | 'failed'

/** 单个阶段的累计耗时（毫秒）：来自其下所有非 STARTED 事件的 elapsed_ms 求和。 */
export function phaseElapsedMs(op: OperationDetail | null, codes: string[]): number | null {
  if (!op) return null
  const events = op.stages ?? []
  let hasAny = false
  let total = 0
  for (const ev of events) {
    if (!codes.includes(ev.stage_code)) continue
    if (ev.event_type === 'STARTED') continue
    hasAny = true
    total += typeof ev.elapsed_ms === 'number' ? ev.elapsed_ms : 0
  }
  return hasAny ? total : null
}

/** 根据 operation 真实事件计算该阶段状态（不提前点亮，不虚构）。 */
export function calcPhaseStatus(op: OperationDetail | null, codes: string[]): PhaseStatus {
  if (!op) return 'pending'
  const events = op.stages ?? []
  let sawStarted = false
  let failed = false
  for (const ev of events) {
    if (!codes.includes(ev.stage_code)) continue
    if (ev.event_type === 'STARTED') sawStarted = true
    else if (ev.event_type === 'FAILED' || ev.event_type === 'ROLLED_BACK') failed = true
  }
  const allCompleted = codes.every((c) => events.some((e) => e.stage_code === c && e.event_type === 'COMPLETED'))
  if (allCompleted) return 'done'
  if (failed) return 'failed'
  if (sawStarted || (op.stage_code && codes.includes(op.stage_code))) return 'active'
  return 'pending'
}

export interface StageFlowListProps {
  phases: StageFlowPhase[]
  op: OperationDetail | null
  /** 当前用户查看的阶段下标。 */
  selectedIdx: number
  onSelect: (idx: number) => void
}

const STATUS_TAIL: Record<PhaseStatus, string> = {
  done: '已完成',
  active: '进行中',
  pending: '等待',
  failed: '失败',
}

function fmtElapsed(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export default function StageFlowList({ phases, op, selectedIdx, onSelect }: StageFlowListProps) {
  const listRef = useRef<HTMLDivElement>(null)

  const statuses: PhaseStatus[] = phases.map((p) => calcPhaseStatus(op, p.codes))
  // 「当前运行」= 第一个 active 阶段；若无 active 则为第一个 failed（仅显示）
  const currentRunningIdx = (() => {
    const i = statuses.findIndex((s) => s === 'active')
    if (i >= 0) return i
    const f = statuses.findIndex((s) => s === 'failed')
    return f >= 0 ? f : -1
  })()

  const isSelectable = (i: number) => {
    const s = statuses[i]
    return s === 'active' || s === 'done' || s === 'failed'
  }

  const selectableIndexes = phases.map((_, i) => i).filter(isSelectable)

  const focusItem = useCallback((i: number) => {
    const root = listRef.current
    if (!root) return
    const el = root.querySelector<HTMLButtonElement>(`[data-stage-idx="${i}"]`)
    el?.focus()
  }, [])

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (selectableIndexes.length === 0) return
      const curPos = selectableIndexes.indexOf(selectedIdx)
      let next: number | null = null
      if (e.key === 'ArrowDown' || e.key === 'ArrowRight') {
        e.preventDefault()
        next = curPos < 0 ? selectableIndexes[0]! : selectableIndexes[(curPos + 1) % selectableIndexes.length]!
      } else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') {
        e.preventDefault()
        next =
          curPos < 0
            ? selectableIndexes[selectableIndexes.length - 1]!
            : selectableIndexes[(curPos - 1 + selectableIndexes.length) % selectableIndexes.length]!
      } else if (e.key === 'Home') {
        e.preventDefault()
        next = selectableIndexes[0]!
      } else if (e.key === 'End') {
        e.preventDefault()
        next = selectableIndexes[selectableIndexes.length - 1]!
      } else {
        return
      }
      onSelect(next)
      focusItem(next)
    },
    [selectableIndexes, selectedIdx, onSelect, focusItem],
  )

  return (
    <div
      ref={listRef}
      role="radiogroup"
      aria-label="简历生成阶段"
      className="process-stages"
      onKeyDown={onKeyDown}
    >
      {phases.map((p, i) => {
        const st = statuses[i]!
        const selectable = isSelectable(i)
        const checked = selectedIdx === i
        const current = currentRunningIdx === i
        const elapsed = phaseElapsedMs(op, p.codes)
        const indicatorContent =
          st === 'done' ? '✓' : st === 'failed' ? '!' : current ? i + 1 : i + 1
        return (
          <button
            key={p.key}
            type="button"
            role="radio"
            aria-checked={checked}
            aria-current={current ? 'true' : undefined}
            aria-label={`${i + 1}. ${p.label}（${STATUS_TAIL[st]}）`}
            data-stage-idx={i}
            data-stage-key={p.key}
            data-stage-status={st}
            tabIndex={checked ? 0 : -1}
            disabled={!selectable}
            onClick={() => selectable && onSelect(i)}
            className={
              `process-stage process-stage--${st}` +
              (checked ? ' process-stage--selected' : '') +
              (current ? ' process-stage--current' : '') +
              (selectable ? '' : ' process-stage--disabled')
            }
          >
            <span className="process-stage__indicator" aria-hidden="true">
              {indicatorContent}
            </span>
            <span className="process-stage__body">
              <span className="process-stage__label">{p.label}</span>
              <span className="process-stage__detail">{p.detail}</span>
            </span>
            <span
              className={
                'process-stage__elapsed' +
                (st === 'active' ? ' process-stage__elapsed--active' : '') +
                (st === 'failed' ? ' process-stage__elapsed--failed' : '')
              }
            >
              {st === 'pending' ? '—' : elapsed != null ? fmtElapsed(elapsed) : '—'}
            </span>
          </button>
        )
      })}
    </div>
  )
}
