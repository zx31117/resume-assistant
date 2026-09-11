import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react'
import { Link } from 'react-router-dom'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import PdfPreview from '../components/PdfPreview'
import StageFlowList, {
  calcPhaseStatus,
  phaseElapsedMs,
  type PhaseStatus,
  type StageFlowPhase,
} from '../components/StageFlowList'
import { Field, TextArea, TextInput } from '../components/ui/Field'
import { useServices } from '../services'
import { ApiError, newOperationId } from '../api/client'
import { useOperation, statusLabel, fmtMs } from '../hooks/useOperation'
import type {
  EvidenceFact,
  JDAnalysis,
  OperationDetail,
  PdfAnchor,
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

// H8 §20.6：4 个覆盖完整 operation 的用户阶段（P1–P4）。
// 内部技术 stage 必须归属于一个用户阶段，耗时与活动 live elapsed 来自后端 OperationProjection。
const PROCESS_PHASES: StageFlowPhase[] = [
  {
    key: 'job_understanding',
    label: '理解目标岗位',
    detail: '生成准备、就绪检查、唯一一次 JD 分析、履历读取',
    codes: ['migration_check', 'embedding_ready', 'jd_analysis', 'sql_readback'],
  },
  {
    key: 'fact_selection',
    label: '从你的履历中挑选相关事实',
    detail: 'Experience 选择与 Fact/证据选择',
    codes: ['select_experiences', 'select_evidence'],
  },
  {
    key: 'content_drafting',
    label: '生成并润色简历内容',
    detail: '基于已选事实的受约束改写',
    codes: ['content_generation'],
  },
  {
    key: 'artifact_build',
    label: '排版并生成 Word/PDF',
    detail: 'ResumeDocument 构建、DOCX 渲染/保存、Word→PDF 转换、响应发布',
    codes: ['resume_build', 'render', 'save_docx', 'response_assembly'],
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

/** V2.1.0 R16：依据面板 —— 点击 PDF 命中层的锚点后展示其真实 evidence。
 *  数据链路（真实、无编造）：
 *  - 锚点坐标/文本/fact_refs 来自后端 PreviewAnchor（PDF 成品内的真实位置）；
 *  - 事实原文来自 `result.evidence`（按 experience_id 聚合的真实 Fact 原文），
 *    前端把 anchor.fact_refs 的 fact_id 放进 evidence map 反查原文；
 *  - fail closed：锚点无 fact_refs / 原文缺失 / artifact 不匹配时，
 *    一律不猜测、不编造，只显示「无可用依据」的诚实状态。
 */
function EvidencePanel({
  result,
  selectedAnchor,
}: {
  result: ResumeDocxGenerateResponse
  selectedAnchor: PdfAnchor | null
}) {
  if (__H6_INJECT__ === 'basis') throw new Error('H6-inject:basis') // H6 test-only
  // fact_id → 原文（读 GeneratePage 现有 evidence 数据源，不改后端）
  const factIndex = useMemo(() => {
    const m = new Map<string, EvidenceFact>()
    for (const list of Object.values(result.evidence ?? {})) {
      for (const f of list ?? []) {
        if (f && f.fact_id) m.set(f.fact_id, f)
      }
    }
    return m
  }, [result])

  if (!selectedAnchor) {
    return (
      <div>
        <div className="evidence-panel__empty">未选中任何内容行。</div>
        <div className="evidence-panel__hint">
          点击左侧「PDF 成品预览」中的内容行即可查看其真实事实原文与采用情况；
          流水线未记录的采用原因不会被编造。
        </div>
      </div>
    )
  }

  const anchorText = selectedAnchor.text || ''
  const refs = (selectedAnchor.fact_refs ?? []).filter((x) => !!x)
  const contentId = selectedAnchor.content_item_id ?? null
  const facts: EvidenceFact[] = refs
    .map((fid) => factIndex.get(fid))
    .filter((f): f is EvidenceFact => !!f)
  const missingCount = refs.length - facts.length

  // 仅在 doc_preview 中按 experience_id 精确命中时才展示条目名称/时段，避免猜配。
  let entryHeading: string | null = null
  let entrySubhead: string | null = null
  let selectionReason: string | null = null
  if (contentId) {
    outer: for (const sec of result.doc_preview ?? []) {
      for (const ent of sec.entries) {
        if (ent.experience_id && ent.experience_id === contentId) {
          entryHeading = ent.heading || null
          entrySubhead = ent.subhead || null
          selectionReason = ent.selection_reason || null
          break outer
        }
      }
    }
  }

  return (
    <div>
      <div className="evidence-panel__meta">
        {entryHeading && (
          <div className="evidence-panel__meta-row">
            <strong>所在条目</strong>
            <span style={{ color: 'var(--ink)' }}>{entryHeading}</span>
          </div>
        )}
        {entrySubhead && (
          <div className="evidence-panel__meta-row">
            <strong>时段</strong>
            <span style={{ color: 'var(--ink)' }}>{entrySubhead}</span>
          </div>
        )}
        <div className="evidence-panel__meta-row">
          <strong>当前内容</strong>
          <span style={{ color: 'var(--ink)' }}>{anchorText || '—'}</span>
        </div>
      </div>

      {selectionReason && (
        <div className="evidence-panel__meta" style={{ marginTop: 'var(--s3)' }}>
          <div className="evidence-panel__meta-row">
            <strong>采用原因</strong>
            <span style={{ color: 'var(--ink)' }}>{selectionReason}</span>
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
        {refs.length === 0 ? (
          <>
            <div className="evidence-panel__empty">该内容行没有可回查的独立事实依据。</div>
            <div className="evidence-panel__hint">
              该行可能为技能/奖项等非独立事实行或走 SQL 回退生成；不虚构理由。
            </div>
          </>
        ) : facts.length > 0 ? (
          <>
            {facts.map((f) => (
              <div key={f.fact_id} className="evidence-panel__fact">
                <div className="evidence-panel__fact-text">{f.text || '（事实原文为空）'}</div>
                <div className="evidence-panel__fact-meta">
                  所属经历：{f.experience_id ?? '—'} · fact_id: {f.fact_id}
                  {f.reason ? ` · 采用：${f.reason}` : ''}
                </div>
              </div>
            ))}
            {missingCount > 0 && (
              <div className="evidence-panel__hint">
                另有 {missingCount} 条引用的 fact_id 未包含在本次响应 evidence 中，无法展示原文。
              </div>
            )}
          </>
        ) : (
          <>
            <div className="evidence-panel__empty">
              该内容行引用了事实，但本次响应未携带其原文（无可用依据）。
            </div>
            <div className="evidence-panel__hint">
              引用 fact_id：{refs.join('、')}。未在 evidence 中命中，不做猜测。
            </div>
          </>
        )}
      </div>
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
  /** H8 §20.7.3：查看阶段 ≠ 运行阶段时的当前运行提示（null=无需提示）。 */
  currentRunningHint?: string | null
  currentRunningIdx?: number
}

function PhaseStream({ phase, phaseIdx, status, operation, currentRunningHint, currentRunningIdx }: PhaseStreamProps) {
  const events = (operation?.stages ?? []).filter((e) => phase.codes.includes(e.stage_code))
  const elapsed = phaseElapsedMs(operation, phase.codes)
  const tag = status === 'failed' ? '阶段失败' : status === 'active' ? '正在执行' : '阶段明细'
  const isHistoryView =
    currentRunningHint != null && currentRunningIdx != null && currentRunningIdx !== phaseIdx
  return (
    <div className="ai-stream" aria-live="polite">
      <div className="ai-stream__head">
        <span className="ai-stream__tag">{isHistoryView ? '历史阶段' : tag}</span>
        <span className="ai-stream__title">
          {phaseIdx + 1}. {phase.label}
        </span>
        <span className="ai-stream__sub">{elapsed != null ? `本阶段用时 ${fmtMs(elapsed)}` : '本阶段用时 —'}</span>
      </div>
      {isHistoryView && currentRunningHint ? (
        <div style={{ fontSize: 12, margin: '4px 0 8px', color: 'var(--warn)' }}>
          {currentRunningHint}
        </div>
      ) : null}
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
  // V2.1.0 R16：当前选中的 PDF 内容行锚点（用于依据面板 + 命中层高亮）；新结果时清空
  const [selectedAnchor, setSelectedAnchor] = useState<PdfAnchor | null>(null)
  // V2.1.0 T12-R5：结果页右侧「依据 / 修改」标签（修改链路尚未接通，disabled 占位）。
  const [resultTab, setResultTab] = useState<'evidence' | 'modify'>('evidence')
  // V2.1.0 T12-R4：处理视图左侧 4 阶段 radio 当前选中（与「当前运行」解耦）。
  // - 规则：① 每次 op 轮询更新时，若「当前活动」高层阶段发生变化，自动切到新活动阶段；
  //        ② 用户主动点击已开始/已完成的阶段可回看，不被立即覆盖；
  //        ③ 离开处理视图或新一次生成时重置。
  const [selectedPhaseIdx, setSelectedPhaseIdx] = useState(0)
  const lastActiveIdxRef = useRef<number>(-1)
  // V2.1.0 T12-R11：导出卡 PDF 按钮状态（真实可恢复）；
  // - pdfMissing: 后端未返回 pdf_download_url（PDF 未生成/失败）；
  // - pdfError : 用户点击时探测到下载链不可达 / 浏览器拒绝。
  // 不进入布局推挤：使用卡内固定高区域表达。
  const [pdfMissing, setPdfMissing] = useState<boolean>(false)
  const [pdfError, setPdfError] = useState<string | null>(null)
  const runSeq = useRef(0)

  useEffect(() => {
    setSelectedAnchor(null)
    // T12-R11：进入成功态时按真实 pdf_download_url 初始化 PDF 可用状态（PDF 未生成→缺失提示）。
    setPdfMissing(!result?.pdf_download_url)
    setPdfError(null)
  }, [result])

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
        {/* 任务上下文 topbar：冻结原型 .gen-topbar（T12-R12：固定不随内容滚动） */}
        <div
          role="region"
          aria-label="当前任务上下文"
          className="gen-topbar"
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

        {/* 冻结原型 .gen-grid：minmax(0,1fr) 400px 左右两列；
            T12-R12：行高由 .page 剩余份额决定，列内各自滚动，卡片外框不随内容跳动 */}
        <div
          className="gen-grid"
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1fr) 400px',
            gap: 'var(--s4)',
            alignItems: 'stretch',
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
    // H8 §20.7.3：查看≠运行时给出「当前正在执行」提示（服务端 user_phases 实时值）
    const runningPhaseObj = currentRunningIdx >= 0 ? PROCESS_PHASES[currentRunningIdx] : null
    const runningUp = runningPhaseObj
      ? (operation?.user_phases ?? []).find((u) => u.key === runningPhaseObj.key)
      : null
    const currentRunningHint =
      runningUp && currentRunningIdx >= 0 && currentRunningIdx !== safeViewIdx
        ? `当前正在执行：${runningUp.code} ${runningUp.label} · ${fmtMs(runningUp.status === 'active' ? runningUp.live_elapsed_ms : runningUp.elapsed_ms)}`
        : null
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

            <div className="process-elapsed" aria-label="总用时">
              <span>总用时</span>
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
                currentRunningHint={currentRunningHint}
                currentRunningIdx={currentRunningIdx}
              />
            )}
          </div>
        </div>
      </div>
    )
  }

  // ================= 成功态 =================
  // V2.1.0 T12-R10/R11/R15b：结果页主从布局（DS-002 result-shell）。
  // - 左：真实 PDF 成品预览（内置 pdf.js viewer，读取与「下载 PDF」同一 pdf_download_url）；
  //   单一外层预览卡、满宽、仅卡内滚动；任何失败都不回退 HTML 近似预览。
  //   ResultPaperPreview（HTML 版式渲染）已从产品路径退出，不再被引用。
  // - 右：sticky 固定区 —— 顶部操作条 + 「依据/修改」标签 + 主体面板；
  // - 导出卡已收口为页面左下角固定独立卡（见 .result-export-card），只含两个真实按钮。
  //   "重新生成/返回修改"动作迁出导出卡，放在右侧栏顶部操作条，不参与导出卡外框。
  //   真实技术字段（warnings / page_count / matched/rendered/template kv）已下沉到开发者后台，
  //   普通结果页不再展示；anchor→fact 真实映射由 R16 EvidencePanel 保留。
  //   doc_preview JSON 仅保留为内容核对/无障碍依据来源，不再承担版式渲染。
  const wordHref = result.download_url
  const wordDownloadName = result.file_name || 'resume.docx'
  const pdfHref = result.pdf_download_url
  const pdfDownloadName = result.pdf_file_name || 'resume.pdf'
  // T12-R11：PDF 真实状态可恢复（pdfMissing/pdfError 由顶部 [result] effect 初始化，
  // 点击时探测下载链；HEAD 失败 → 卡内固定高区域显示具体错误并可重新生成）

  async function probePdfDownload(): Promise<boolean> {
    if (!pdfHref) {
      setPdfMissing(true)
      setPdfError(null)
      return false
    }
    try {
      // H7 R34：使用 GET + Range: bytes=0-0 进行可达性探测。
      // GET 总是被后端允许（@router.get 路径），既不会被路由为 405，又能拿到真实状态码；
      // Range 头让响应只返回第一字节，避免下载完整 PDF。206 / 200 都视为可达，404/5xx 视为不可达。
      const r = await fetch(pdfHref, {
        method: 'GET',
        headers: { Range: 'bytes=0-0', Accept: 'application/pdf' },
      })
      if (!r.ok && r.status !== 206) {
        setPdfError(`PDF 下载失败（HTTP ${r.status}）；请稍后重试或重新生成。`)
        return false
      }
      setPdfError(null)
      return true
    } catch (e) {
      setPdfError(e instanceof Error ? `PDF 不可达：${e.message}` : 'PDF 不可达。')
      return false
    }
  }

  function handlePdfClick(e: ReactMouseEvent<HTMLAnchorElement>) {
    // 同步探测 + 阻止无效下载（探测失败则让按钮保持可恢复的「重新生成」状态）
    if (!pdfHref) {
      e.preventDefault()
      setPdfMissing(true)
      return
    }
    void probePdfDownload()
  }

  const exportErrTone: 'warn' | 'danger' | null = pdfError
    ? 'danger'
    : pdfMissing
      ? 'warn'
      : null
  const exportErrText = pdfError
    ? pdfError
    : pdfMissing
      ? 'PDF 尚未生成或本次生成失败；重新生成后可下载。'
      : ''
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
      <div className="result-shell">
        {/* 左：真实 PDF 成品预览（单一外层卡、满宽、仅卡内滚动；不回退 HTML 近似） */}
        <div className="result-shell__preview">
          {pdfHref ? (
            <PdfPreview
              url={pdfHref}
              artifactId={result.pdf_artifact_id}
              anchors={result.pdf_anchors}
              selectedAnchor={selectedAnchor}
              onSelectAnchor={setSelectedAnchor}
              onBackToEdit={backToEdit}
            />
          ) : (
            <div className="pdf-preview pdf-preview--state" data-state="unavailable" role="status">
              <div className="pdf-preview__stateblock">
                <div className="pdf-preview__statetitle">PDF 成品未生成</div>
                <p className="pdf-preview__statesub">
                  本次生成未产出可预览的 PDF；不使用 HTML 近似替代预览。可下载 Word，或重新生成后重试。
                </p>
              </div>
            </div>
          )}
        </div>

        {/* 右：sticky 固定区 —— 顶部操作 + 依据/修改（顺序稳定） */}
        <aside className="result-shell__aside" aria-label="依据 / 修改 / 操作">
          <div className="result-aside-actions">
            <Button
              variant="ghost"
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

          <div className="result-tabs" role="tablist" aria-label="结果侧栏标签">
            <button
              type="button"
              role="tab"
              aria-selected={resultTab === 'evidence'}
              tabIndex={resultTab === 'evidence' ? 0 : -1}
              className={
                'result-tabs__tab' +
                (resultTab === 'evidence' ? ' result-tabs__tab--active' : '')
              }
              onClick={() => setResultTab('evidence')}
            >
              依据
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={resultTab === 'modify'}
              tabIndex={resultTab === 'modify' ? 0 : -1}
              className={
                'result-tabs__tab' +
                (resultTab === 'modify' ? ' result-tabs__tab--active' : '')
              }
              onClick={() => setResultTab('modify')}
              aria-label="修改（即将上线）"
            >
              <span>修改</span>
              <span className="result-tabs__soon" aria-hidden="true">
                即将上线
              </span>
            </button>
          </div>

          <Card
            className="result-aside-panel"
            title={resultTab === 'evidence' ? '逐条依据' : '意图级修改'}
            subtitle={
              resultTab === 'evidence'
                ? '点击左侧 PDF 预览中的内容行查看真实事实原文与采用情况。'
                : '描述你希望调整的方向；真实链路尚未接通，仅展示占位。'
            }
          >
            {resultTab === 'evidence' ? (
              <EvidencePanel result={result} selectedAnchor={selectedAnchor} />
            ) : (
              <div className="modify-placeholder" role="region" aria-label="修改占位（即将上线）">
                <div className="modify-placeholder__head">
                  <Badge tone="neutral">即将上线</Badge>
                  <span className="muted modify-placeholder__hint">
                    例如：更突出项目 / 更技术 / 更简洁 / 强调某项真实成果。
                  </span>
                </div>
                <textarea
                  className="intent-input"
                  rows={3}
                  placeholder="描述你希望调整的方向"
                  disabled
                  aria-label="修改意图（即将上线，暂不可用）"
                />
                <div className="intent-row">
                  <Button variant="secondary" size="sm" disabled>
                    更突出项目
                  </Button>
                  <Button variant="secondary" size="sm" disabled>
                    更技术
                  </Button>
                  <Button variant="secondary" size="sm" disabled>
                    更简洁
                  </Button>
                  <Button variant="secondary" size="sm" disabled>
                    强调真实成果
                  </Button>
                </div>
                <div className="modify-placeholder__scope">
                  <strong style={{ color: 'var(--ink)' }}>当前简历作用范围</strong>
                  <p className="muted">
                    仅修改此份简历；不会改动「我的经历」或长期事实。修订历史与回退为后续版本功能。
                  </p>
                </div>
              </div>
            )}
          </Card>
        </aside>
      </div>

      {/* 左下角固定独立导出卡：只保留「下载 Word / 下载 PDF」两个真实按钮。
          外框尺寸不随文件名/状态/错误文案变化；错误/缺失走卡内固定高区域。 */}
      {(() => { if (__H6_INJECT__ === 'export') throw new Error('H6-inject:export'); return null })() /* H6 test-only */}
      <aside className="result-export-card" aria-label="导出">
        <div className="result-export-card__buttons">
          <a
            className="btn btn--primary btn--md"
            href={wordHref}
            download={wordDownloadName}
            data-role="download-word"
          >
            下载 Word
          </a>
          {pdfHref ? (
            <a
              className="btn btn--secondary btn--md"
              href={pdfHref}
              download={pdfDownloadName}
              onClick={handlePdfClick}
              data-role="download-pdf"
            >
              下载 PDF
            </a>
          ) : (
            <button
              type="button"
              className="btn btn--secondary btn--md"
              disabled
              data-role="download-pdf"
              aria-label="下载 PDF（暂不可用）"
            >
              下载 PDF
            </button>
          )}
        </div>
        <div
          className="result-export-card__err"
          data-tone={exportErrTone ?? ''}
          role={exportErrTone ? 'status' : undefined}
          aria-live="polite"
        >
          {exportErrText || ' '}
        </div>
      </aside>
    </div>
  )
}
