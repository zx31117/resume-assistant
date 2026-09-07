import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import PageHeader from '../components/PageHeader'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import OperationTimeline from '../components/OperationTimeline'
import { Field, Select, TextArea, TextInput } from '../components/ui/Field'
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
  TemplateInfo,
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

interface ProcessPhase {
  key: string
  label: string
  detail: string
  /** 点亮该阶段所需的后端真实 stage_code（全部出现 COMPLETED 事件才算完成）。 */
  codes: string[]
}

const PROCESS_PHASES: ProcessPhase[] = [
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

type PhaseStatus = 'pending' | 'active' | 'done' | 'failed'

/** 依据真实 operation 事件计算某一用户阶段的点亮状态。 */
function phaseStatus(op: OperationDetail | null, codes: string[]): PhaseStatus {
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

/** 单条摘要 chips 区块（JDAnalysis 真实字段驱动）。 */
function AnalysisChips({ a }: { a: JDAnalysis }) {
  const rows: Array<{ label: string; values: string[]; strong?: boolean }> = []
  if (a.position) rows.push({ label: '目标岗位', values: [a.position], strong: true })
  if (a.required_skills.length) rows.push({ label: '核心要求', values: a.required_skills })
  if (a.preferred_skills.length) rows.push({ label: '加分项', values: a.preferred_skills })
  if (a.experience_preferences.length) rows.push({ label: '经验偏好', values: a.experience_preferences })
  if (a.keywords.length) rows.push({ label: '关键词', values: a.keywords })
  if (a.industry) rows.push({ label: '行业', values: [a.industry] })
  return (
    <div className="stack" style={{ gap: 'var(--s3)', marginTop: 'var(--s4)' }}>
      {rows.map((r) => (
        <div className="jd-field" key={r.label}>
          <span className="jd-field__label">{r.label}</span>
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 'var(--s2)',
              fontWeight: r.strong ? 600 : undefined,
            }}
          >
            {r.values.map((v, i) => (
              <span
                className="tag"
                key={`${r.label}-${i}`}
                style={r.strong ? { background: 'var(--tint)', color: 'var(--primary)' } : undefined}
              >
                {v}
              </span>
            ))}
          </div>
        </div>
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

/** 4 个用户语言阶段的可视列表（由真实阶段事件点亮）。 */
function ProcessStages({ op }: { op: OperationDetail | null }) {
  const tailOf: Record<PhaseStatus, string> = { done: '已完成', active: '进行中', pending: '等待', failed: '失败' }
  const indicatorOf: Record<PhaseStatus, { bg: string; color: string; content: string }> = {
    done: { bg: 'var(--primary)', color: '#fff', content: '✓' },
    active: { bg: 'var(--tint)', color: 'var(--primary)', content: '…' },
    pending: { bg: 'var(--surface-2)', color: 'var(--ink-faint)', content: '' },
    failed: { bg: 'var(--danger-wash)', color: 'var(--danger)', content: '!' },
  }
  return (
    <ol style={{ listStyle: 'none', display: 'flex', flexDirection: 'column' }}>
      {PROCESS_PHASES.map((p, i) => {
        const st = phaseStatus(op, p.codes)
        const ind = indicatorOf[st]
        return (
          <li
            key={p.key}
            style={{
              display: 'flex',
              gap: 'var(--s4)',
              alignItems: 'center',
              padding: 'var(--s4) var(--s5)',
              ...(i > 0 ? { borderTop: '1px solid var(--line)' } : {}),
            }}
          >
            <span
              style={{
                width: 30,
                height: 30,
                borderRadius: '50%',
                flexShrink: 0,
                display: 'grid',
                placeItems: 'center',
                fontWeight: 600,
                fontSize: 'var(--text-sm)',
                background: ind.bg,
                color: ind.color,
              }}
              aria-hidden="true"
            >
              {ind.content || i + 1}
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontWeight: st === 'active' ? 600 : 500,
                  color: st === 'failed' ? 'var(--danger)' : 'var(--ink)',
                }}
              >
                {p.label}
              </div>
              <div className="muted">{p.detail}</div>
            </div>
            <span
              className="muted"
              style={{
                flexShrink: 0,
                color: st === 'active' ? 'var(--primary)' : st === 'failed' ? 'var(--danger)' : undefined,
                fontWeight: st === 'active' ? 600 : undefined,
              }}
            >
              {tailOf[st]}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

export default function GeneratePage() {
  const services = useServices()

  // —— 元信息：模板 / 系统状态 ——
  const [templates, setTemplates] = useState<TemplateInfo[]>([])
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

  // 生成期间轮询该 op 的真实阶段（约 1s，页面不可见时 3s）；离开处理视图即停止。
  const polled = useOperation(opId, view === 'processing' && opId != null && !result)
  // 仅接受与当前 op 匹配的快照，避免「重新生成」后旧快照短暂串场
  const operation = polled && polled.operation_id === opId ? polled : null

  useEffect(() => {
    jdRef.current = jd
  }, [jd])

  // —— 元信息加载 ——
  const loadMeta = useCallback(async () => {
    try {
      const [tpl, st] = await Promise.all([services.template.list(), services.system.status()])
      setTemplates(tpl.templates)
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
    const list: Array<{ text: string }> = []
    if (!identity.name.trim()) list.push({ text: '姓名未填写，简历无法署名。请先补全身份信息。' })
    if (experienceCount === 0) list.push({ text: '暂无可用经历，没有可挑选的事实。请先在「我的经历」录入内容。' })
    if (jdTooShort) {
      list.push({ text: `JD 过短（当前 ${jdTrimmed.length} 字，至少需要 ${JD_MIN_CHARS} 字）。` })
    }
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

  const name = identity.name.trim()
  const targetLabel = shownAnalysis?.position ?? ''
  const processingFailed = genError != null || (operation != null && ['FAILED', 'TIMED_OUT', 'INTERRUPTED'].includes(operation.status))
  const jdSnippet = jdTrimmed.length > 60 ? `${jdTrimmed.slice(0, 60)}…` : jdTrimmed

  const setIdentityField = (k: keyof Identity) => (v: string) =>
    setIdentity((p) => ({ ...p, [k]: v }))

  // ================= 输入视图 =================
  if (view === 'input') {
    return (
      <div className="page">
        <PageHeader
          title="生成简历"
          description="根据「我的经历」中已确认的事实与目标 JD，生成一份可直接投递的 DOCX。身份输入仅用于本次请求，不会写入经历。"
          actions={
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--s2)', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
              {metaError ? (
                <Badge tone="warn">状态读取失败</Badge>
              ) : factCount != null ? (
                <Badge tone="ok">{factCount} 条事实已就绪</Badge>
              ) : (
                <Badge tone="neutral">读取状态中…</Badge>
              )}
              <Link className="btn btn--secondary btn--sm" to="/profile">
                查看我的经历
              </Link>
            </span>
          }
        />

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--s6)', alignItems: 'flex-start' }}>
          {/* —— 左列：身份摘要 + 目标岗位与 JD —— */}
          <div
            style={{
              flex: '1 1 440px',
              minWidth: 0,
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--s5)',
            }}
          >
            <Card
              title="身份摘要"
              subtitle="以下信息仅用于本次生成，不写入「我的经历」；姓名为必填。"
              actions={
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--s2)', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                  <Badge tone="neutral">本次生成使用</Badge>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setEditingIdentity((v) => !v)}
                    disabled={generating}
                  >
                    {editingIdentity ? '收起' : '编辑'}
                  </Button>
                </span>
              }
            >
              {editingIdentity ? (
                <div className="stack">
                  <div className="form-grid">
                    <Field label="姓名（必填）" hint="用于简历署名。">
                      <TextInput
                        value={identity.name}
                        onChange={(e) => setIdentityField('name')(e.target.value)}
                        placeholder="张三"
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
                  <div className="hstack" style={{ marginTop: 'var(--s2)' }}>
                    <Button variant="secondary" size="sm" onClick={() => setEditingIdentity(false)}>
                      完成
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="hstack" style={{ marginTop: 0, gap: 'var(--s2)' }}>
                  <span style={identity.name.trim() ? undefined : { color: 'var(--error)', fontWeight: 600 }}>
                    {identity.name.trim() || '—'}
                  </span>
                  {!identity.name.trim() && <span style={{ color: 'var(--error)', fontWeight: 600 }}>姓名未填写</span>}
                  <span className="muted">·</span>
                  <span>{identity.phone.trim() || '—'}</span>
                  <span className="muted">·</span>
                  <span>{identity.email.trim() || '—'}</span>
                  <span className="muted">·</span>
                  <span>{identity.location.trim() || '—'}</span>
                </div>
              )}
            </Card>

            <Card
              title="目标岗位与 JD"
              subtitle="粘贴完整岗位描述；文本达到 60 字后会自动分析一次，右侧展示解析摘要。"
            >
              <TextArea
                value={jd}
                onChange={(e) => setJd(e.target.value)}
                placeholder="将招聘 JD 完整粘贴于此…"
                style={{ minHeight: 200 }}
              />
              <div className="hstack" style={{ marginTop: 'var(--s3)', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="muted">
                  {jdTrimmed.length} 字{jdTooShort ? `（不足 ${JD_MIN_CHARS} 字，暂不分析）` : ''}
                </span>
                <div className="hstack" style={{ marginTop: 0, gap: 'var(--s2)' }}>
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
                <div className="notice notice--warn">JD 已修改，将自动重新分析（约 {JD_ANALYZE_DEBOUNCE_MS / 1000}s 内触发）。</div>
              )}
              {shownAnalysis && <AnalysisChips a={shownAnalysis} />}
            </Card>
          </div>

          {/* —— 右列：生成前检查 + 生成 CTA —— */}
          <div
            style={{
              flex: '0 1 340px',
              width: 340,
              maxWidth: '100%',
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--s4)',
            }}
          >
            <Card title="生成前检查">
              {blocked ? (
                <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
                  {issues.map((it, i) => (
                    <li key={i} style={{ display: 'flex', gap: 'var(--s3)', color: 'var(--error)', fontSize: 'var(--text-sm)', lineHeight: 1.5 }}>
                      <span aria-hidden="true">•</span>
                      <span>{it.text}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="notice notice--ok" style={{ marginTop: 0 }}>
                  事实与输入已就绪，可直接生成。
                </div>
              )}
            </Card>

            <div
              style={{
                padding: 'var(--s4) var(--s5)',
                borderRadius: 'var(--r-lg)',
                background: 'var(--surface-2)',
                fontSize: 'var(--text-sm)',
                color: 'var(--ink-soft)',
                lineHeight: 1.6,
              }}
            >
              系统会基于你已确认的事实与本岗位 JD 完成选材、表达与排版。生成中保留输入与状态；失败时返回修改不会丢失任何字段。
            </div>

            <Card
              title="生成"
              actions={<Badge tone="neutral">{templates.length ? `${templates.length} 个模板` : '…'}</Badge>}
            >
              <Field label="模板">
                <Select value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
                  {templates.length === 0 && <option value="">加载模板中…</option>}
                  {templates.map((t) => (
                    <option key={t.template_id} value={t.template_id}>
                      {t.display_name}
                    </option>
                  ))}
                </Select>
              </Field>
              {metaError && <div className="notice notice--warn">模板 / 状态读取失败：{metaError}</div>}
              {blocked && (
                <div className="muted" style={{ marginTop: 'var(--s3)' }}>
                  请先处理上方 {issues.length} 项问题后即可生成。
                </div>
              )}
              <Button
                variant="primary"
                size="lg"
                onClick={() => void beginGenerate()}
                disabled={blocked}
                style={{ width: '100%', marginTop: 'var(--s4)' }}
              >
                生成岗位简历
              </Button>
              <div className="muted" style={{ marginTop: 'var(--s3)' }}>
                生成中保留输入与状态；全程由真实服务端阶段驱动。
              </div>
            </Card>
          </div>
        </div>
      </div>
    )
  }

  // ================= 处理中 / 结果 / 失败视图 =================
  return (
    <div
      className="page"
      style={{
        maxWidth: result ? 1120 : 900,
        width: '100%',
        margin: '0 auto',
        alignItems: 'stretch',
      }}
    >
      <div>
        {targetLabel && (
          <div className="muted" style={{ textTransform: 'uppercase', letterSpacing: '0.06em', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--ink-faint)' }}>
            {targetLabel} · {result ? '已生成' : '生成中'}
          </div>
        )}
        <h1
          style={{
            fontSize: 'var(--text-2xl)',
            fontWeight: 600,
            letterSpacing: '-0.01em',
            lineHeight: 1.25,
            marginTop: 'var(--s2)',
          }}
        >
          {result ? '简历已生成，可直接下载' : '正在为你准备一份可直接投递的简历'}
        </h1>
        <p className="muted" style={{ marginTop: 'var(--s2)' }}>
          {result
            ? '以下为本份生成的真实产物与统计。'
            : '系统按真实阶段推进；输入已保留，失败时不会被静默丢弃。'}
        </p>
      </div>

      {/* 已提交输入 · 保留中 */}
      <Card>
        <div style={{ fontSize: 'var(--text-xs)', letterSpacing: '0.06em', textTransform: 'uppercase', fontWeight: 600, color: 'var(--ink-faint)' }}>
          已提交输入 · 保留中
        </div>
        <div style={{ marginTop: 'var(--s3)', fontSize: 'var(--text-base)', lineHeight: 1.7, color: 'var(--ink-soft)' }}>
          <div>
            姓名：<strong style={{ color: 'var(--ink)' }}>{name || '未填写'}</strong>
            {targetLabel && (
              <>
                <span style={{ margin: '0 var(--s2)' }}>·</span>
                目标岗位：<strong style={{ color: 'var(--ink)' }}>{targetLabel}</strong>
              </>
            )}
          </div>
          {jdSnippet && <div className="muted" style={{ marginTop: 'var(--s1)' }}>JD：{jdSnippet}</div>}
        </div>
      </Card>

      {/* 进度顶栏：已用时 + 真实状态 */}
      {!result && (
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 'var(--s3)', justifyContent: 'space-between' }}>
          <span className="muted">已用时</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--s3)' }}>
            {operation ? (
              <>
                <Badge tone={statusTone(operation.status)}>{statusLabel(operation.status)}</Badge>
                {operation.stage_name && <Badge tone="accent">{operation.stage_name}</Badge>}
              </>
            ) : (
              <Badge tone="neutral">提交中…</Badge>
            )}
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-lg)', fontWeight: 600, minWidth: '6ch', textAlign: 'right' }}>
              {operation ? fmtMs(operation.elapsed_ms) : '—'}
            </span>
          </span>
        </div>
      )}

      {/* 失败态 */}
      {processingFailed && !result && (
        <div className="notice notice--danger" style={{ marginTop: 0 }}>
          <div style={{ fontWeight: 600 }}>生成未完成：{genError?.message ?? (operation ? `${statusLabel(operation.status)}，见下方阶段明细。` : '发生未知错误。')}</div>
          {(genError?.stage || genError?.code) && (
            <div className="muted" style={{ marginTop: 'var(--s2)' }}>
              后端返回：stage={genError?.stage ?? '—'} code={genError?.code ?? '—'}
            </div>
          )}
          {operation && ['FAILED', 'TIMED_OUT', 'INTERRUPTED'].includes(operation.status) && (
            <div className="muted" style={{ marginTop: 'var(--s1)' }}>
              操作 {operation.operation_id.slice(0, 8)} {statusLabel(operation.status)}
              {operation.diagnostic_code ? ` · 诊断码 ${operation.diagnostic_code}` : ''}
              {operation.attempt > 1 || operation.max_attempts > 1
                ? ` · 尝试 ${operation.attempt}/${operation.max_attempts}`
                : ''}
            </div>
          )}
          <div className="hstack" style={{ marginTop: 'var(--s3)' }}>
            <Button variant="primary" size="sm" disabled={generating} onClick={() => void beginGenerate()}>
              重新生成
            </Button>
            <Button variant="secondary" size="sm" disabled={generating} onClick={backToEdit}>
              返回修改
            </Button>
          </div>
          <div className="muted" style={{ marginTop: 'var(--s2)' }}>
            输入已保留，返回修改不会丢失任何字段。
          </div>
        </div>
      )}

      {/* 运行中 / 阶段列表 */}
      {!result && !processingFailed && (
        <Card
          title="生成阶段"
          subtitle="以下 4 步由服务端真实阶段事件驱动点亮，未确认的阶段保持等待。"
        >
          <ProcessStages op={operation} />
          <div
            className="hstack"
            style={{ marginTop: 'var(--s4)', justifyContent: 'space-between', alignItems: 'center', gap: 'var(--s3)' }}
          >
            <span className="muted">进度会随服务端更新，可随时查看。</span>
            <Button variant="ghost" size="sm" disabled={generating} onClick={backToEdit}>
              返回修改输入
            </Button>
          </div>
        </Card>
      )}

      {/* 成功态 */}
      {result && (
        <>
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
        </>
      )}

      {/* 真实阶段明细（operation 轮询事件） */}
      {operation && (
        <Card title="真实阶段明细" actions={<Badge tone={statusTone(operation.status)}>{statusLabel(operation.status)}</Badge>}>
          <OperationTimeline operation={operation} />
        </Card>
      )}
    </div>
  )
}
