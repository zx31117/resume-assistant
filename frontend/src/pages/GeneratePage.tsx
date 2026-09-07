import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import OperationTimeline from '../components/OperationTimeline'
import StageFlowList, {
  calcPhaseStatus,
  phaseElapsedMs,
  type PhaseStatus,
  type StageFlowPhase,
} from '../components/StageFlowList'
import { Field, TextArea, TextInput } from '../components/ui/Field'
import { useServices } from '../services'
import { ApiError, newOperationId } from '../api/client'
import { useOperation, statusLabel, statusTone, fmtMs } from '../hooks/useOperation'
import type {
  DocPreviewSection,
  EvidenceFact,
  JDAnalysis,
  OperationDetail,
  ResumeDocxGenerateResponse,
  SystemStatus,
} from '../api/types'

/**
 * V2.1.0（T5）：生成简历 —— 按 DS-002 基线重构交互，但所有能力保持真实：
 * - 数据全部来自 useServices() 端口：template.list / system.status / jd.analyze / resume.generateDocx；
 * - 生成过程进度完全由 operation 轮询事件驱动（useOperation），不虚构百分比或固定时长；
 * - 「生成前检查」只判断前端可真实判定的项：姓名缺失 / 无经历 / JD 过短。
 *
 * 4 个用户语言阶段的点亮规则（真实后端阶段码见 backend/services/resume_generation_service.py，
 * 事件由 backend/core/operations.py 以 STAGE_STARTED/STAGE_COMPLETED.{code} 记录）：
 *   阶段1 挑选事实 ← select_experiences + select_evidence（两层选材）
 *   阶段2 起草表达 ← content_generation（受约束改写）
 *   阶段3 排版装配 ← resume_build（Builder 构建与一致性整理）
 *   阶段4 DOCX 装配 ← render + save_docx + response_assembly（渲染/保存/下载就绪）
 * 某阶段只有在它对应的全部真实 stage 出现 COMPLETED 事件后才点亮为「已完成」，
 * 宁可少点亮也不猜。
 */

/** JD 最短长度：过短时后端 strict JD 分析不可靠，前端阻止生成。 */
const JD_MIN_CHARS = 60
/** JD 文本变化后自动分析的防抖间隔。 */
const JD_ANALYZE_DEBOUNCE_MS = 600

interface Identity {
  name: string
  phone: string
  email: string
  location: string
}

const EMPTY_IDENTITY: Identity = { name: '', phone: '', email: '', location: '' }

interface GenError {
  message: string
  stage?: string
  code?: string
  retryable?: boolean
}

function toGenError(e: unknown): GenError {
  if (e instanceof ApiError) {
    return {
      message: e.message,
      stage: e.stage,
      code: e.error_code,
      retryable: e.retryable,
    }
  }
  return { message: String(e) }
}

const PROCESS_PHASES: StageFlowPhase[] = [
  {
    key: 'selection',
    label: '从你的经历中挑选相关事实',
    detail: '按目标岗位 JD 决定选取哪些事实与时段',
    codes: ['select_experiences', 'select_evidence'],
  },
  {
    key: 'rewrite',
    label: '受约束起草表达',
    detail: '基于已选事实生成 bullet，保留事实引用',
    codes: ['content_generation'],
  },
  {
    key: 'layout',
    label: '排版装配',
    detail: '固定结构内做排版与一致性整理',
    codes: ['resume_build'],
  },
  {
    key: 'docx',
    label: '完成 DOCX 装配',
    detail: '确定性 Builder 渲染，可下载',
    codes: ['render', 'save_docx', 'response_assembly'],
  },
]

/** 单条摘要 chips 区块（JDAnalysis 真实字段驱动；按 DS-002 冻结原型以「标签 · 值」单 chip 形式展示）。 */
function AnalysisChips({ a }: { a: JDAnalysis }) {
  const rows: Array<{ label: string; values: string[] }> = []
  if (a.position) rows.push({ label: '目标岗位', values: [a.position] })
  if (a.required_skills.length) rows.push({ label: '核心要求', values: a.required_skills })
  if (a.preferred_skills.length) rows.push({ label: '加分项', values: a.preferred_skills })
  if (a.experience_preferences.length) rows.push({ label: '经验偏好', values: a.experience_preferences })
  if (a.keywords.length) rows.push({ label: '关键词', values: a.keywords })
  if (a.industry) rows.push({ label: '行业', values: [a.industry] })
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--s2)', marginTop: 'var(--s3)' }}>
      {rows.map((r) => (
        <span
          className="tag"
          key={r.label}
          style={{ height: 'auto', padding: '4px 10px', fontSize: 12, color: 'var(--ink)' }}
        >
          <strong style={{ fontWeight: 600 }}>{r.label}</strong>
          <span style={{ margin: '0 6px', color: 'var(--border-strong)' }}>·</span>
          {r.values.join(' · ')}
        </span>
      ))}
    </div>
  )
}

/** V2.1.0 T6：依据面板 —— 点击 bullet 后展示其真实 evidence（事实原文 / 采用原因 / 所属经历）。
 *  一切以 `result.evidence`（来自后端 Fact 表的真实原文）与 `result.build_meta.bullet_fact_refs`
 *  （后端 R7 per-bullet 引用映射）为准；本流水线不记录 per-fact 采用原因，故 EvidenceFact.reason
 *  保持空、不编造；selection_reason 仅在该经历真实携带时显示。
 */
