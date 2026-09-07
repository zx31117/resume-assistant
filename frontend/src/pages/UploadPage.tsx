import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import { Field, Select, TextArea, TextInput } from '../components/ui/Field'
import { ApiError } from '../api/client'
import { experienceApi, resumeApi } from '../api/endpoints'
import type { ExtractExperienceItem, ExperienceItem } from '../api/types'

/**
 * V2.1.0 T12-R2：上传现有简历 · 解析视图（路由 /upload）。
 *
 * 真实链路（无中间流事件源）：
 *   选/拖入 PDF → POST /api/resume/upload（文件→文本） → POST /api/experience/extract
 *   （文本→带 provenance 的 experiences） → D-038 分流（direct 逐条 create；inferred 待确认）。
 *
 * 诚实映射（左侧 4 阶段 radio + 右侧 ai-stream 单选阶段输出）：
 *   ① 读取文件  —— File 对象本地事实（文件名 / 大小 / 类型 / 修改时间）。
 *   ② 本机解析  —— POST /api/resume/upload 真实响应（text 长度 / 首行摘要 或 真实错误）。
 *   ③ 结构化提取 —— POST /api/experience/extract 真实响应（共 N 条 / 按 type / 按 classification 计数）。
 *   ④ 分类整理  —— provenance 分流（direct 自动 create；inferred 进需确认）真实结果统计。
 *
 * - 左侧阶段项 = radiogroup；当前活动 / 当前查看 解耦，自动跟随活动阶段，
 *   但用户可点击「已开始 / 已完成」阶段回看；未开始阶段不可选，无占位明细；
 * - 右侧只显示当前选中阶段的真实结果事实；不得把多阶段输出同时纵向铺开；
 * - 失败阶段右侧展示真实错误（不暴露原始堆栈），提供可理解原因 + 重试；
 * - D-038 分流：direct 自动落库进「我的经历」，inferred / 自动保存失败项 进需确认核对原文后保存；
 * - 不引入假数据 / 假能力，不展示 Embedding / 内部迁移 / 原始资源类型 / 私有思维链。
 */

const MAX_TEXT_SUMMARY_CHARS = 80
const MAX_BYTES_DEFAULT = 8 * 1024 * 1024

const EXPERIENCE_TYPES: { value: string; label: string }[] = [
  { value: 'work', label: '工作' },
  { value: 'project', label: '项目' },
  { value: 'education', label: '教育' },
]

type PhaseStatus = 'pending' | 'active' | 'done' | 'failed'

interface PhaseOutput {
  /** 真实可观察的结果事实，按阶段分别保留。 */
  kind: 'read' | 'parse' | 'extract' | 'classify' | 'error'
  payload: unknown
}

interface UploadPhase {
  key: 'read' | 'parse' | 'extract' | 'classify'
  label: string
  detail: string
  status: PhaseStatus
  /** 阶段起始本地毫秒时间（仅用于真实耗时；不外推）。 */
  startedAt: number | null
  endedAt: number | null
  /** 真实可观察的输出。 */
  output: PhaseOutput | null
}

interface ClassifyOk { directSaved: number; directFailed: number; inferred: number; total: number }

const PHASE_LABEL: Record<UploadPhase['key'], string> = {
  read: '读取文件',
  parse: '本机解析',
  extract: '结构化提取',
  classify: '分类整理',
}

const PHASE_DETAIL: Record<UploadPhase['key'], string> = {
  read: '记录所选 PDF 的文件名 / 大小 / 类型等本地事实',
  parse: '调用 /api/resume/upload，把 PDF 转成可检索文本',
  extract: '调用 /api/experience/extract，从文本中提取候选经历',
  classify: '按 provenance 分流，direct 自动入库，inferred 需确认',
}

function emptyPhases(): UploadPhase[] {
  return (
    ['read', 'parse', 'extract', 'classify'] as UploadPhase['key'][]
  ).map((k) => ({
    key: k,
    label: PHASE_LABEL[k],
    detail: PHASE_DETAIL[k],
    status: 'pending',
    startedAt: null,
    endedAt: null,
    output: null,
  }))
}

