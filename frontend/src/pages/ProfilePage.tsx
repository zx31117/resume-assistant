import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import PageHeader from '../components/PageHeader'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { Field, Select, TextArea, TextInput } from '../components/ui/Field'
import OperationTimeline from '../components/OperationTimeline'
import { experienceApi, resumeApi } from '../api/endpoints'
import { ApiError, newOperationId } from '../api/client'
import { useOperation, statusLabel, statusTone, fmtMs } from '../hooks/useOperation'
import type { ExperienceItem, ExperienceOut, OperationDetail, ExtractExperienceItem } from '../api/types'

const EXPERIENCE_TYPES: { value: string; label: string }[] = [
  { value: 'work', label: '工作' },
  { value: 'project', label: '项目' },
  { value: 'education', label: '教育' },
]

// V2.1.0 DS-002：筛选 tab 只映射后端真实 type 值域（''=全部，tab value 直接匹配 type 字符串）。
const FILTER_TABS: { value: string; label: string }[] = [
  { value: '', label: '全部' },
  ...EXPERIENCE_TYPES,
]

// V2.1.0 DS-002：列表区布局样式（tab + 搜索的工具条、区域内滚动的单列主列表）。
// 页面最外层继续走 .page/.page-head/.card 体系；新增的容器以行内样式自绘，不改动 global.css。
const masterStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  minWidth: 0,
  minHeight: 0,
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

const toolbarStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 'var(--s4)',
  flexWrap: 'wrap',
  marginBottom: 'var(--s4)',
}

const tabsStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 'var(--s2)',
  flexWrap: 'wrap',
}

const toolbarEndStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 'var(--s3)',
  flexWrap: 'wrap',
}

const tabBaseStyle: CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  height: 30,
  padding: '0 12px',
  borderRadius: 999,
  border: '1px solid transparent',
  background: 'transparent',
  color: 'var(--ink-soft)',
  fontSize: 'var(--text-sm)',
  fontWeight: 500,
  fontFamily: 'inherit',
  lineHeight: 1,
  cursor: 'pointer',
  whiteSpace: 'nowrap',
  transition:
    'background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease',
}

// DS-002 被选态：--tint 底 + --primary 文字
const tabActiveStyle: CSSProperties = {
  background: 'var(--tint)',
  color: 'var(--primary)',
  fontWeight: 600,
}

const tabCountStyle: CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  opacity: 0.8,
  fontVariantNumeric: 'tabular-nums',
}

// 列表区内区域滚动（页面顶栏固定，长列表不撑破工作台）
const listScrollStyle: CSSProperties = {
  maxHeight: 'max(360px, calc(100vh - 348px))',
  overflowY: 'auto',
  overflowX: 'hidden',
  paddingRight: 'var(--s1)',
}

function typeLabel(type: string): string {
  return EXPERIENCE_TYPES.find((t) => t.value === type)?.label ?? (type || '未分类')
}

function summaryMeta(status?: string): { label: string; tone: 'neutral' | 'ok' | 'warn' | 'danger' } {
  switch (status) {
    case 'empty':
      return { label: '无事实', tone: 'neutral' }
    case 'ready':
      return { label: '索引可用', tone: 'ok' }
    case 'failed':
      return { label: '处理失败', tone: 'danger' }
    case 'pending':
    default:
      return { label: '索引待重建', tone: 'warn' }
  }
}

// V2.0.1：本页发起操作（提取 / 新增 / 更新 / 删除）的实时状态与阶段时间线
function InlineOperation({ operation }: { operation: OperationDetail | null }) {
  if (!operation) return <Badge tone="neutral">提交中…</Badge>
  return (
    <div className="stack" style={{ marginTop: 'var(--s4)' }}>
      <div className="hstack" style={{ marginTop: 0 }}>
        <Badge tone={statusTone(operation.status)}>{statusLabel(operation.status)}</Badge>
        {operation.stage_name && <Badge tone="accent">{operation.stage_name}</Badge>}
        <span className="muted">已用时 {fmtMs(operation.elapsed_ms)}</span>
        <span className="op-id">#{operation.operation_id.slice(0, 8)}</span>
      </div>
      <OperationTimeline operation={operation} />
    </div>
  )
}