function EvidencePanel({
  result,
  selected,
  docPreview,
}: {
  result: ResumeDocxGenerateResponse
  selected: { sectionIdx: number; entryIdx: number; bulletIdx: number } | null
  docPreview: DocPreviewSection[] | null
}) {
  if (!selected || !docPreview) {
    return (
      <div>
        <div className="evidence-panel__empty">未选中任何 bullet。</div>
        <div className="evidence-panel__hint">
          点击左侧「内容预览」中的 bullet 即可查看其真实事实原文与采用原因；
          流水线不记录 per-fact 采用原因时不会编造内容。
        </div>
      </div>
    )
  }
  const sec = docPreview[selected.sectionIdx]
  const ent = sec?.entries[selected.entryIdx]
  if (!ent) {
    return <div className="evidence-panel__empty">未选中任何 bullet。</div>
  }
  const bullet = ent.bullets[selected.bulletIdx] ?? ''
  const expId = ent.experience_id ?? null
  const perBulletRefs = expId
    ? (result.build_meta.bullet_fact_refs?.[expId]?.[selected.bulletIdx] ?? [])
    : []
  const factIds = perBulletRefs.filter((x) => !!x)
  const factsForExp = expId ? (result.evidence?.[expId] ?? []) : []
  const facts: EvidenceFact[] = factIds
    .map((fid) => factsForExp.find((f) => f.fact_id === fid))
    .filter((x): x is EvidenceFact => !!x)
  return (
    <div>
      <div className="evidence-panel__meta">
        {ent.heading && (
          <div className="evidence-panel__meta-row">
            <strong>所在条目</strong>
            <span style={{ color: 'var(--ink)' }}>{ent.heading}</span>
          </div>
        )}
        {ent.subhead && (
          <div className="evidence-panel__meta-row">
            <strong>时段</strong>
            <span style={{ color: 'var(--ink)' }}>{ent.subhead}</span>
          </div>
        )}
        <div className="evidence-panel__meta-row">
          <strong>当前 bullet</strong>
          <span style={{ color: 'var(--ink)' }}>{bullet || '—'}</span>
        </div>
      </div>

      {ent.selection_reason && (
        <div className="evidence-panel__meta" style={{ marginTop: 'var(--s3)' }}>
          <div className="evidence-panel__meta-row">
            <strong>采用原因</strong>
            <span style={{ color: 'var(--ink)' }}>{ent.selection_reason}</span>
          </div>
        </div>
      )}

      <div style={{ marginTop: 'var(--s3)' }}>
        <div
          className="evidence-panel__meta-row"
          style={{ fontWeight: 600, color: 'var(--ink)', marginBottom: 'var(--s1)' }}
        >
          事实原文
        </div>
        {facts.length > 0 ? (
          facts.map((f) => (
            <div key={f.fact_id} className="evidence-panel__fact">
              <div className="evidence-panel__fact-text">{f.text || '（事实原文为空）'}</div>
              <div className="evidence-panel__fact-meta">
                所属经历：{f.experience_id ?? '—'} · fact_id: {f.fact_id}
                {f.reason ? ` · 采用：${f.reason}` : ''}
              </div>
            </div>
          ))
        ) : (
          <div className="evidence-panel__empty">本条没有可回查的独立事实引用。</div>
        )}
      </div>

      {expId && factIds.length === 0 && (
        <div className="evidence-panel__hint">
          （该 bullet 未在本次第二层选材中关联到独立 fact，可能是材料不足走 SQL 回退；不虚构理由）
        </div>
      )}
    </div>
  )
}

/* ============================================================
   V2.1.0 T12-R4：处理视图右侧组件
   - PhaseStream：单选阶段的真实 stage 事件流（按 phase.codes 过滤）。
   - FailurePanel：失败态右侧面板（阶段名 + 原因 + 诊断 + 恢复动作）。
   - 全部基于真实 operation.stages / genError，不编造 stage_code 直出。
   ============================================================ */

const PHASE_STREAM_RESOURCE_LABEL: Record<string, string> = {
  LOCAL_DB: '本地数据库',
  LOCAL_FILE: '本地文件',
  LOCAL_CPU: '本地计算',
  LLM: 'LLM',
  EMBEDDING: 'Embedding',
}

function phaseEventLabel(t: string): string {
  switch (t) {
    case 'STARTED':
      return '开始'
    case 'COMPLETED':
      return '完成'
    case 'FAILED':
      return '失败'
    case 'ROLLED_BACK':
      return '已回滚'
    default:
      return t
  }
}