function setPhase(
  phases: UploadPhase[],
  key: UploadPhase['key'],
  patch: Partial<UploadPhase>,
): UploadPhase[] {
  return phases.map((p) => (p.key === key ? { ...p, ...patch } : p))
}

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(2)} MB`
}

function fmtElapsed(ms: number | null): string {
  if (ms == null) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function typeLabel(t: string): string {
  return EXPERIENCE_TYPES.find((x) => x.value === t)?.label ?? (t || '未分类')
}

function firstLine(text: string, max = MAX_TEXT_SUMMARY_CHARS): string {
  const t = text.replace(/\s+/g, ' ').trim()
  if (t.length === 0) return '（空）'
  return t.length > max ? `${t.slice(0, max)}…` : t
}

/** V2.1.0 D-038：把「提取响应条目（含 provenance）」显式白名单为写库请求体，避免把证据字段透传后端。 */
function toCreatePayload(item: ExtractExperienceItem): ExperienceItem {
  return {
    type: item.type,
    title: item.title,
    company: item.company,
    time: item.time,
    role: item.role,
    description: item.description,
    skills: item.skills ?? [],
    achievements: item.achievements ?? [],
    raw_text: item.raw_text ?? '',
  }
}

function splitSkills(v: string): string[] {
  return v
    .split(/[,，\n]/)
    .map((s) => s.trim())
    .filter(Boolean)
}

function splitAchievements(v: string): string[] {
  return v
    .split(/\n/)
    .map((s) => s.trim())
    .filter(Boolean)
}

interface LocationState { file?: File }

/** 上传视图顶部信息条（视觉对齐原型 .app-topbar） */
const topbarStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 'var(--s3)',
  padding: 'var(--s2) var(--s4)',
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--r-md)',
  boxShadow: 'var(--shadow-sm)',
  fontSize: 13,
  color: 'var(--ink-soft)',
  flexWrap: 'wrap',
}

/** 「AI 解析过程」阶段列表 radio 子组件 —— 复用 process-stage CSS */
function UploadPhaseList({
  phases,
  selectedIdx,
  currentRunningIdx,
  onSelect,
}: {
  phases: UploadPhase[]
  selectedIdx: number
  currentRunningIdx: number
  onSelect: (i: number) => void
}) {
  const listRef = useRef<HTMLDivElement>(null)
  const isSelectable = (i: number) => {
    const s = phases[i]?.status
    return s === 'active' || s === 'done' || s === 'failed'
  }
  const selectableIndexes = phases.map((_, i) => i).filter(isSelectable)
  const focusItem = (i: number) => {
    const el = listRef.current?.querySelector<HTMLButtonElement>(`[data-stage-idx="${i}"]`)
    el?.focus()
  }
  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
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
  }
  return (
    <div
      ref={listRef}
      role="radiogroup"
      aria-label="简历解析阶段"
      className="process-stages"
      onKeyDown={onKeyDown}
    >
      {phases.map((p, i) => {
        const selectable = isSelectable(i)
        const checked = selectedIdx === i
        const current = currentRunningIdx === i
        const elapsed =
          p.startedAt != null && p.endedAt != null ? Math.max(0, p.endedAt - p.startedAt) : null
        const indicatorContent =
          p.status === 'done' ? '✓' : p.status === 'failed' ? '!' : current ? i + 1 : i + 1
        const statusTail =
          p.status === 'done' ? '已完成' : p.status === 'active' ? '进行中' : p.status === 'failed' ? '失败' : '等待'
        return (
          <button
            key={p.key}
            type="button"
            role="radio"
            aria-checked={checked}
            aria-current={current ? 'true' : undefined}
            aria-label={`${i + 1}. ${p.label}（${statusTail}）`}
            data-stage-idx={i}
            data-stage-key={p.key}
            data-stage-status={p.status}
            tabIndex={checked ? 0 : -1}
            disabled={!selectable}
            onClick={() => selectable && onSelect(i)}
            className={
              `process-stage process-stage--${p.status}` +
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
                (p.status === 'active' ? ' process-stage__elapsed--active' : '') +
                (p.status === 'failed' ? ' process-stage__elapsed--failed' : '')
              }
            >
              {p.status === 'pending' ? '—' : fmtElapsed(elapsed)}
            </span>
          </button>
        )
      })}
    </div>
  )
}

/** 右侧 ai-stream：只渲染当前选中阶段的真实结果事实。 */
function PhaseOutput({
  phase,
  phaseIdx,
  onRetry,
  parsing,
}: {
  phase: UploadPhase
  phaseIdx: number
  onRetry: (fromKey: UploadPhase['key']) => void
  parsing: boolean
}) {
  const tag =
    phase.status === 'failed'
      ? '阶段失败'
      : phase.status === 'active'
        ? '正在执行'
        : phase.status === 'done'
          ? '阶段完成'
          : '阶段明细'
  const sub =
    phase.startedAt != null && phase.endedAt != null
      ? fmtElapsed(Math.max(0, phase.endedAt - phase.startedAt))
      : phase.startedAt != null
        ? fmtElapsed(Date.now() - phase.startedAt)
        : '—'

  return (
    <div className="ai-stream" aria-live="polite">
      <div className="ai-stream__head">
        <span className="ai-stream__tag">{tag}</span>
        <span className="ai-stream__title">
          {phaseIdx + 1}. {phase.label}
        </span>
        <span className="ai-stream__sub">{sub}</span>
      </div>
      <div className="ai-stream__list" role="log">
        <PhaseOutputBody phase={phase} onRetry={onRetry} parsing={parsing} />
      </div>
    </div>
  )
}

function PhaseOutputBody({
  phase,
  onRetry,
  parsing,
}: {
  phase: UploadPhase
  onRetry: (fromKey: UploadPhase['key']) => void
  parsing: boolean
}) {
  if (phase.status === 'pending') {
    return (
      <div className="ai-stream__empty">
        该阶段尚未开始；等待上一阶段完成后会自动推进。点击左侧已开始 / 已完成阶段可回看其结果事实。
      </div>
    )
  }
  if (phase.status === 'active' && !phase.output) {
    return <div className="ai-stream__empty">阶段进行中…完成会写入真实结果事实。</div>
  }
  if (phase.status === 'failed' && phase.output?.kind === 'error') {
    const err = phase.output.payload as { message: string; code?: string; stage?: string; retryable?: boolean }
    return (
      <div className="ai-stream__line ai-stream__line--failed">
        <div className="ai-stream__line-main">
          <Badge tone="danger">失败</Badge>
          <span className="ai-stream__line-name">{phase.label}</span>
        </div>
        <div className="ai-stream__line-msg">{err.message || '阶段失败'}</div>
        <div className="ai-stream__line-meta">
          {err.code ? <span>错误码 {err.code}</span> : null}
          {err.stage ? <span>· 阶段 {err.stage}</span> : null}
          {err.retryable ? <span>· 可重试</span> : null}
        </div>
        <div style={{ marginTop: 'var(--s2)' }}>
          <Button size="sm" variant="primary" onClick={() => onRetry(phase.key)} disabled={parsing}>
            重试本阶段
          </Button>
        </div>
      </div>
    )
  }
  if (phase.output?.kind === 'read') {
    const r = phase.output.payload as { name: string; size: number; type: string; lastModified: number }
    return (
      <div className="ai-stream__line ai-stream__line--started">
        <div className="ai-stream__line-main">
          <Badge tone="ok">已就绪</Badge>
          <span className="ai-stream__line-name">本地 PDF 事实</span>
        </div>
        <div className="ai-stream__line-msg">
          文件名：{r.name || '（未命名）'}
          <br />
          大小：{fmtBytes(r.size)}
          <br />
          类型：{r.type || 'application/pdf'}
          {r.lastModified ? (
            <>
              <br />
              本地修改：{new Date(r.lastModified).toLocaleString()}
            </>
          ) : null}
        </div>
        <div className="ai-stream__line-meta">
          本地读取仅记录事实，不会上传原始文件。
        </div>
      </div>
    )
  }
  if (phase.output?.kind === 'parse') {
    const r = phase.output.payload as { length: number; summary: string }
    return (
      <div className="ai-stream__line ai-stream__line--started">
        <div className="ai-stream__line-main">
          <Badge tone="ok">解析完成</Badge>
          <span className="ai-stream__line-name">本机解析 · 文本</span>
        </div>
        <div className="ai-stream__line-msg">
          解析完成：文本约 {r.length} 字
          <br />
          首行摘要：{r.summary}
        </div>
        <div className="ai-stream__line-meta">
          真实响应字段；后续提取步骤将基于这份文本。
        </div>
      </div>
    )
  }
  if (phase.output?.kind === 'extract') {
    const r = phase.output.payload as {
      total: number
      byType: Record<string, number>
      byClass: { direct: number; inferred: number }
    }
    const byTypeEntries = Object.entries(r.byType).filter(([, n]) => n > 0)
    return (
      <>
        <div className="ai-stream__line ai-stream__line--started">
          <div className="ai-stream__line-main">
            <Badge tone="ok">提取完成</Badge>
            <span className="ai-stream__line-name">共 {r.total} 条候选经历</span>
          </div>
          <div className="ai-stream__line-msg">
            {byTypeEntries.length > 0 ? (
              byTypeEntries.map(([t, n]) => (
                <span key={t}>
                  · {typeLabel(t)}：{n}
                  <br />
                </span>
              ))
            ) : (
              '未提取到任何经历。'
            )}
            · direct：{r.byClass.direct}（可自动入库）
            <br />
            · inferred：{r.byClass.inferred}（需你确认）
          </div>
          <div className="ai-stream__line-meta">来源：真实 /api/experience/extract 响应。</div>
        </div>
      </>
    )
  }
  if (phase.output?.kind === 'classify') {
    const r = phase.output.payload as ClassifyOk
    return (
      <div className="ai-stream__line ai-stream__line--started">
        <div className="ai-stream__line-main">
          <Badge tone="ok">分流完成</Badge>
          <span className="ai-stream__line-name">分类整理</span>
        </div>
        <div className="ai-stream__line-msg">
          · direct：{r.directSaved + r.directFailed}（已自动入库 {r.directSaved}
          {r.directFailed > 0 ? ` · 失败 ${r.directFailed}` : ''}）
          <br />
          · inferred：{r.inferred}（需你逐项确认后保存）
        </div>
        <div className="ai-stream__line-meta">
          失败的自动保存项已合并到下方「需确认条目」中，可核对原文后重新保存。
        </div>
      </div>
    )
  }
  return <div className="ai-stream__empty">暂无输出。</div>
}

/** 失败阶段横向重试面板（与 process-side 上下保持一致）。 */
function FailurePanel({
  phase,
  phaseIdx,
  onRetry,
  onRestart,
  onChangeFile,
  onGoProfile,
}: {
  phase: UploadPhase | null
  phaseIdx: number
  onRetry: () => void
  onRestart: () => void
  onChangeFile: () => void
  onGoProfile: () => void
}) {
  let reason = '发生未知错误'
  let diag: string | null = null
  if (phase?.output?.kind === 'error') {
    const err = phase.output.payload as { message: string; code?: string; stage?: string; retryable?: boolean }
    reason = err.message || reason
    if (err.code || err.stage) diag = `后端返回：stage=${err.stage ?? '—'} · code=${err.code ?? '—'}`
  }
  return (
    <div className="process-error" role="alert">
      <div className="process-error__head">
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          aria-hidden="true"
        >
          <path d="M12 9v4M12 17h.01" />
          <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
        </svg>
        解析未完成
      </div>
      {phase ? (
        <div className="process-error__phase">
          失败阶段：{phaseIdx + 1}. {phase.label}
        </div>
      ) : null}
      <div className="process-error__reason">{reason}</div>
      {diag ? <div className="process-error__diag">{diag}</div> : null}
      <div className="process-error__actions">
        <Button variant="primary" size="sm" onClick={onRetry}>
          重试当前阶段
        </Button>
        <Button variant="secondary" size="sm" onClick={onRestart}>
          重新选择文件
        </Button>
        <Button variant="ghost" size="sm" onClick={onGoProfile}>
          返回我的经历
        </Button>
      </div>
      <div className="process-error__note">错误来自真实后端响应；普通用户不展示原始堆栈。</div>
      <div style={{ display: 'none' }} aria-hidden="true">
        <button type="button" onClick={onChangeFile}>
          备用：换文件
        </button>
      </div>
    </div>
  )
}

export default function UploadPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const incoming = (location.state as LocationState | null)?.file ?? null

  // 阶段列表 + 选中 + 视图模式
  const [phases, setPhases] = useState<UploadPhase[]>(() => emptyPhases())
  const [mode, setMode] = useState<'idle' | 'parsing' | 'review'>(
    incoming ? 'parsing' : 'idle',
  )
  const [file, setFile] = useState<File | null>(incoming)
  const [selectedPhaseIdx, setSelectedPhaseIdx] = useState(0)
  const [globalError, setGlobalError] = useState<{ message: string; code?: string; stage?: string; retryable?: boolean } | null>(null)
  const runSeq = useRef(0)

  // review 状态
  const [reviewItems, setReviewItems] = useState<ExtractExperienceItem[]>([])
  const [reviewResults, setReviewResults] = useState<{ idx: number; ok: boolean; msg: string }[]>([])
  const [reviewSaving, setReviewSaving] = useState(false)
  const [reviewSummary, setReviewSummary] = useState<string | null>(null)
  const [doneOk, setDoneOk] = useState(false)

  // idle 视图：拖拽支持
  const idleInputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)

  const currentRunningIdx = useMemo(
    () => phases.findIndex((p) => p.status === 'active'),
    [phases],
  )
  const failedPhaseIdx = useMemo(
    () => phases.findIndex((p) => p.status === 'failed'),
    [phases],
  )
  const safePhaseIdx =
    selectedPhaseIdx >= 0 && selectedPhaseIdx < phases.length ? selectedPhaseIdx : 0
  const viewPhase = phases[safePhaseIdx]!
  const totalElapsedMs = useMemo(() => {
    const starts = phases.map((p) => p.startedAt).filter((v): v is number => v != null)
    const ends = phases.map((p) => p.endedAt).filter((v): v is number => v != null)
    if (starts.length === 0) return null
    const minStart = Math.min(...starts)
    const maxEnd = ends.length > 0 ? Math.max(...ends) : Date.now()
    return Math.max(0, maxEnd - minStart)
  }, [phases])

  // 自动跟随「当前活动」阶段：活动阶段切换 → 选中跟随；都结束后默认看最后一个有内容的阶段。
  useEffect(() => {
    if (mode !== 'parsing') return
    if (currentRunningIdx >= 0) {
      setSelectedPhaseIdx(currentRunningIdx)
      return
    }
    // 没有 active 阶段 → 默认显示最后一个 done/failed 阶段
    let target = -1
    for (let i = phases.length - 1; i >= 0; i--) {
      if (phases[i]!.status === 'done' || phases[i]!.status === 'failed') {
        target = i
        break
      }
    }
    if (target >= 0) setSelectedPhaseIdx(target)
  }, [currentRunningIdx, phases, mode])

  /** 真实运行：阶段 k —— 调用真实 API 写结果到 output。
   *  仅供 read / parse / extract 三步使用；classify 步骤由调用方内联实现 D-038 分流。 */
  const runPhase = useCallback(
    async (
      key: 'read' | 'parse' | 'extract',
      currentFile: File,
      resumeText?: string,
    ): Promise<
      | { kind: 'read' }
      | { kind: 'parse'; text: string }
      | { kind: 'extract'; experiences: ExtractExperienceItem[] }
    > => {
      setGlobalError(null)
      const startTs = Date.now()
      setPhases((arr) => setPhase(arr, key, { status: 'active', startedAt: startTs, endedAt: null, output: null }))

      const finish = (patch: Partial<UploadPhase>) => {
        const endTs = Date.now()
        setPhases((arr) => setPhase(arr, key, { ...patch, endedAt: endTs }))
      }

      try {
        if (key === 'read') {
          finish({
            status: 'done',
            output: {
              kind: 'read',
              payload: {
                name: currentFile.name,
                size: currentFile.size,
                type: currentFile.type || 'application/pdf',
                lastModified: currentFile.lastModified,
              },
            },
          })
          return { kind: 'read' }
        }
        if (key === 'parse') {
          const res = await resumeApi.uploadPdf(currentFile)
          finish({
            status: 'done',
            output: {
              kind: 'parse',
              payload: {
                length: (res.text ?? '').length,
                summary: firstLine(res.text ?? ''),
              },
            },
          })
          return { kind: 'parse', text: res.text ?? '' }
        }
        // key === 'extract'
        if (!resumeText) throw new ApiError(0, { message: '内部错误：缺少待提取文本。' })
        const res = await experienceApi.extract({ resume_text: resumeText })
        const exps = res.experiences ?? []
        const byType: Record<string, number> = {}
        let direct = 0
        let inferred = 0
        for (const e of exps) {
          byType[e.type] = (byType[e.type] ?? 0) + 1
          const c = e.provenance?.classification
          if (c === 'direct') direct++
          else inferred++
        }
        finish({
          status: 'done',
          output: {
            kind: 'extract',
            payload: { total: exps.length, byType, byClass: { direct, inferred } },
          },
        })
        return { kind: 'extract', experiences: exps }
      } catch (e) {
        const err =
          e instanceof ApiError
            ? { message: e.message, code: e.error_code, stage: e.stage, retryable: e.retryable }
            : { message: e instanceof Error ? e.message : String(e) }
        finish({ status: 'failed', output: { kind: 'error', payload: err } })
        throw e
      }
    },
    [],
  )

  /** 完整链路：read → parse → extract → classify（同步串行，串行失败停在该阶段）。 */
  const runChain = useCallback(
    async (f: File) => {
      const seq = ++runSeq.current
      setMode('parsing')
      setSelectedPhaseIdx(0)
      setPhases(emptyPhases())
      setGlobalError(null)
      setReviewItems([])
      setReviewResults([])
      setReviewSummary(null)
      setDoneOk(false)

      try {
        await runPhase('read', f)
        if (runSeq.current !== seq) return
        const parseRes = await runPhase('parse', f)
        if (runSeq.current !== seq) return
        if (!parseRes || parseRes.kind !== 'parse') return
        const extractRes = await runPhase('extract', f, parseRes.text)
        if (runSeq.current !== seq) return
        if (!extractRes || extractRes.kind !== 'extract') return

        // 阶段④：分类整理 —— 直接在本处实现 D-038 分流（不再走 runPhase('classify') 内部错误占位）
        const startTs = Date.now()
        setPhases((arr) => setPhase(arr, 'classify', { status: 'active', startedAt: startTs, endedAt: null, output: null }))
        const exps = extractRes.experiences
        const direct = exps.filter((e) => e.provenance?.classification === 'direct')
        const needsConfirm = exps.filter((e) => e.provenance?.classification !== 'direct')

        let directSaved = 0
        const directFailed: ExtractExperienceItem[] = []
        for (const item of direct) {
          try {
            await experienceApi.create(toCreatePayload(item))
            directSaved++
          } catch {
            directFailed.push(item)
          }
        }
        const reviewAll = [...needsConfirm, ...directFailed]
        const summary: ClassifyOk = {
          directSaved,
          directFailed: directFailed.length,
          inferred: needsConfirm.length,
          total: exps.length,
        }
        const endTs = Date.now()
        setPhases((arr) =>
          setPhase(arr, 'classify', {
            status: 'done',
            endedAt: endTs,
            output: { kind: 'classify', payload: summary },
          }),
        )
        setReviewItems(reviewAll)
        if (directFailed.length > 0) {
          setReviewSummary(
            `已自动整理 ${directSaved} 项进入「我的经历」；${directFailed.length} 项自动保存失败，请在下方核对后重新保存。`,
          )
        } else if (direct.length > 0) {
          setReviewSummary(`已自动整理 ${directSaved} 项进入「我的经历」。`)
        } else {
          setReviewSummary('本次提取均为 AI 推断 / 补全内容，请在下方逐项核对后保存。')
        }
        setMode('review')
      } catch (e) {
        if (runSeq.current !== seq) return
        const err =
          e instanceof ApiError
            ? { message: e.message, code: e.error_code, stage: e.stage, retryable: e.retryable }
            : { message: e instanceof Error ? e.message : String(e) }
        setGlobalError(err)
      }
    },
    [runPhase],
  )

  // 入口文件已传入（来自欢迎页）：立即开始链路
  useEffect(() => {
    if (incoming) {
      void runChain(incoming)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // —— idle 视图：拖拽 / 选择 ——
  function takeIdleFile(f: File | undefined) {
    if (!f) return
    if (!(f.type === 'application/pdf' || /\.pdf$/i.test(f.name))) {
      window.alert('仅支持 PDF 文件，请重新选择。')
      return
    }
    setFile(f)
    void runChain(f)
  }

  function onIdleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    takeIdleFile(e.target.files?.[0])
    e.target.value = ''
  }
  function onIdleDrop(e: React.DragEvent<HTMLLabelElement>) {
    e.preventDefault()
    setDragOver(false)
    takeIdleFile(e.dataTransfer?.files?.[0])
  }

  // —— 阶段重试：定位到失败阶段并从那里重跑整条链 ——
  function retryFromPhase(fromKey: UploadPhase['key']) {
    if (!file) return
    // 重跑策略：重置 read 之后的「已完成 / 失败」标记后，从 fromKey 开始串行。
    // 为简化实现：直接重置整条链 + 从 fromKey 开始逐步调用。
    const seq = ++runSeq.current
    setMode('parsing')
    setReviewItems([])
    setReviewResults([])
    setReviewSummary(null)
    setDoneOk(false)
    setGlobalError(null)

    // 重置从 fromKey 开始到末尾
    const order: UploadPhase['key'][] = ['read', 'parse', 'extract', 'classify']
    const startIdx = order.indexOf(fromKey)
    setPhases((arr) =>
      arr.map((p, i) =>
        i >= startIdx
          ? { ...p, status: 'pending', startedAt: null, endedAt: null, output: null }
          : p,
      ),
    )
    setSelectedPhaseIdx(startIdx)

    void (async () => {
      try {
        await runPhase('read', file)
        if (runSeq.current !== seq) return
        const parseRes = await runPhase('parse', file)
        if (runSeq.current !== seq) return
        if (!parseRes || parseRes.kind !== 'parse') return
        const extractRes = await runPhase('extract', file, parseRes.text)
        if (runSeq.current !== seq) return
        if (!extractRes || extractRes.kind !== 'extract') return

        // 阶段④
        const startTs = Date.now()
        setPhases((arr) => setPhase(arr, 'classify', { status: 'active', startedAt: startTs, endedAt: null, output: null }))
        const exps = extractRes.experiences
        const direct = exps.filter((e) => e.provenance?.classification === 'direct')
        const needsConfirm = exps.filter((e) => e.provenance?.classification !== 'direct')

        let directSaved = 0
        const directFailed: ExtractExperienceItem[] = []
        for (const item of direct) {
          try {
            await experienceApi.create(toCreatePayload(item))
            directSaved++
          } catch {
            directFailed.push(item)
          }
        }
        const reviewAll = [...needsConfirm, ...directFailed]
        const endTs = Date.now()
        setPhases((arr) =>
          setPhase(arr, 'classify', {
            status: 'done',
            endedAt: endTs,
            output: {
              kind: 'classify',
              payload: {
                directSaved,
                directFailed: directFailed.length,
                inferred: needsConfirm.length,
                total: exps.length,
              } satisfies ClassifyOk,
            },
          }),
        )
        setReviewItems(reviewAll)
        if (directFailed.length > 0) {
          setReviewSummary(
            `已自动整理 ${directSaved} 项进入「我的经历」；${directFailed.length} 项自动保存失败，请在下方核对后重新保存。`,
          )
        } else if (direct.length > 0) {
          setReviewSummary(`已自动整理 ${directSaved} 项进入「我的经历」。`)
        } else {
          setReviewSummary('本次提取均为 AI 推断 / 补全内容，请在下方逐项核对后保存。')
        }
        setMode('review')
      } catch (e) {
        if (runSeq.current !== seq) return
        const err =
          e instanceof ApiError
            ? { message: e.message, code: e.error_code, stage: e.stage, retryable: e.retryable }
            : { message: e instanceof Error ? e.message : String(e) }
        setGlobalError(err)
      }
    })()
  }

  function restartFlow() {
    runSeq.current += 1
    setMode('idle')
    setFile(null)
    setPhases(emptyPhases())
    setSelectedPhaseIdx(0)
    setReviewItems([])
    setReviewResults([])
    setReviewSummary(null)
    setDoneOk(false)
    setGlobalError(null)
    navigate('/upload', { replace: true, state: null })
  }

  // —— review UI handlers ——
  function updateImported(idx: number, patch: Partial<ExperienceItem>) {
    setReviewItems((arr) => arr.map((it, i) => (i === idx ? { ...it, ...patch } : it)))
  }

  async function saveAllReview() {
    setReviewSaving(true)
    setDoneOk(false)
    const results: { idx: number; ok: boolean; msg: string }[] = []
    for (let i = 0; i < reviewItems.length; i++) {
      try {
        await experienceApi.create(toCreatePayload(reviewItems[i]!))
        results.push({ idx: i, ok: true, msg: '已保存' })
      } catch (e) {
        results.push({
          idx: i,
          ok: false,
          msg: e instanceof ApiError ? e.message : String(e),
        })
      }
    }
    setReviewResults(results)
    setReviewSaving(false)
    setDoneOk(true)
  }

  // ====== 渲染 ======
  if (mode === 'idle') {
    return (
      <div className="page" style={{ gap: 'var(--s4)' }}>
        <div role="region" aria-label="上传现有简历" style={topbarStyle}>
          <span style={{ color: 'var(--ink-faint)' }}>第 1 步 · 准备经历</span>
          <span style={{ color: 'var(--border-strong)' }}>/</span>
          <span style={{ fontWeight: 600, color: 'var(--ink)' }}>上传现有简历</span>
          <span style={{ color: 'var(--border-strong)' }}>·</span>
          <span
            className="tag"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              height: 22,
              padding: '0 10px',
              color: 'var(--ok)',
              background: 'var(--ok-wash)',
            }}
          >
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor' }} />
            本机解析
          </span>
          <span
            className="tag"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              height: 22,
              padding: '0 10px',
              color: 'var(--ink-soft)',
              background: 'var(--surface-2)',
            }}
          >
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor' }} />
            不保留中间文件副本
          </span>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 'var(--s2)' }}>
            <Link className="btn btn--secondary btn--sm" to="/profile">
              返回我的经历
            </Link>
          </div>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1fr) 360px',
            gap: 'var(--s4)',
            alignItems: 'start',
          }}
        >
          <div className="card" style={{ padding: 'var(--s5)', minWidth: 0 }}>
            <label
              htmlFor="upload-pdf-input"
              className={'upload-dropzone' + (dragOver ? ' upload-dropzone--drag' : '')}
              onDragOver={(e) => {
                e.preventDefault()
                setDragOver(true)
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onIdleDrop}
            >
              <input
                ref={idleInputRef}
                id="upload-pdf-input"
                type="file"
                accept="application/pdf,.pdf"
                className="visually-hidden-file"
                onChange={onIdleFileChange}
                tabIndex={0}
                aria-label="选择 PDF 简历（单击或拖入）"
              />
              <div className="upload-dropzone__icon" aria-hidden="true">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <path d="M17 8l-5-5-5 5" />
                  <path d="M12 3v12" />
                </svg>
              </div>
              <h3 className="upload-dropzone__title">选择 PDF 或拖入此区域</h3>
              <p className="upload-dropzone__desc">
                仅支持文本型 PDF（≤ {fmtBytes(MAX_BYTES_DEFAULT)}），文件仅在本机解析。
              </p>
              <span className="btn btn--secondary" aria-hidden="true">选择文件</span>
            </label>
          </div>

          <aside style={{ minWidth: 0 }}>
            <div className="ai-stream" aria-live="polite">
              <div className="ai-stream__head">
                <span className="ai-stream__tag">AI 处理中</span>
                <span className="ai-stream__title">AI 解析过程</span>
              </div>
              <div className="ai-stream__list" role="log">
                <div className="ai-stream__empty">
                  选择或拖入 PDF 后，右侧会按「读取文件 → 本机解析 → 结构化提取 → 分类整理」四阶段展示真实结果事实；不是逐行 LLM 流，后端为同步请求。
                </div>
              </div>
            </div>
          </aside>
        </div>
      </div>
    )
  }

  // parsing / review 视图：左侧 4 阶段 radio + 右侧 ai-stream
  const processingFailed = globalError != null || failedPhaseIdx >= 0
  const viewPhaseIdx = processingFailed && failedPhaseIdx >= 0 ? failedPhaseIdx : safePhaseIdx
  const viewPhaseSafe = phases[viewPhaseIdx] ?? viewPhase

  return (
    <div
      className="page"
      style={{ maxWidth: 1200, width: '100%', margin: '0 auto', alignItems: 'stretch' }}
    >
      <div role="region" aria-label="上传现有简历" style={topbarStyle}>
        <span style={{ color: 'var(--ink-faint)' }}>第 1 步 · 准备经历</span>
        <span style={{ color: 'var(--border-strong)' }}>/</span>
        <span style={{ fontWeight: 600, color: 'var(--ink)' }}>上传现有简历</span>
        <span style={{ color: 'var(--border-strong)' }}>·</span>
        <span
          className="tag"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            height: 22,
            padding: '0 10px',
            color: 'var(--ok)',
            background: 'var(--ok-wash)',
          }}
        >
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor' }} />
          本机解析
        </span>
        {file && (
          <span
            className="tag"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              height: 22,
              padding: '0 10px',
              color: 'var(--ink-soft)',
              background: 'var(--surface-2)',
              maxWidth: 320,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={file.name}
          >
            {file.name}
          </span>
        )}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 'var(--s2)' }}>
          <Button variant="ghost" size="sm" onClick={restartFlow}>
            重新选择文件
          </Button>
        </div>
      </div>

      <div className="process-shell">
        <div className="process-main">
          <div className="process-header">
            <div className="process-header__eyebrow">
              上传现有简历 ·{' '}
              {processingFailed
                ? '解析未完成'
                : mode === 'review'
                  ? '解析完成 · 待确认'
                  : '解析中'}
            </div>
            <h1 className="process-header__h1">
              {processingFailed
                ? '简历解析未完成，可重试或重新选择文件'
                : mode === 'review'
                  ? '解析完成，请在下方核对需确认条目'
                  : '正在为本机解析这份 PDF'}
            </h1>
            <p className="process-header__desc">
              {processingFailed
                ? '失败原因来自真实后端响应；可重试当前阶段或重新选择文件。'
                : '系统按真实阶段推进；每条内容都来自真实响应，不展示虚构进度。'}
            </p>
          </div>

          <div className="process-elapsed" aria-label="已用时">
            <span>已用时</span>
            <span className="process-elapsed__value">{fmtElapsed(totalElapsedMs)}</span>
          </div>

          <UploadPhaseList
            phases={phases}
            selectedIdx={viewPhaseIdx >= 0 ? viewPhaseIdx : safePhaseIdx}
            currentRunningIdx={currentRunningIdx}
            onSelect={setSelectedPhaseIdx}
          />

          <div className="process-foot">
            <div className="process-foot__left">
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  fontSize: 12,
                  color: 'var(--ok)',
                  background: 'var(--ok-wash)',
                  padding: '2px 8px',
                  borderRadius: 999,
                }}
              >
                <span
                  style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor' }}
                />
                输入已保留
              </span>
              <span>
                {processingFailed
                  ? '失败时仍可重试当前阶段；输入（已选文件）不会被静默丢弃。'
                  : '进度会随服务端响应推进，可点击已开始阶段查看该阶段真实结果事实。'}
              </span>
            </div>
            <div className="hstack" style={{ marginTop: 0 }}>
              <Button variant="ghost" size="sm" onClick={restartFlow} disabled={mode === 'parsing'}>
                重新选择文件
              </Button>
            </div>
          </div>
        </div>

        <aside className="process-side" aria-label="阶段明细">
          {processingFailed ? (
            <FailurePanel
              phase={viewPhaseSafe}
              phaseIdx={viewPhaseIdx >= 0 ? viewPhaseIdx : safePhaseIdx}
              onRetry={() => {
                const failedKey = phases[failedPhaseIdx]?.key
                if (failedKey) retryFromPhase(failedKey)
                else if (viewPhaseSafe) retryFromPhase(viewPhaseSafe.key)
              }}
              onRestart={restartFlow}
              onChangeFile={restartFlow}
              onGoProfile={() => navigate('/profile')}
            />
          ) : (
            <PhaseOutput
              phase={viewPhaseSafe}
              phaseIdx={viewPhaseIdx >= 0 ? viewPhaseIdx : safePhaseIdx}
              onRetry={retryFromPhase}
              parsing={mode === 'parsing'}
            />
          )}
        </aside>
      </div>

      {mode === 'review' && (
        <div
          className="card"
          style={{ marginTop: 'var(--s5)', padding: 'var(--s4) var(--s5)' }}
        >
          <div className="card__title" style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--s2)' }}>
            需确认条目
            <span style={{ color: 'var(--ink-faint)', fontSize: 12, fontWeight: 400 }}>
              内容含 AI 推断 / 补全，请核对原文后保存
            </span>
          </div>
          {reviewSummary && (
            <div className="notice notice--ok" style={{ margin: 'var(--s3) 0' }}>
              {reviewSummary}
            </div>
          )}

          {reviewItems.length === 0 ? (
            <div className="empty">
              <p className="empty__desc">本次提取全部自动整理入库，无需逐条确认。</p>
              <Button variant="secondary" onClick={() => navigate('/profile')}>
                查看我的经历
              </Button>
            </div>
          ) : (
            <div className="stack" style={{ marginTop: 'var(--s3)' }}>
              {reviewItems.map((item, idx) => {
                const r = reviewResults.find((x) => x.idx === idx)
                const snippets = item.provenance?.source_snippets ?? []
                return (
                  <div className="exp-item" key={idx}>
                    <div className="exp-item__head">
                      <span className="exp-item__title">
                        {idx + 1}. {item.title || '（未命名）'}
                      </span>
                      <Badge tone="warn">需确认</Badge>
                      {r && <Badge tone={r.ok ? 'ok' : 'danger'}>{r.ok ? '已保存' : '失败'}</Badge>}
                    </div>
                    {snippets.length > 0 && (
                      <blockquote className="exp-source">
                        {snippets.map((s, si) => (
                          <div key={si}>“{s}”</div>
                        ))}
                      </blockquote>
                    )}
                    <div className="form-grid" style={{ marginTop: 'var(--s3)' }}>
                      <Field label="类型">
                        <Select
                          value={item.type}
                          onChange={(e) => updateImported(idx, { type: e.target.value })}
                        >
                          {EXPERIENCE_TYPES.map((t) => (
                            <option key={t.value} value={t.value}>
                              {t.label}
                            </option>
                          ))}
                        </Select>
                      </Field>
                      <Field label="标题">
                        <TextInput
                          value={item.title}
                          onChange={(e) => updateImported(idx, { title: e.target.value })}
                        />
                      </Field>
                      <Field label="公司 / 组织">
                        <TextInput
                          value={item.company}
                          onChange={(e) => updateImported(idx, { company: e.target.value })}
                        />
                      </Field>
                      <Field label="时间">
                        <TextInput
                          value={item.time}
                          onChange={(e) => updateImported(idx, { time: e.target.value })}
                        />
                      </Field>
                      <Field label="角色">
                        <TextInput
                          value={item.role}
                          onChange={(e) => updateImported(idx, { role: e.target.value })}
                        />
                      </Field>
                      <Field label="技能（逗号分隔）">
                        <TextInput
                          value={(item.skills ?? []).join(', ')}
                          onChange={(e) => updateImported(idx, { skills: splitSkills(e.target.value) })}
                        />
                      </Field>
                    </div>
                    <div className="stack" style={{ marginTop: 'var(--s4)' }}>
                      <Field label="职责描述">
                        <TextArea
                          value={item.description}
                          onChange={(e) => updateImported(idx, { description: e.target.value })}
                        />
                      </Field>
                      <Field label="成果（每行一条）">
                        <TextArea
                          value={(item.achievements ?? []).join('\n')}
                          onChange={(e) =>
                            updateImported(idx, { achievements: splitAchievements(e.target.value) })
                          }
                        />
                      </Field>
                      {r && !r.ok && <p className="notice notice--danger">{r.msg}</p>}
                    </div>
                  </div>
                )
              })}
              <div className="hstack" style={{ marginTop: 'var(--s2)' }}>
                <Button onClick={() => void saveAllReview()} disabled={reviewSaving}>
                  {reviewSaving ? '保存中…' : '批量保存'}
                </Button>
                {doneOk && (
                  <Button
                    variant="ghost"
                    onClick={() => navigate('/profile')}
                  >
                    完成 · 查看我的经历
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