function emptyForm(): ExperienceItem {
  return {
    type: 'work',
    title: '',
    company: '',
    time: '',
    role: '',
    description: '',
    skills: [],
    achievements: [],
    raw_text: '',
  }
}

function formFromExp(exp: ExperienceOut): ExperienceItem {
  return {
    type: exp.type,
    title: exp.title,
    company: exp.company,
    time: exp.time,
    role: exp.role,
    description: exp.description,
    skills: exp.skills ?? [],
    achievements: exp.achievements ?? [],
    raw_text: exp.raw_text ?? '',
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

// 单个经历编辑弹窗
function ExperienceForm({
  initial,
  saving,
  onCancel,
  onSave,
}: {
  initial: ExperienceItem
  saving: boolean
  onCancel: () => void
  onSave: (data: ExperienceItem) => void
}) {
  const [form, setForm] = useState<ExperienceItem>(initial)
  const [skillsText, setSkillsText] = useState((initial.skills ?? []).join(', '))
  const [achievementsText, setAchievementsText] = useState((initial.achievements ?? []).join('\n'))

  const set = (k: keyof ExperienceItem) => (v: string) =>
    setForm((f) => ({ ...f, [k]: v }))

  function submit() {
    onSave({
      ...form,
      skills: splitSkills(skillsText),
      achievements: splitAchievements(achievementsText),
    })
  }

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="modal__head">
          <h2 className="modal__title">编辑经历</h2>
          <Button variant="ghost" size="sm" onClick={onCancel}>
            关闭
          </Button>
        </div>
        <div className="modal__body">
          <div className="form-grid">
            <Field label="类型">
              <Select value={form.type} onChange={(e) => set('type')(e.target.value)}>
                {EXPERIENCE_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="标题">
              <TextInput value={form.title} onChange={(e) => set('title')(e.target.value)} placeholder="后端工程师 / XX 项目" />
            </Field>
            <Field label="公司 / 组织">
              <TextInput value={form.company} onChange={(e) => set('company')(e.target.value)} placeholder="某公司" />
            </Field>
            <Field label="时间">
              <TextInput value={form.time} onChange={(e) => set('time')(e.target.value)} placeholder="2020-2023" />
            </Field>
            <Field label="角色">
              <TextInput value={form.role} onChange={(e) => set('role')(e.target.value)} placeholder="后端" />
            </Field>
            <Field label="技能（逗号分隔）">
              <TextInput value={skillsText} onChange={(e) => setSkillsText(e.target.value)} placeholder="Python, SQL, Docker" />
            </Field>
          </div>
          <div className="stack" style={{ marginTop: 'var(--s4)' }}>
            <Field label="职责描述">
              <TextArea value={form.description} onChange={(e) => set('description')(e.target.value)} placeholder="负责订单系统重构…" />
            </Field>
            <Field label="成果（每行一条）">
              <TextArea value={achievementsText} onChange={(e) => setAchievementsText(e.target.value)} placeholder={'QPS 提升 30%\n交付准时率 100%'} />
            </Field>
          </div>
          <div className="hstack">
            <Button onClick={submit} disabled={saving}>
              {saving ? '保存中…' : '保存'}
            </Button>
            <Button variant="ghost" onClick={onCancel} disabled={saving}>
              取消
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function ProfilePage() {
  const [items, setItems] = useState<ExperienceOut[]>([])
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null)

  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('')

  const [editing, setEditing] = useState<ExperienceItem | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const [deleting, setDeleting] = useState<ExperienceOut | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)

  // V2.0.1：单条 CRUD 与提取操作的实时阶段
  const [crudOpId, setCrudOpId] = useState<string | null>(null)
  const [crudActive, setCrudActive] = useState(false)
  const crudOperation = useOperation(crudOpId, crudActive)

  // PDF 导入流程
  const [importOpen, setImportOpen] = useState(false)
  const [importStep, setImportStep] = useState<'upload' | 'review'>('upload')
  const [importText, setImportText] = useState('')
  const [importExtracting, setImportExtracting] = useState(false)
  // V2.1.0 D-038：review 列表只保留「需确认」条目（inferred 或自动直入失败项）
  const [importItems, setImportItems] = useState<ExtractExperienceItem[]>([])
  const [importResults, setImportResults] = useState<{ idx: number; ok: boolean; msg: string }[]>([])
  const [importSaving, setImportSaving] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
  // 分流提示（如「N 项已自动整理入库」），review 期显示
  const [importSummary, setImportSummary] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const chooseFileBtnRef = useRef<HTMLButtonElement>(null)
  // V2.1.0 T7：/profile?import=1 只在初始挂载读取一次，不随渲染循环触发
  const importParamHandled = useRef(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const list = await experienceApi.list()
      setItems(list)
      setNotice(null)
    } catch (e) {
      setNotice({ ok: false, text: e instanceof ApiError ? e.message : String(e) })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // V2.1.0 T7：欢迎页卡 A 跳转 /profile?import=1 → 打开导入弹窗并聚焦「选择 PDF 文件」。
  // 仅在首次挂载读取 query 一次；若浏览器不允许程序化拉起文件选择器，
  // 用户仍可直接操作已聚焦的选择按钮（真实路径，不伪造任何状态）。
  useEffect(() => {
    if (importParamHandled.current) return
    importParamHandled.current = true
    if (new URLSearchParams(window.location.search).get('import') !== '1') return
    resetImport()
    setImportOpen(true)
    window.setTimeout(() => {
      chooseFileBtnRef.current?.focus()
      fileRef.current?.click()
    }, 120)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const sorted = useMemo(() => {
    const q = search.trim().toLowerCase()
    const filtered = items.filter((it) => {
      if (typeFilter && it.type !== typeFilter) return false
      if (!q) return true
      const hay = [it.title, it.company, it.role, it.description].join(' ').toLowerCase()
      return hay.includes(q)
    })
    return filtered.sort((a, b) => {
      const byType = a.type.localeCompare(b.type)
      if (byType !== 0) return byType
      const byTime = (a.time ?? '').localeCompare(b.time ?? '')
      if (byTime !== 0) return byTime
      const byTitle = a.title.localeCompare(b.title)
      if (byTitle !== 0) return byTitle
      return a.id.localeCompare(b.id)
    })
  }, [items, search, typeFilter])

  // DS-002 tab 计数：按真实 type 值域统计（与搜索词无关，仅反映当前库规模）
  const typeCounts = useMemo(() => {
    const c = new Map<string, number>()
    for (const it of items) c.set(it.type, (c.get(it.type) ?? 0) + 1)
    return c
  }, [items])

  function openCreate() {
    setEditingId(null)
    setEditing(emptyForm())
  }

  function openEdit(exp: ExperienceOut) {
    setEditingId(exp.id)
    setEditing(formFromExp(exp))
  }

  async function saveForm(data: ExperienceItem) {
    const id = newOperationId()
    setCrudOpId(id)
    setCrudActive(true)
    setSaving(true)
    try {
      if (editingId) {
        await experienceApi.update(editingId, data, id)
        setNotice({ ok: true, text: '已保存。后端已同步事实并对旧向量做失效处理。' })
      } else {
        await experienceApi.create(data, id)
        setNotice({ ok: true, text: '已创建。后端已生成事实，索引将在重建后可用。' })
      }
      setEditing(null)
      await load()
    } catch (e) {
      setNotice({ ok: false, text: e instanceof ApiError ? e.message : String(e) })
    } finally {
      setSaving(false)
      setCrudActive(false)
    }
  }

  async function doDelete() {
    if (!deleting) return
    const id = newOperationId()
    setCrudOpId(id)
    setCrudActive(true)
    setDeleteBusy(true)
    try {
      await experienceApi.remove(deleting.id, id)
      setDeleting(null)
      setNotice({ ok: true, text: '已删除，相关事实与向量一并清理。' })
      await load()
    } catch (e) {
      setNotice({ ok: false, text: e instanceof ApiError ? e.message : String(e) })
    } finally {
      setDeleteBusy(false)
      setCrudActive(false)
    }
  }

  function resetImport() {
    setImportStep('upload')
    setImportText('')
    setImportItems([])
    setImportResults([])
    setImportError(null)
    setImportSummary(null)
    setNotice(null)
  }

  async function onPickFile(file: File | undefined) {
    if (!file) return
    setImportError(null)
    try {
      const res = await resumeApi.uploadPdf(file)
      setImportText(res.text)
      setImportStep('upload')
    } catch (e) {
      setImportError(e instanceof ApiError ? e.message : String(e))
    }
  }

  // V2.1.0 D-038：direct 条目自动落库（group 聚合），失败项回到「需确认」可重试
  async function autoSaveDirect(direct: ExtractExperienceItem[]) {
    const groupId = newOperationId()
    const failed: ExtractExperienceItem[] = []
    let okCount = 0
    for (const item of direct) {
      try {
        const data = toCreatePayload(item)
        await experienceApi.create(data, newOperationId(), groupId)
        okCount++
      } catch {
        failed.push(item)
      }
    }
    if (failed.length > 0) {
      setImportItems((cur) => [...cur, ...failed])
      setImportSummary(
        `已自动整理 ${okCount} 项进入「我的经历」；${failed.length} 项自动保存失败，请在下方核对后重新保存。`,
      )
    } else {
      setImportSummary(`已自动整理 ${okCount} 项进入「我的经历」。`)
    }
    await load()
  }

  async function runExtract() {
    if (!importText.trim()) return
    const id = newOperationId()
    setCrudOpId(id)
    setCrudActive(true)
    setImportExtracting(true)
    setImportError(null)
    setImportSummary(null)
    try {
      const res = await experienceApi.extract({ resume_text: importText }, id)
      if (!res.experiences || res.experiences.length === 0) {
        setImportError('未能从简历中提取到经历，请确认「本地系统」已配置并测试连接后重试。')
        setImportStep('upload')
        return
      }
      // D-038 分流：direct → 自动入库；其余（inferred/无证据）→ 需确认
      const needsConfirm = res.experiences.filter(
        (e) => e.provenance?.classification !== 'direct',
      )
      const direct = res.experiences.filter((e) => e.provenance?.classification === 'direct')
      setImportItems(needsConfirm)
      if (direct.length > 0) {
        await autoSaveDirect(direct)
      } else {
        setImportSummary('本次提取均为 AI 推断/补全内容，请在下方逐项核对后保存。')
      }
      setImportResults([])
      setImportStep('review')
    } catch (e) {
      setImportError(e instanceof ApiError ? e.message : String(e))
      setImportStep('upload')
    } finally {
      setImportExtracting(false)
      setCrudActive(false)
    }
  }

  function updateImported(idx: number, patch: Partial<ExperienceItem>) {
    setImportItems((arr) => arr.map((it, i) => (i === idx ? { ...it, ...patch } : it)))
  }

  async function saveAllImported() {
    setImportSaving(true)
    setNotice(null)
    const groupId = newOperationId()
    const results: { idx: number; ok: boolean; msg: string }[] = []
    for (let i = 0; i < importItems.length; i++) {
      try {
        const data = toCreatePayload(importItems[i])
        await experienceApi.create(data, newOperationId(), groupId)
        results.push({ idx: i, ok: true, msg: '已保存' })
      } catch (e) {
        results.push({ idx: i, ok: false, msg: e instanceof ApiError ? e.message : String(e) })
      }
    }
    setImportResults(results)
    setImportSaving(false)
    const okCount = results.filter((r) => r.ok).length
    const failCount = results.length - okCount
    setNotice(
      failCount === 0
        ? { ok: true, text: `全部 ${okCount} 项已保存。` }
        : { ok: false, text: `部分完成：成功 ${okCount} 项，失败 ${failCount} 项（未保存项见下）。` },
    )
    await load()
  }

  // DS-002：页头「上传 PDF」——重置并打开导入 Modal，等 Modal 挂载后聚焦/拉起 file input
  function openImportUpload() {
    resetImport()
    setImportOpen(true)
    window.setTimeout(() => {
      fileRef.current?.click()
    }, 80)
  }

  function clearFilters() {
    setSearch('')
    setTypeFilter('')
  }

  return (
    <div className="page">
      <PageHeader
        title="我的经历"
        description="长期事实库 · 新事实经确认后写入。本页为「我的经历」主列表；每条的 summary_status 徽章为真实索引状态，事实明细由后端 Fact 服务维护。"
        actions={
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s3)', flexWrap: 'wrap' }}>
            <Button onClick={openImportUpload}>上传 PDF</Button>
            <Button variant="ghost" onClick={openCreate}>
              新增经历
            </Button>
          </div>
        }
      />

      {/* ── V2.0.1 本页当前操作 ── */}
      {crudActive && (
        <Card title="当前操作" subtitle="本页发起操作（提取 / 新增 / 更新 / 删除）的实时阶段与耗时。">
          <InlineOperation operation={crudOperation} />
        </Card>
      )}

      {/* ── V2.1.0 DS-002：我的经历主从视图（信息架构：tab 筛选 + 搜索 + 单列主列表） ── */}
      <Card>
        <div className="exp-master" style={masterStyle}>
          <div className="exp-toolbar" style={toolbarStyle}>
            <div className="exp-tabs" role="tablist" aria-label="按经历类型筛选" style={tabsStyle}>
              {FILTER_TABS.map((t) => {
                const active = typeFilter === t.value
                const count = t.value === '' ? items.length : (typeCounts.get(t.value) ?? 0)
                return (
                  <button
                    key={t.value}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    className="exp-tab"
                    style={{ ...tabBaseStyle, ...(active ? tabActiveStyle : {}) }}
                    onClick={() => setTypeFilter(t.value)}
                  >
                    {t.label}
                    <span style={tabCountStyle}>{count}</span>
                  </button>
                )
              })}
            </div>
            <div className="exp-toolbar__end" style={toolbarEndStyle}>
              <input
                className="input"
                type="search"
                placeholder="按标题 / 公司 / 角色 / 描述查找"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ width: 'min(300px, 42vw)', minWidth: 200 }}
              />
              <Button variant="ghost" onClick={load}>
                刷新
              </Button>
            </div>
          </div>

          {notice && (
            <div
              className={`notice ${notice.ok ? 'notice--ok' : 'notice--danger'}`}
              style={{ margin: '0 0 var(--s4)' }}
            >
              {notice.text}
            </div>
          )}

          {loading ? (
            <p className="muted" style={{ padding: 'var(--s6) 0', textAlign: 'center' }}>
              读取中…
            </p>
          ) : sorted.length === 0 ? (
            items.length === 0 ? (
              <div className="empty">
                <p className="empty__title">还没有任何经历</p>
                <p className="empty__desc">上传现有简历或新增一段经历，从这里开始构建你的长期事实库。</p>
                <div style={{ display: 'flex', gap: 'var(--s3)', marginTop: 'var(--s3)', flexWrap: 'wrap', justifyContent: 'center' }}>
                  <Button onClick={openImportUpload}>上传 PDF</Button>
                  <Button variant="secondary" onClick={openCreate}>
                    新增经历
                  </Button>
                </div>
              </div>
            ) : (
              <div className="empty">
                <p className="empty__title">没有匹配的经历</p>
                <p className="empty__desc">调整类型 tab 或查找关键词后再试。</p>
                <Button variant="ghost" onClick={clearFilters} style={{ marginTop: 'var(--s3)' }}>
                  清除筛选
                </Button>
              </div>
            )
          ) : (
            <ul className="exp-list" style={listScrollStyle}>
              {sorted.map((exp) => {
                const meta = summaryMeta(exp.summary_status)
                return (
                  <li className="exp-item" key={exp.id}>
                    <div className="exp-item__head">
                      <div>
                        <span className="exp-item__title">{exp.title || '（未命名）'}</span>{' '}
                        <Badge tone="neutral">{typeLabel(exp.type)}</Badge>
                        <div className="exp-item__meta">
                          {[exp.company, exp.time, exp.role].filter(Boolean).join(' · ')}
                        </div>
                      </div>
                      <div className="exp-item__actions">
                        <Badge tone={meta.tone}>{meta.label}</Badge>
                        {typeof exp.fact_count === 'number' && (
                          <span className="tag">{exp.fact_count} 事实</span>
                        )}
                        <Button size="sm" variant="ghost" onClick={() => openEdit(exp)}>
                          编辑
                        </Button>
                        <Button size="sm" variant="danger" onClick={() => setDeleting(exp)}>
                          删除
                        </Button>
                      </div>
                    </div>
                    {exp.description && <p className="exp-item__desc">{exp.description}</p>}
                    {exp.skills && exp.skills.length > 0 && (
                      <div className="exp-item__tags">
                        {exp.skills.map((s) => (
                          <span className="tag" key={s}>
                            {s}
                          </span>
                        ))}
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </Card>

      {editing && (
        <ExperienceForm
          initial={editing}
          saving={saving}
          onCancel={() => setEditing(null)}
          onSave={saveForm}
        />
      )}

      {deleting && (
        <div className="modal-backdrop" onClick={() => setDeleting(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
            <div className="modal__head">
              <h2 className="modal__title">删除确认</h2>
            </div>
            <div className="modal__body">
              <p className="confirm__text">
                确认删除「{deleting.title || '（未命名）'}」？该经历的事实与向量将一并清理，且不可恢复。
              </p>
              <div className="hstack">
                <Button variant="danger" onClick={doDelete} disabled={deleteBusy}>
                  {deleteBusy ? '删除中…' : '确认删除'}
                </Button>
                <Button variant="ghost" onClick={() => setDeleting(null)} disabled={deleteBusy}>
                  取消
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {importOpen && (
        <div className="modal-backdrop" onClick={() => setImportOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
            <div className="modal__head">
              <h2 className="modal__title">导入 PDF</h2>
              <Button variant="ghost" size="sm" onClick={() => setImportOpen(false)}>
                关闭
              </Button>
            </div>
            <div className="modal__body">
              <div className="stack">
                <div className="hstack">
                  <input
                    ref={fileRef}
                    type="file"
                    accept="application/pdf,.pdf"
                    style={{ display: 'none' }}
                    onChange={(e) => onPickFile(e.target.files?.[0])}
                  />
                  <button
                    ref={chooseFileBtnRef}
                    type="button"
                    className="btn btn--secondary"
                    onClick={() => fileRef.current?.click()}
                  >
                    选择 PDF 文件
                  </button>
                  <span className="muted">
                    {importText ? '已解析出文本，可点击「提取经历」。' : '支持 PDF，解析成功后提取为经历。'}
                  </span>
                </div>

                {importText && (
                  <TextArea
                    value={importText}
                    onChange={(e) => setImportText(e.target.value)}
                    placeholder="解析出的简历文本"
                  />
                )}

                {importError && <div className="notice notice--danger">{importError}</div>}

                {importStep === 'upload' && (
                  <div className="stack">
                    <div className="hstack" style={{ marginTop: 0 }}>
                      <Button onClick={runExtract} disabled={!importText.trim() || importExtracting}>
                        {importExtracting ? '提取中…' : '提取经历'}
                      </Button>
                    </div>
                    {importExtracting && <InlineOperation operation={crudOperation} />}
                  </div>
                )}

                {importStep === 'review' && (
                  <div className="stack">
                    {importSummary && <div className="notice notice--ok">{importSummary}</div>}
                    <h3 className="section-label">
                      需确认条目（共 {importItems.length} 项）：内容含 AI 推断/补全，请核对原文后保存
                    </h3>
                    {importItems.map((item, idx) => {
                      const r = importResults.find((x) => x.idx === idx)
                      const snippets = item.provenance?.source_snippets ?? []
                      return (
                        <div className="exp-item" key={idx}>
                          <div className="exp-item__head">
                            <span className="exp-item__title">
                              {idx + 1}. {item.title || '（未命名）'}
                            </span>
                            <Badge tone="warn">需确认</Badge>
                            {r && (
                              <Badge tone={r.ok ? 'ok' : 'danger'}>{r.ok ? '已保存' : '失败'}</Badge>
                            )}
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
                              <Select value={item.type} onChange={(e) => updateImported(idx, { type: e.target.value })}>
                                {EXPERIENCE_TYPES.map((t) => (
                                  <option key={t.value} value={t.value}>
                                    {t.label}
                                  </option>
                                ))}
                              </Select>
                            </Field>
                            <Field label="标题">
                              <TextInput value={item.title} onChange={(e) => updateImported(idx, { title: e.target.value })} />
                            </Field>
                            <Field label="公司 / 组织">
                              <TextInput value={item.company} onChange={(e) => updateImported(idx, { company: e.target.value })} />
                            </Field>
                            <Field label="时间">
                              <TextInput value={item.time} onChange={(e) => updateImported(idx, { time: e.target.value })} />
                            </Field>
                            <Field label="角色">
                              <TextInput value={item.role} onChange={(e) => updateImported(idx, { role: e.target.value })} />
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
                              <TextArea value={item.description} onChange={(e) => updateImported(idx, { description: e.target.value })} />
                            </Field>
                            <Field label="成果（每行一条）">
                              <TextArea
                                value={(item.achievements ?? []).join('\n')}
                                onChange={(e) => updateImported(idx, { achievements: splitAchievements(e.target.value) })}
                              />
                            </Field>
                            {r && !r.ok && <p className="notice notice--danger">{r.msg}</p>}
                          </div>
                        </div>
                      )
                    })}
                    {importItems.length === 0 && !importSummary && (
                      <div className="empty">
                        <p className="empty__desc">没有提取到经历，请返回检查简历文本或连接配置。</p>
                        <Button variant="secondary" onClick={() => { setImportStep('upload'); setImportError(null) }}>
                          返回重新提取
                        </Button>
                      </div>
                    )}
                    {importItems.length === 0 && importSummary && (
                      <div className="empty">
                        <p className="empty__desc">本次提取全部自动整理入库，无需逐条确认。</p>
                        <Button variant="secondary" onClick={() => { setImportOpen(false); resetImport() }}>
                          完成
                        </Button>
                      </div>
                    )}
                    {importItems.length > 0 && (
                      <div className="hstack">
                        <Button onClick={saveAllImported} disabled={importSaving}>
                          {importSaving ? '保存中…' : '批量保存'}
                        </Button>
                        {importResults.length > 0 && (
                          <Button variant="ghost" onClick={() => { setImportOpen(false); resetImport() }}>
                            完成
                          </Button>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}