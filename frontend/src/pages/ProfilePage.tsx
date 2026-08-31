import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import PageHeader from '../components/PageHeader'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { Field, Select, TextArea, TextInput } from '../components/ui/Field'
import { experienceApi, resumeApi } from '../api/endpoints'
import { ApiError } from '../api/client'
import type { ExperienceItem, ExperienceOut } from '../api/types'

const EXPERIENCE_TYPES: { value: string; label: string }[] = [
  { value: 'work', label: '工作' },
  { value: 'project', label: '项目' },
  { value: 'education', label: '教育' },
]

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

  // PDF 导入流程
  const [importOpen, setImportOpen] = useState(false)
  const [importStep, setImportStep] = useState<'upload' | 'review'>('upload')
  const [importText, setImportText] = useState('')
  const [importExtracting, setImportExtracting] = useState(false)
  const [importItems, setImportItems] = useState<ExperienceItem[]>([])
  const [importResults, setImportResults] = useState<{ idx: number; ok: boolean; msg: string }[]>([])
  const [importSaving, setImportSaving] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

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

  function openCreate() {
    setEditingId(null)
    setEditing(emptyForm())
  }

  function openEdit(exp: ExperienceOut) {
    setEditingId(exp.id)
    setEditing(formFromExp(exp))
  }

  async function saveForm(data: ExperienceItem) {
    setSaving(true)
    try {
      if (editingId) {
        await experienceApi.update(editingId, data)
        setNotice({ ok: true, text: '已保存。后端已同步事实并对旧向量做失效处理。' })
      } else {
        await experienceApi.create(data)
        setNotice({ ok: true, text: '已创建。后端已生成事实，索引将在重建后可用。' })
      }
      setEditing(null)
      await load()
    } catch (e) {
      setNotice({ ok: false, text: e instanceof ApiError ? e.message : String(e) })
    } finally {
      setSaving(false)
    }
  }

  async function doDelete() {
    if (!deleting) return
    setDeleteBusy(true)
    try {
      await experienceApi.remove(deleting.id)
      setDeleting(null)
      setNotice({ ok: true, text: '已删除，相关事实与向量一并清理。' })
      await load()
    } catch (e) {
      setNotice({ ok: false, text: e instanceof ApiError ? e.message : String(e) })
    } finally {
      setDeleteBusy(false)
    }
  }

  function resetImport() {
    setImportStep('upload')
    setImportText('')
    setImportItems([])
    setImportResults([])
    setImportError(null)
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

  async function runExtract() {
    if (!importText.trim()) return
    setImportExtracting(true)
    setImportError(null)
    try {
      const res = await experienceApi.extract({ resume_text: importText })
      if (!res.experiences || res.experiences.length === 0) {
        setImportError('未能从简历中提取到经历，请确认「本地系统」已配置并测试连接后重试。')
        setImportStep('upload')
        return
      }
      setImportItems(res.experiences)
      setImportResults([])
      setImportStep('review')
    } catch (e) {
      setImportError(e instanceof ApiError ? e.message : String(e))
      setImportStep('upload')
    } finally {
      setImportExtracting(false)
    }
  }

  function updateImported(idx: number, patch: Partial<ExperienceItem>) {
    setImportItems((arr) => arr.map((it, i) => (i === idx ? { ...it, ...patch } : it)))
  }

  async function saveAllImported() {
    setImportSaving(true)
    setNotice(null)
    const results: { idx: number; ok: boolean; msg: string }[] = []
    for (let i = 0; i < importItems.length; i++) {
      try {
        await experienceApi.create(importItems[i])
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

  return (
    <div className="page">
      <PageHeader
        title="履历库"
        description="查看并维护你的 Experience（项目 / 工作 / 教育），支持 PDF 导入、逐项检查与增删改。事实层继续由后端 Fact 服务维护。"
        actions={<Button onClick={openCreate}>新建经历</Button>}
      />

      <Card
        title="Experience 列表"
        subtitle="保存后仅展示 Experience 级汇总状态；事实明细不在此页展开。"
        actions={
          <Button variant="secondary" onClick={() => { resetImport(); setImportOpen(true) }}>
            导入 PDF
          </Button>
        }
      >
        <div className="toolbar">
          <input
            className="input input--grow"
            type="search"
            placeholder="按标题 / 公司 / 角色 / 描述查找"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <Select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} style={{ width: 'auto' }}>
            <option value="">全部类型</option>
            {EXPERIENCE_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </Select>
          <Button variant="ghost" onClick={load}>
            刷新
          </Button>
        </div>

        {notice && (
          <div className={`notice ${notice.ok ? 'notice--ok' : 'notice--danger'}`}>{notice.text}</div>
        )}

        {loading ? (
          <p className="muted">读取中…</p>
        ) : sorted.length === 0 ? (
          <div className="empty">
            <p className="empty__title">{items.length === 0 ? '还没有 Experience' : '没有匹配的经历'}</p>
            <p className="empty__desc">
              {items.length === 0
                ? '点击「新建经历」手动录入，或「导入 PDF」从简历中提取。'
                : '调整查找关键词或类型筛选项。'}
            </p>
          </div>
        ) : (
          <ul className="exp-list">
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
                  <Button variant="secondary" onClick={() => fileRef.current?.click()}>
                    选择 PDF 文件
                  </Button>
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
                  <div className="hstack">
                    <Button onClick={runExtract} disabled={!importText.trim() || importExtracting}>
                      {importExtracting ? '提取中…' : '提取经历'}
                    </Button>
                  </div>
                )}

                {importStep === 'review' && (
                  <div className="stack">
                    <h3 className="section-label">逐项检查 / 修改后保存（共 {importItems.length} 项）</h3>
                    {importItems.map((item, idx) => {
                      const r = importResults.find((x) => x.idx === idx)
                      return (
                        <div className="exp-item" key={idx}>
                          <div className="exp-item__head">
                            <span className="exp-item__title">
                              {idx + 1}. {item.title || '（未命名）'}
                            </span>
                            {r && (
                              <Badge tone={r.ok ? 'ok' : 'danger'}>{r.ok ? '已保存' : '失败'}</Badge>
                            )}
                          </div>
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
                    {importItems.length === 0 && (
                      <div className="empty">
                        <p className="empty__desc">没有提取到经历，请返回检查简历文本或连接配置。</p>
                        <Button variant="secondary" onClick={() => { setImportStep('upload'); setImportError(null) }}>
                          返回重新提取
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