import Badge from './ui/Badge'
import type { OperationDetail, StageProjection } from '../api/types'
import { fmtMs } from '../hooks/useOperation'

const RESOURCE_LABEL: Record<string, string> = {
  LOCAL_DB: '本地数据库',
  LOCAL_FILE: '本地文件',
  LOCAL_CPU: '本地计算',
  LLM: 'LLM',
  EMBEDDING: 'Embedding',
}

function eventTone(type: string): 'neutral' | 'ok' | 'warn' | 'danger' | 'accent' {
  switch (type) {
    case 'COMPLETED':
      return 'ok'
    case 'FAILED':
      return 'danger'
    case 'ROLLED_BACK':
      return 'warn'
    case 'STARTED':
    default:
      return 'neutral'
  }
}

function eventLabel(type: string): string {
  switch (type) {
    case 'STARTED':
      return '开始'
    case 'COMPLETED':
      return '完成'
    case 'FAILED':
      return '失败'
    case 'ROLLED_BACK':
      return '已回滚'
    default:
      return type
  }
}

function StageRow({ ev, recent }: { ev: StageProjection; recent?: { median_ms: number | null; max_ms: number | null; sample_size: number } }) {
  const isStart = ev.event_type === 'STARTED'
  const label = isStart ? ev.stage_name || ev.stage_code : eventLabel(ev.event_type)
  return (
    <li className="tl__row">
      <span className="tl__status">
        <Badge tone={eventTone(ev.event_type)}>{eventLabel(ev.event_type)}</Badge>
      </span>
      <span className="tl__name">{label}</span>
      <span className="tl__resource tag">{RESOURCE_LABEL[ev.resource_type] ?? ev.resource_type}</span>
      <span className="tl__elapsed">
        {isStart ? '' : fmtMs(ev.elapsed_ms)}
      </span>
      {!isStart && recent ? (
        <span className="tl__recent muted">
          近{recent.sample_size}次 中位 {fmtMs(recent.median_ms)} / 最大 {fmtMs(recent.max_ms)}
        </span>
      ) : null}
    </li>
  )
}

/** 单次操作的阶段时间线（顺序 / 状态 / 资源 / 阶段耗时 / 近期对比）。 */
export default function OperationTimeline({ operation }: { operation: OperationDetail }) {
  if (!operation.stages || operation.stages.length === 0) {
    return <p className="muted">暂无阶段事件。</p>
  }
  return (
    <ul className="tl">
      {operation.stages.map((ev, i) => (
        <StageRow key={`${ev.seq}-${i}`} ev={ev} recent={operation.recent_stats?.[ev.stage_code]} />
      ))}
    </ul>
  )
}