function phaseEventTone(t: string): 'neutral' | 'ok' | 'warn' | 'danger' {
  switch (t) {
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

interface PhaseStreamProps {
  phase: StageFlowPhase
  phaseIdx: number
  status: PhaseStatus
  operation: OperationDetail | null
}

function PhaseStream({ phase, phaseIdx, status, operation }: PhaseStreamProps) {
  const events = (operation?.stages ?? []).filter((e) => phase.codes.includes(e.stage_code))
  const elapsed = phaseElapsedMs(operation, phase.codes)
  const tag = status === 'failed' ? '阶段失败' : status === 'active' ? '正在执行' : '阶段明细'
  return (
    <div className="ai-stream" aria-live="polite">
      <div className="ai-stream__head">
        <span className="ai-stream__tag">{tag}</span>
        <span className="ai-stream__title">
          {phaseIdx + 1}. {phase.label}
        </span>
        <span className="ai-stream__sub">{elapsed != null ? fmtMs(elapsed) : '—'}</span>
      </div>
      <div className="ai-stream__list" role="log">
        {events.length === 0 ? (
          <div className="ai-stream__empty">
            {status === 'pending'
              ? '该阶段尚未开始；可点击左侧已开始阶段查看明细。'
              : '等待服务端推送该阶段事件…'}
          </div>
        ) : (
          events.map((ev, i) => {
            const isStart = ev.event_type === 'STARTED'
            const recent = operation?.recent_stats?.[ev.stage_code]
            const stageDisplay = ev.stage_name || phase.label
            return (
              <div
                key={`${ev.seq}-${i}`}
                className={`ai-stream__line ai-stream__line--${ev.event_type.toLowerCase()}`}
              >
                <div className="ai-stream__line-main">
                  <Badge tone={phaseEventTone(ev.event_type)}>{phaseEventLabel(ev.event_type)}</Badge>
                  <span className="ai-stream__line-name">{stageDisplay}</span>
                  {!isStart && (
                    <span className="ai-stream__line-elapsed">{fmtMs(ev.elapsed_ms)}</span>
                  )}
                </div>
                {ev.message ? <div className="ai-stream__line-msg">{ev.message}</div> : null}
                {(ev.resource_type || ev.attempt > 1 || recent) && (
                  <div className="ai-stream__line-meta">
                    {ev.resource_type ? (
                      <span>{PHASE_STREAM_RESOURCE_LABEL[ev.resource_type] ?? ev.resource_type}</span>
                    ) : null}
                    {ev.attempt > 1 ? <span>· 第 {ev.attempt}/{ev.max_attempts} 次</span> : null}
                    {recent && recent.sample_size > 0 ? (
                      <span>
                        · 近{recent.sample_size}次 中位 {fmtMs(recent.median_ms)} / 最大{' '}
                        {fmtMs(recent.max_ms)}
                      </span>
                    ) : null}
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

interface FailurePanelProps {
  phase: StageFlowPhase | null
  phaseIdx: number
  op: OperationDetail | null
  genError: GenError | null
  generating: boolean
  onRegenerate: () => void
  onBackToEdit: () => void
}

function FailurePanel({
  phase,
  phaseIdx,
  op,
  genError,
  generating,
  onRegenerate,
  onBackToEdit,
}: FailurePanelProps) {
  const reason = genError?.message ?? (op ? statusLabel(op.status) : '发生未知错误')
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
        生成未完成
      </div>
      {phase ? (
        <div className="process-error__phase">
          失败阶段：{phaseIdx + 1}. {phase.label}
        </div>
      ) : null}
      <div className="process-error__reason">{reason}</div>
      {(genError?.stage || genError?.code) && (
        <div className="process-error__diag">
          后端返回：stage={genError?.stage ?? '—'} · code={genError?.code ?? '—'}
        </div>
      )}
      {op && (
        <div className="process-error__diag">
          操作 #{op.operation_id.slice(0, 8)} {statusLabel(op.status)}
          {op.diagnostic_code ? ` · 诊断码 ${op.diagnostic_code}` : ''}
          {op.attempt > 1 || op.max_attempts > 1
            ? ` · 尝试 ${op.attempt}/${op.max_attempts}`
            : ''}
        </div>
      )}
      <div className="process-error__actions">
        <Button variant="primary" size="sm" disabled={generating} onClick={onRegenerate}>
          重新生成
        </Button>
        <Button variant="secondary" size="sm" disabled={generating} onClick={onBackToEdit}>
          返回修改
        </Button>
      </div>
      <div className="process-error__note">输入已保留，返回修改不会丢失任何字段。</div>
    </div>
  )
}

export default function GeneratePage() {
  const services = useServices()

  // —— 元信息：固定模板（后端 is_default，无 UI）+ 系统状态 ——
  const [templateId, setTemplateId] = useState('')
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [metaError, setMetaError] = useState<string | null>(null)

  // —— 身份（仅本次请求使用）——
  const [identity, setIdentity] = useState<Identity>(EMPTY_IDENTITY)
  const [editingIdentity, setEditingIdentity] = useState(false)

  // —— 目标岗位 JD 与自动分析 ——
  const [jd, setJd] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [analysis, setAnalysis] = useState<JDAnalysis | null>(null)
  const [analyzedFor, setAnalyzedFor] = useState('')
  const [analyzeError, setAnalyzeError] = useState<string | null>(null)
  const analyzedForRef = useRef('')
  const jdRef = useRef('')
  const analyzeSeq = useRef(0)
  const analyzingRef = useRef(false)

  // —— 生成运行 ——
  const [view, setView] = useState<'input' | 'processing'>('input')
  const [generating, setGenerating] = useState(false)
  const [opId, setOpId] = useState<string | null>(null)
  const [result, setResult] = useState<ResumeDocxGenerateResponse | null>(null)
  const [genError, setGenError] = useState<GenError | null>(null)
  // V2.1.0 T6：当前选中的 bullet（用于依据面板）；新生成结果时清空
  const [selectedBullet, setSelectedBullet] = useState<
    { sectionIdx: number; entryIdx: number; bulletIdx: number } | null
  >(null)
  const runSeq = useRef(0)

  useEffect(() => {
    setSelectedBullet(null)
  }, [result])

  // V2.1.0 T12-R4：处理视图左侧 4 阶段 radio 当前选中（与「当前运行」解耦）。
  // - 规则：① 每次 op 轮询更新时，若「当前活动」高层阶段发生变化，自动切到新活动阶段；
  //        ② 用户主动点击已开始/已完成的阶段可回看，不被立即覆盖；
  //        ③ 离开处理视图或新一次生成时重置。
  const [selectedPhaseIdx, setSelectedPhaseIdx] = useState(0)
  const lastActiveIdxRef = useRef<number>(-1)

  useEffect(() => {
    if (opId) {
      setSelectedPhaseIdx(0)
      lastActiveIdxRef.current = -1
    }
  }, [opId])

  // 生成期间轮询该 op 的真实阶段（约 1s，页面不可见时 3s）；离开处理视图即停止。
  const polled = useOperation(opId, view === 'processing' && opId != null && !result)
  // 仅接受与当前 op 匹配的快照，避免「重新生成」后旧快照短暂串场
  const operation = polled && polled.operation_id === opId ? polled : null

  // 4 高层阶段的实时状态（来自真实 stage 事件，不提前点亮、不虚构）。
  const phaseStatuses: PhaseStatus[] = useMemo(
    () => PROCESS_PHASES.map((p) => calcPhaseStatus(operation, p.codes)),
    [operation],
  )
  const currentRunningIdx = useMemo(
    () => phaseStatuses.findIndex((s) => s === 'active'),
    [phaseStatuses],
  )
  const failedPhaseIdx = useMemo(
    () => phaseStatuses.findIndex((s) => s === 'failed'),
    [phaseStatuses],
  )

  // 自动跟随「当前活动」阶段：新活动阶段出现 / 切换时同步右侧。
  useEffect(() => {
    if (view !== 'processing' || result) return
    if (currentRunningIdx >= 0) {
      if (currentRunningIdx !== lastActiveIdxRef.current) {
        lastActiveIdxRef.current = currentRunningIdx
        setSelectedPhaseIdx(currentRunningIdx)
      }
    } else if (operation) {
      // 没有活动阶段（可能全部已完成或失败）→ 默认显示最后已完成/失败的阶段
      let target = -1
      for (let i = phaseStatuses.length - 1; i >= 0; i--) {
        if (phaseStatuses[i] === 'done' || phaseStatuses[i] === 'failed') {
          target = i
          break
        }
      }
      if (target >= 0 && target !== selectedPhaseIdx) setSelectedPhaseIdx(target)
    }
  }, [view, result, currentRunningIdx, phaseStatuses, operation, selectedPhaseIdx])

  useEffect(() => {
    jdRef.current = jd
  }, [jd])

  // —— 元信息加载：固定模板（取后端 is_default 供 generateDocx 使用，无 UI） ——
  const loadMeta = useCallback(async () => {
    try {
      const [tpl, st] = await Promise.all([services.template.list(), services.system.status()])
      const def = tpl.templates.find((t) => t.is_default) ?? tpl.templates[0]
      setTemplateId((cur) => cur || def?.template_id || '')
      setStatus(st)
      setMetaError(null)
    } catch (e) {
      setMetaError(e instanceof ApiError ? e.message : String(e))
    }
  }, [services])

  useEffect(() => {
    void loadMeta()
  }, [loadMeta])

  // —— 真实前端可判定信息 ——
  const factCount = status?.counts?.fact
  const experienceCount = status?.counts?.experience

  // —— JD 自动分析 ——
  const jdTrimmed = jd.trim()

  async function doAnalyze(text: string) {
    if (analyzingRef.current && analyzedForRef.current === text) return
    const seq = ++analyzeSeq.current
    analyzingRef.current = true
    setAnalyzing(true)
    setAnalyzeError(null)
    try {
      const res = await services.jd.analyze({ jd_text: text })
      if (analyzeSeq.current !== seq) return
      if (jdRef.current.trim() !== text) return // JD 又变了：本次结果过期，不落地
      setAnalysis(res)
      setAnalyzedFor(text)
      analyzedForRef.current = text
    } catch (e) {
      if (analyzeSeq.current !== seq) return
      setAnalyzeError(e instanceof ApiError ? e.message : String(e))
    } finally {
      if (analyzeSeq.current === seq) {
        analyzingRef.current = false
        setAnalyzing(false)
      }
    }
  }

  // JD < 最短长度 → 清空摘要；≥ 最短长度 → 防抖自动分析一次
  useEffect(() => {
    if (jdTrimmed.length < JD_MIN_CHARS) {
      setAnalysis(null)
      setAnalyzedFor('')
      analyzedForRef.current = ''
      return
    }
    const timer = window.setTimeout(() => {
      if (analyzedForRef.current !== jdTrimmed) void doAnalyze(jdTrimmed)
    }, JD_ANALYZE_DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jd])

  // 分析摘要仅在其对应文本与当前 JD 一致时有效；JD 改动后旧摘要视为失效
  const analysisFresh = analysis !== null && analyzedFor === jdTrimmed
  const shownAnalysis = analysisFresh ? analysis : null
  const jdTooShort = jdTrimmed.length < JD_MIN_CHARS

  // —— 生成前检查（只展示前端可真实判定的项）——
  const issues = useMemo(() => {
    const list: Array<{ title: string; desc: string }> = []
    if (!identity.name.trim()) list.push({ title: '姓名必填', desc: '请确认已填入姓名后再继续。' })
    if (experienceCount === 0)
      list.push({ title: '暂无可用经历', desc: '请先在「我的经历」录入内容。' })
    if (jdTooShort)
      list.push({ title: 'JD 过短', desc: `当前 ${jdTrimmed.length} 字，至少需要 ${JD_MIN_CHARS} 字。` })
    return list
  }, [identity.name, experienceCount, jdTooShort, jdTrimmed.length])

  const blocked = issues.length > 0

  // —— 生成（POST /api/resume/generate-docx，同步长链路；进度由 operation 轮询驱动）——
  async function beginGenerate() {
    if (blocked || generating) return
    const id = newOperationId()
    const seq = ++runSeq.current
    const targetPosition = (shownAnalysis?.position ?? '').trim()
    setOpId(id)
    setResult(null)
    setGenError(null)
    setGenerating(true)
    setView('processing')
    try {
      const res = await services.resume.generateDocx(
        {
          jd_text: jdTrimmed,
          template_id: templateId || undefined,
          profile: {
            name: identity.name.trim(),
            phone: identity.phone.trim() || undefined,
            email: identity.email.trim() || undefined,
            location: identity.location.trim() || null,
            target_position: targetPosition || undefined,
          },
        },
        id,
      )
      if (runSeq.current !== seq) return
      setResult(res)
    } catch (e) {
      if (runSeq.current !== seq) return
      setGenError(toGenError(e))
    } finally {
      if (runSeq.current === seq) setGenerating(false)
    }
  }

  function backToEdit() {
    runSeq.current += 1
    setView('input')
    setOpId(null)
    setResult(null)
    setGenError(null)
    setGenerating(false)
  }

  const targetLabel = shownAnalysis?.position ?? ''
  const processingFailed =
    genError != null ||
    (operation != null && ['FAILED', 'TIMED_OUT', 'INTERRUPTED'].includes(operation.status))

  const setIdentityField = (k: keyof Identity) => (v: string) =>
    setIdentity((p) => ({ ...p, [k]: v }))

  // ================= 输入视图（DS-002 冻结原型：gen-topbar / gen-grid > gen-main + gen-rail） =================
  if (view === 'input') {
    const position = (shownAnalysis?.position ?? '').trim()
    const factChipTone = metaError ? 'warn' : factCount != null ? 'ok' : 'neutral'
    const factChipText = metaError
      ? '状态读取失败'
      : factCount != null
        ? `${factCount} 条事实已就绪`
        : '读取状态中…'
    return (
      <div className="page" style={{ gap: 'var(--s4)' }}>
        {/* 任务上下文 topbar：冻结原型 .gen-topbar */}
        <div
          role="region"
          aria-label="当前任务上下文"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--s3)',
            padding: 'var(--s2) var(--s4)',
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--r-md)',
            boxShadow: 'var(--shadow-sm)',
            fontSize: 13,
            flexWrap: 'wrap',
          }}
        >
          <span style={{ color: 'var(--ink-faint)' }}>生成简历</span>
          <span style={{ color: 'var(--border-strong)' }}>/</span>
          <span style={{ fontWeight: 600, color: 'var(--ink)' }}>
            目标岗位 · {position || '待分析'}
          </span>
          <span
            className="tag"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              height: 22,
              padding: '0 10px',
              color:
                factChipTone === 'ok'
                  ? 'var(--ok)'
                  : factChipTone === 'warn'
                    ? 'var(--warn)'
                    : 'var(--ink-soft)',
              background:
                factChipTone === 'ok'
                  ? 'var(--ok-wash)'
                  : factChipTone === 'warn'
                    ? 'var(--warn-wash)'
                    : 'var(--surface-2)',
            }}
          >
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor' }} />
            {factChipText}
          </span>
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
            输入保留中
          </span>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 'var(--s2)' }}>
            <Link className="btn btn--secondary btn--sm" to="/profile">
              查看我的经历
            </Link>
          </div>
        </div>

        {/* 冻结原型 .gen-grid：minmax(0,1fr) 400px 左右两列 */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1fr) 400px',
            gap: 'var(--s4)',
            alignItems: 'start',
          }}
        >
          {/* —— 左侧 .gen-main：身份摘要 + 目标岗位与 JD —— */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s4)', minWidth: 0 }}>
            {/* .identity-card */}
            <div className="card" style={{ padding: 'var(--s4) var(--s5)' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: 'var(--s3)',
                  gap: 'var(--s3)',
                }}
              >
                <div className="card__title" style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--s2)' }}>
                  身份摘要
                  <span style={{ color: 'var(--ink-faint)', fontSize: 12, fontWeight: 400 }}>
                    默认可见 · 点击编辑
                  </span>
                </div>
                <Badge tone="accent">本次生成使用</Badge>
              </div>
              {editingIdentity ? (
                <div>
                  <div className="form-grid">
                    <Field label="姓名 *" hint="必填。仅用于本次生成；身份信息自动带入为后续版本功能。">
                      <TextInput
                        value={identity.name}
                        onChange={(e) => setIdentityField('name')(e.target.value)}
                        placeholder="例如：张三"
                      />
                    </Field>
                    <Field label="联系电话">
                      <TextInput
                        value={identity.phone}
                        onChange={(e) => setIdentityField('phone')(e.target.value)}
                        placeholder="选填"
                      />
                    </Field>
                    <Field label="电子邮箱">
                      <TextInput
                        type="email"
                        value={identity.email}
                        onChange={(e) => setIdentityField('email')(e.target.value)}
                        placeholder="选填"
                      />
                    </Field>
                    <Field label="所在地">
                      <TextInput
                        value={identity.location}
                        onChange={(e) => setIdentityField('location')(e.target.value)}
                        placeholder="选填，例如：北京"
                      />
                    </Field>
                  </div>
                  <div
                    style={{
                      marginTop: 'var(--s3)',
                      display: 'flex',
                      justifyContent: 'flex-end',
                    }}
                  >
                    <Button variant="secondary" size="sm" onClick={() => setEditingIdentity(false)}>
                      完成
                    </Button>
                  </div>
                </div>
              ) : (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--s3)',
                    flexWrap: 'wrap',
                    fontSize: 14,
                    lineHeight: 1.6,
                    color: 'var(--ink-soft)',
                  }}
                >
                  <span style={{ fontWeight: 600, color: 'var(--ink)' }}>
                    {identity.name.trim() || '—'}
                  </span>
                  {!identity.name.trim() && (
                    <span style={{ color: 'var(--warn)', fontWeight: 600, fontSize: 12 }}>
                      姓名未填写
                    </span>
                  )}
                  <span style={{ color: 'var(--border-strong)' }}>·</span>
                  <span>{identity.phone.trim() || '—'}</span>
                  <span style={{ color: 'var(--border-strong)' }}>·</span>
                  <span>{identity.email.trim() || '—'}</span>
                  <span style={{ color: 'var(--border-strong)' }}>·</span>
                  <span>{identity.location.trim() || '—'}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setEditingIdentity(true)}
                    disabled={generating}
                    style={{ marginLeft: 'auto', height: 30, padding: '0 10px' }}
                  >
                    编辑
                  </Button>
                </div>
              )}
            </div>

            {/* .jd-card */}
            <div className="card" style={{ padding: 'var(--s4) var(--s5)' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: 'var(--s3)',
                  gap: 'var(--s3)',
                }}
              >
                <div className="card__title" style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--s2)' }}>
                  目标岗位与 JD
                  <span style={{ color: 'var(--ink-faint)', fontSize: 12, fontWeight: 400 }}>同屏输入</span>
                </div>
                <Badge tone="ok">JD 分析 · Active</Badge>
              </div>
              <div className="field" style={{ marginBottom: 'var(--s3)' }}>
                <label htmlFor="i-jd" className="field__label">
                  粘贴完整岗位描述
                </label>
                <TextArea
                  id="i-jd"
                  value={jd}
                  onChange={(e) => setJd(e.target.value)}
                  placeholder="将招聘 JD 完整粘贴于此。系统会在右侧实时输出解析过程。"
                  style={{ minHeight: 220 }}
                />
              </div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: 'var(--s2)',
                  fontSize: 12,
                  color: 'var(--ink-soft)',
                }}
              >
                <span>
                  {jdTrimmed.length} 字
                  {jdTooShort ? `（不足 ${JD_MIN_CHARS} 字，暂不分析）` : ''}
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s2)' }}>
                  {analyzing ? (
                    <Badge tone="accent">分析中…</Badge>
                  ) : shownAnalysis ? (
                    <Badge tone="ok">已分析 · {shownAnalysis.position || '完成'}</Badge>
                  ) : analysis != null && !analysisFresh ? (
                    <Badge tone="warn">已修改，需重新分析</Badge>
                  ) : (
                    <Badge tone="neutral">{jdTooShort ? '待输入' : '待分析'}</Badge>
                  )}
                  {analysis != null && !analysisFresh && (
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={analyzing || jdTooShort}
                      onClick={() => void doAnalyze(jdTrimmed)}
                    >
                      立即分析
                    </Button>
                  )}
                </div>
              </div>
              {analyzeError && <div className="notice notice--danger">{analyzeError}</div>}
              {analysis != null && !analysisFresh && !analyzing && (
                <div className="notice notice--warn">
                  JD 已修改，将自动重新分析（约 {JD_ANALYZE_DEBOUNCE_MS / 1000}s 内触发）。
                </div>
              )}
              {shownAnalysis && <AnalysisChips a={shownAnalysis} />}
            </div>
          </div>

          {/* —— 右侧 .gen-rail：生成前检查 + 产品级说明 + gen-cta —— */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)', minWidth: 0 }}>
            {/* .missing-summary / .missing-panel：生成前检查 */}
            <div className="card" style={{ padding: 'var(--s4)' }}>
              <h4
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: 'var(--ink)',
                  margin: 0,
                  marginBottom: 'var(--s3)',
                }}
              >
                生成前检查
              </h4>
              {blocked ? (
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  {issues.map((it, i) => (
                    <div
                      key={i}
                      style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: 'var(--s3)',
                        padding: 'var(--s2) 0',
                        borderTop: i === 0 ? 'none' : '1px dashed var(--border)',
                      }}
                    >
                      <div style={{ flex: 1, fontSize: 13, minWidth: 0 }}>
                        <div style={{ fontWeight: 500, color: 'var(--ink)' }}>{it.title}</div>
                        <div style={{ color: 'var(--ink-soft)', fontSize: 12, marginTop: 2 }}>
                          {it.desc}
                        </div>
                      </div>
                      <div style={{ marginLeft: 'auto', flexShrink: 0 }}>
                        <Badge tone="danger">阻断</Badge>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--s2)',
                    color: 'var(--ok)',
                    fontSize: 13,
                  }}
                >
                  <svg
                    width="15"
                    height="15"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    aria-hidden="true"
                  >
                    <path d="M20 6 9 17l-5-5" />
                  </svg>
                  事实与输入已就绪，可直接生成
                </div>
              )}
            </div>

            {/* .gen-banner：产品级说明 */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--s2)',
                padding: 'var(--s2) var(--s3)',
                background: 'var(--info-wash)',
                border: '1px solid color-mix(in srgb, var(--info) 22%, transparent)',
                borderRadius: 'var(--r-md)',
                fontSize: 12,
                color: 'var(--ink-soft)',
                lineHeight: 1.5,
              }}
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                style={{ color: 'var(--info)', flexShrink: 0 }}
                aria-hidden="true"
              >
                <circle cx="12" cy="12" r="10" />
                <path d="M12 8v4M12 16h.01" />
              </svg>
              <div>
                <strong style={{ color: 'var(--ink)' }}>
                  系统会基于你已确认的事实与本岗位 JD 完成选材、表达与排版。
                </strong>
                生成中保留输入与状态；失败时返回修改不会丢失任何字段。
              </div>
            </div>

            {/* .gen-cta：precheck-ready + 主按钮 + 底部行 */}
            <div className="card" style={{ padding: 'var(--s4)' }}>
              {!blocked && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--s2)',
                    fontSize: 13,
                    color: 'var(--ok)',
                    marginBottom: 'var(--s3)',
                  }}
                >
                  <svg
                    width="15"
                    height="15"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    aria-hidden="true"
                  >
                    <path d="M20 6 9 17l-5-5" />
                  </svg>
                  事实与输入已就绪，可直接生成
                </div>
              )}
              <Button
                variant="primary"
                size="lg"
                onClick={() => void beginGenerate()}
                disabled={blocked}
                style={{ width: '100%' }}
              >
                生成岗位简历
              </Button>
              <div
                style={{
                  marginTop: 'var(--s3)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: 12,
                  color: 'var(--ink-soft)',
                }}
              >
                <span>生成中保留输入与状态</span>
                <Link
                  to="/profile"
                  style={{ color: 'var(--primary)', textDecoration: 'none', fontWeight: 500 }}
                >
                  查看我的经历
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // ================= 处理中 / 结果 / 失败视图 =================
  // 处理视图（DS-002 process-shell 视觉语法：左侧 4 阶段 radio 流程 + 右侧流式/明细/失败）
  if (!result) {
    const eyebrow = targetLabel
      ? `${targetLabel} · ${processingFailed ? '生成未完成' : '生成中'}`
      : processingFailed
        ? '生成未完成'
        : '生成中'
    const headerTitle = processingFailed
      ? '简历生成未完成，可恢复或返回修改'
      : '正在为你准备一份可直接投递的简历'
    const headerDesc = processingFailed
      ? '失败原因来自真实后端响应；可重新生成或返回修改，输入已保留。'
      : '系统按真实阶段推进；输入已保留，失败时不会被静默丢弃。'
    // 失败时强制定位到失败阶段（若可识别），否则定位到 selectedPhaseIdx
    const focusFailedIdx = failedPhaseIdx >= 0 ? failedPhaseIdx : selectedPhaseIdx
    const viewPhaseIdx = processingFailed ? focusFailedIdx : selectedPhaseIdx
    const safeViewIdx = viewPhaseIdx >= 0 && viewPhaseIdx < PROCESS_PHASES.length ? viewPhaseIdx : 0
    const viewPhase = PROCESS_PHASES[safeViewIdx]!
    const viewStatus = phaseStatuses[safeViewIdx] ?? 'pending'
    const totalElapsedMs = operation?.elapsed_ms ?? null
    return (
      <div
        className="page"
        style={{
          maxWidth: 1200,
          width: '100%',
          margin: '0 auto',
          alignItems: 'stretch',
        }}
      >
        <div className="process-shell">
          {/* —— 左：4 阶段 radio 流程 —— */}
          <div className="process-main">
            <div className="process-header">
              <div className="process-header__eyebrow">{eyebrow}</div>
              <h1 className="process-header__h1">{headerTitle}</h1>
              <p className="process-header__desc">{headerDesc}</p>
            </div>

            <div className="process-elapsed" aria-label="已用时">
              <span>已用时</span>
              <span className="process-elapsed__value">
                {totalElapsedMs != null ? fmtMs(totalElapsedMs) : '—'}
              </span>
            </div>

            <StageFlowList
              phases={PROCESS_PHASES}
              op={operation}
              selectedIdx={selectedPhaseIdx}
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
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: '50%',
                      background: 'currentColor',
                    }}
                  />
                  输入已保留
                </span>
                <span>进度会随服务端更新，可点击已开始阶段查看明细。</span>
              </div>
              <Button variant="ghost" size="sm" disabled={generating} onClick={backToEdit}>
                返回修改输入
              </Button>
            </div>
          </div>

          {/* —— 右：选中阶段的流式/明细 / 失败 —— */}
          <div className="process-side" aria-label="阶段明细">
            {processingFailed ? (
              <FailurePanel
                phase={viewPhase}
                phaseIdx={safeViewIdx}
                op={operation}
                genError={genError}
                generating={generating}
                onRegenerate={() => void beginGenerate()}
                onBackToEdit={backToEdit}
              />
            ) : (
              <PhaseStream
                phase={viewPhase}
                phaseIdx={safeViewIdx}
                status={viewStatus}
                operation={operation}
              />
            )}
          </div>
        </div>
      </div>
    )
  }

  // ================= 成功态 =================
  return (
    <div
      className="page"
      style={{
        maxWidth: 1120,
        width: '100%',
        margin: '0 auto',
        alignItems: 'stretch',
      }}
    >
      <div>
        <div
          className="muted"
          style={{
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            fontSize: 'var(--text-xs)',
            fontWeight: 600,
            color: 'var(--ink-faint)',
          }}
        >
          {targetLabel ? `${targetLabel} · 已生成` : '已生成'}
        </div>
        <h1
          style={{
            fontSize: 'var(--text-2xl)',
            fontWeight: 600,
            letterSpacing: '-0.01em',
            lineHeight: 1.25,
            marginTop: 'var(--s2)',
          }}
        >
          简历已生成，可直接下载
        </h1>
        <p className="muted" style={{ marginTop: 'var(--s2)' }}>
          以下为本份生成的真实产物与统计。
        </p>
      </div>

      {/* 本次结果摘要：warnings + 关键 kv（不杜撰任何字段） */}
      <Card title="本次结果" subtitle={result.file_name}>
        {result.warnings && result.warnings.length > 0 && (
          <div className="notice notice--warn" style={{ marginTop: 0 }}>
            {result.warnings.map((w, i) => (
              <div key={i}>• {w}</div>
            ))}
          </div>
        )}
        <div className="kv" style={{ marginTop: 'var(--s4)' }}>
          {typeof result.page_count === 'number' && (
            <div className="kv__row">
              <span className="kv__k">页数</span>
              <span className="kv__v">{result.page_count} 页</span>
            </div>
          )}
          <div className="kv__row">
            <span className="kv__k">匹配经历</span>
            <span className="kv__v">{result.matched_experience_ids.length} 条</span>
          </div>
          <div className="kv__row">
            <span className="kv__k">渲染经历</span>
            <span className="kv__v">{result.rendered_experience_ids.length} 条</span>
          </div>
          <div className="kv__row">
            <span className="kv__k">模板</span>
            <span className="kv__v">{result.template_id}</span>
          </div>
        </div>
      </Card>

      {/* 左：内容预览（真实文本）；右：sticky 下载/依据 侧栏 */}
      <div className="result-shell">
        <div className="result-shell__preview">
          <div className="preview-disclaimer">
            <Badge tone="neutral">内容预览</Badge>
            <span>
              文本来自本次生成结果；<strong>下载的 DOCX 为最终正式文件</strong>，预览不冒充 DOCX 像素。
            </span>
          </div>
          <div className="preview-scroll">
            <article className="paper-preview" aria-label="简历内容预览">
              {result.doc_preview && result.doc_preview.length > 0 ? (
                result.doc_preview.map((sec, sIdx) => (
                  <section
                    key={`${sec.section}-${sIdx}`}
                    className="paper-preview__section"
                  >
                    <h2 className="paper-preview__heading">{sec.title}</h2>
                    {sec.entries.map((ent, eIdx) => (
                      <div key={`${sIdx}-${eIdx}`} className="paper-preview__entry">
                        <div className="paper-preview__entry-head">
                          {ent.heading && (
                            <span className="paper-preview__entry-title">{ent.heading}</span>
                          )}
                          {ent.subhead && (
                            <span className="paper-preview__entry-sub">{ent.subhead}</span>
                          )}
                        </div>
                        {sec.section === 'skills' ? (
                          <div className="paper-preview__skill-line">
                            <strong>{ent.heading}</strong>
                            {ent.bullets.join('、')}
                          </div>
                        ) : ent.bullets.length > 0 ? (
                          <ul className="paper-preview__bullets">
                            {ent.bullets.map((b, bIdx) => {
                              const isSelected =
                                selectedBullet?.sectionIdx === sIdx &&
                                selectedBullet?.entryIdx === eIdx &&
                                selectedBullet?.bulletIdx === bIdx
                              return (
                                <li
                                  key={`${sIdx}-${eIdx}-${bIdx}`}
                                  className={
                                    'paper-preview__bullet' +
                                    (isSelected ? ' paper-preview__bullet--selected' : '')
                                  }
                                  onClick={() =>
                                    setSelectedBullet({
                                      sectionIdx: sIdx,
                                      entryIdx: eIdx,
                                      bulletIdx: bIdx,
                                    })
                                  }
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter' || e.key === ' ') {
                                      e.preventDefault()
                                      setSelectedBullet({
                                        sectionIdx: sIdx,
                                        entryIdx: eIdx,
                                        bulletIdx: bIdx,
                                      })
                                    }
                                  }}
                                  role="button"
                                  tabIndex={0}
                                  aria-pressed={isSelected}
                                >
                                  {b}
                                </li>
                              )
                            })}
                          </ul>
                        ) : null}
                      </div>
                    ))}
                  </section>
                ))
              ) : (
                <div
                  className="empty"
                  style={{ padding: 'var(--s6) var(--s4)' }}
                >
                  <div className="empty__title">本次响应未携带内容预览</div>
                  <div className="empty__desc">
                    可直接下载下方 DOCX；预览能力在升级到带 V2.1.0 T6 字段的后端后可用。
                  </div>
                </div>
              )}
            </article>
          </div>
        </div>

        <aside className="result-shell__aside" aria-label="依据 / 导出">
          <Card title="下载 DOCX">
            <div className="export-card">
              <div className="export-card__hint">
                文件名：<strong style={{ color: 'var(--ink)' }}>{result.file_name}</strong>
              </div>
              <a
                className="btn btn--primary btn--lg"
                href={result.download_url}
                download
              >
                下载 DOCX
              </a>
              <div className="export-card__hint">
                下载为浏览器原生行为，不通过中转。
              </div>
              <div className="hstack" style={{ marginTop: 0 }}>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void beginGenerate()}
                  disabled={generating}
                >
                  重新生成
                </Button>
                <Button variant="ghost" size="sm" onClick={backToEdit}>
                  返回修改输入
                </Button>
              </div>
              <div className="hstack" style={{ marginTop: 0 }}>
                <Badge tone="ok">已生成</Badge>
                <span className="op-id">#{result.operation_id.slice(0, 8)}</span>
              </div>
            </div>
          </Card>

          <Card
            title="逐条依据"
            subtitle="点击左侧 bullet 查看其真实事实"
          >
            <EvidencePanel
              result={result}
              selected={selectedBullet}
              docPreview={result.doc_preview ?? null}
            />
          </Card>
        </aside>
      </div>

      {/* 真实阶段明细（仅结果态展示，处理态已改为 process-side 阶段流） */}
      {operation && (
        <Card title="真实阶段明细" actions={<Badge tone={statusTone(operation.status)}>{statusLabel(operation.status)}</Badge>}>
          <OperationTimeline operation={operation} />
        </Card>
      )}
    </div>
  )
}
