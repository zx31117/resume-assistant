import { useCallback, useEffect, useMemo, useState } from 'react'
import PageHeader from '../components/PageHeader'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import OperationTimeline from '../components/OperationTimeline'
import { Field, Select, TextArea, TextInput } from '../components/ui/Field'
import { jdApi, resumeApi, systemApi, templateApi } from '../api/endpoints'
import { ApiError, newOperationId } from '../api/client'
import { useOperation, statusLabel, statusTone, fmtMs } from '../hooks/useOperation'
import type {
  JDAnalysis,
  ResumeDocxGenerateResponse,
  SystemStatus,
  TemplateInfo,
} from '../api/types'

function chips(label: string, values: string[]) {
  if (!values || values.length === 0) return null
  return (
    <div className="jd-field">
      <span className="jd-field__label">{label}</span>
      <div className="exp-item__tags">
        {values.map((v, i) => (
          <span className="tag" key={`${v}-${i}`}>
            {v}
          </span>
        ))}
      </div>
    </div>
  )
}

function AnalysisView({ a }: { a: JDAnalysis }) {
  return (
    <div className="stack">
      <div className="form-grid">
        <Field label="岗位">
          <div className="readonly">{a.position || '（未识别）'}</div>
        </Field>
        <Field label="行业">
          <div className="readonly">{a.industry || '（未识别）'}</div>
        </Field>
      </div>
      {chips('必需技能', a.required_skills)}
      {chips('加分技能', a.preferred_skills)}
      {chips('关键词', a.keywords)}
      {chips('经验偏好', a.experience_preferences)}
      {a.responsibilities && a.responsibilities.length > 0 && (
        <div className="jd-field">
          <span className="jd-field__label">主要职责</span>
          <ul className="next-steps">
            {a.responsibilities.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export default function GeneratePage() {
  const [templates, setTemplates] = useState<TemplateInfo[]>([])
  const [templateId, setTemplateId] = useState('')
  const [status, setStatus] = useState<SystemStatus | null>(null)

  const [profile, setProfile] = useState({
    name: '',
    phone: '',
    email: '',
    location: '',
    target_position: '',
  })
  const [jd, setJd] = useState('')

  const [analyzing, setAnalyzing] = useState(false)
  const [analysis, setAnalysis] = useState<JDAnalysis | null>(null)
  const [analysisError, setAnalysisError] = useState<string | null>(null)

  const [generating, setGenerating] = useState(false)
  const [opId, setOpId] = useState<string | null>(null)
  const [result, setResult] = useState<ResumeDocxGenerateResponse | null>(null)
  const [generateError, setGenerateError] = useState<string | null>(null)

  // V2.0.1：短轮询当前生成操作的实时阶段（仅生成期间有效）
  const operation = useOperation(opId, generating)

  const loadMeta = useCallback(async () => {
    try {
      const [tpl, st] = await Promise.all([templateApi.list(), systemApi.status()])
      setTemplates(tpl.templates)
      const def = tpl.templates.find((t) => t.is_default) ?? tpl.templates[0]
      setTemplateId((cur) => cur || def?.template_id || '')
      setStatus(st)
    } catch (e) {
      setGenerateError(e instanceof ApiError ? e.message : String(e))
    }
  }, [])

  useEffect(() => {
    loadMeta()
  }, [loadMeta])

  const ready = status?.ready ?? false

  const canGenerate = useMemo(
    () => profile.name.trim().length > 0 && jd.trim().length > 0 && ready && !generating,
    [profile.name, jd, ready, generating],
  )

  const set = (k: keyof typeof profile) => (v: string) =>
    setProfile((p) => ({ ...p, [k]: v }))

  async function runAnalyze() {
    if (!jd.trim()) return
    setAnalyzing(true)
    setAnalysisError(null)
    setAnalysis(null)
    try {
      const res = await jdApi.analyze({ jd_text: jd })
      setAnalysis(res)
    } catch (e) {
      setAnalysisError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setAnalyzing(false)
    }
  }

  async function runGenerate() {
    if (!canGenerate) return
    const id = newOperationId()
    setOpId(id)
    setGenerating(true)
    setGenerateError(null)
    setResult(null)
    try {
      const res = await resumeApi.generateDocx(
        {
          jd_text: jd,
          template_id: templateId || undefined,
          profile: {
            name: profile.name.trim(),
            phone: profile.phone.trim(),
            email: profile.email.trim(),
            location: profile.location.trim() || null,
            target_position: profile.target_position.trim(),
          },
        },
        id,
      )
      setResult(res)
    } catch (e) {
      setGenerateError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="page">
      <PageHeader
        title="生成工作台"
        description="输入身份信息与目标 JD，分析岗位需求、选择模板并生成 DOCX。生成链路复用 V1.5.0 已验收的两层选材与受约束改写。"
        actions={
          ready ? (
            <Badge tone="ok">索引就绪</Badge>
          ) : (
            <Badge tone="warn">索引未就绪</Badge>
          )
        }
      />

      <Card title="本次身份信息" subtitle="以下信息仅用于本次生成，不写入 Experience。姓名必填，目标岗位缺失时用 JD 分析结果兜底。">
        <div className="form-grid">
          <Field label="姓名（必填）">
            <TextInput value={profile.name} onChange={(e) => set('name')(e.target.value)} placeholder="张三" />
          </Field>
          <Field label="目标岗位">
            <TextInput value={profile.target_position} onChange={(e) => set('target_position')(e.target.value)} placeholder="后端工程师" />
          </Field>
          <Field label="电话">
            <TextInput value={profile.phone} onChange={(e) => set('phone')(e.target.value)} placeholder="13800000000" />
          </Field>
          <Field label="邮箱">
            <TextInput type="email" value={profile.email} onChange={(e) => set('email')(e.target.value)} placeholder="you@example.com" />
          </Field>
          <Field label="所在地">
            <TextInput value={profile.location} onChange={(e) => set('location')(e.target.value)} placeholder="北京" />
          </Field>
        </div>
      </Card>

      <Card title="目标 JD" subtitle="粘贴职位描述；可先分析出结构化需求再生成。">
        <TextArea
          value={jd}
          onChange={(e) => setJd(e.target.value)}
          placeholder="粘贴职位描述（JD）全文…"
        />
        <div className="hstack">
          <Button variant="secondary" onClick={runAnalyze} disabled={!jd.trim() || analyzing}>
            {analyzing ? '分析中…' : '分析 JD'}
          </Button>
        </div>
        {analysisError && <div className="notice notice--danger">{analysisError}</div>}
        {analysis && (
          <div style={{ marginTop: 'var(--s4)' }}>
            <h3 className="section-label">JD 结构化结果</h3>
            <AnalysisView a={analysis} />
          </div>
        )}
      </Card>

      <Card title="模板选择" subtitle="从系统内置模板中选择生成目标。" actions={<Badge tone="neutral">{templates.length} 个模板</Badge>}>
        <Select value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
          {templates.map((t) => (
            <option key={t.template_id} value={t.template_id}>
              {t.display_name}（{t.sections.join(' / ')}）
            </option>
          ))}
        </Select>
      </Card>

      <Card title="生成" subtitle="提交后按提交中、生成中、成功或失败展示；失败后由你明确重试，不会自动重复调用。">
        {!ready && status && (
          <div className="notice notice--warn">
            索引未就绪，生成被阻断。请前往「本地系统」页执行初始化 / 迁移 / 重建索引，完成后再回来生成。
          </div>
        )}

        {generateError && <div className="notice notice--danger">{generateError}</div>}

        {(generating || (generateError != null && operation != null)) && (
          <div className="stack" style={{ marginTop: 'var(--s4)' }}>
            <div className="hstack" style={{ marginTop: 0 }}>
              {operation ? (
                <>
                  <Badge tone={statusTone(operation.status)}>{statusLabel(operation.status)}</Badge>
                  {operation.stage_name && <Badge tone="accent">{operation.stage_name}</Badge>}
                  <span className="muted">已用时 {fmtMs(operation.elapsed_ms)}</span>
                  <span className="op-id">#{operation.operation_id.slice(0, 8)}</span>
                </>
              ) : (
                <Badge tone="neutral">提交中…</Badge>
              )}
            </div>
            {operation && <OperationTimeline operation={operation} />}
          </div>
        )}

        {result && (
          <div className="stack" style={{ marginTop: 'var(--s4)' }}>
            <div className="kv">
              <div className="kv__row">
                <span className="kv__k">文件名</span>
                <span className="kv__v">{result.file_name}</span>
              </div>
              <div className="kv__row">
                <span className="kv__k">模板</span>
                <span className="kv__v">{result.template_id}</span>
              </div>
              {typeof result.page_count === 'number' && (
                <div className="kv__row">
                  <span className="kv__k">页数</span>
                  <span className="kv__v">{result.page_count}</span>
                </div>
              )}
              <div className="kv__row">
                <span className="kv__k">匹配经历</span>
                <span className="kv__v">{result.matched_experience_ids.length} 条</span>
              </div>
            </div>

            {result.warnings && result.warnings.length > 0 && (
              <div className="notice notice--warn">
                {result.warnings.map((w, i) => (
                  <div key={i}>• {w}</div>
                ))}
              </div>
            )}

            <div className="hstack">
              <a className="btn btn--primary" href={result.download_url} download>
                下载 DOCX
              </a>
            </div>
          </div>
        )}

        <div className="hstack">
          <Button onClick={runGenerate} disabled={!canGenerate}>
            {generating ? '生成中…' : '生成 DOCX'}
          </Button>
        </div>
      </Card>
    </div>
  )
}