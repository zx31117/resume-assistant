import { useCallback, useEffect, useRef, useState } from 'react'
import PageHeader from '../components/PageHeader'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { Field, Select, TextInput } from '../components/ui/Field'
import OperationTimeline from '../components/OperationTimeline'
import { useServices } from '../services'
import { ApiError } from '../api/client'
import { useOperation, statusLabel, statusTone, fmtMs, fmtTime } from '../hooks/useOperation'
import type {
  ConfigSnapshot,
  ConnectionTestResponse,
  DiagnosticsSummary,
  LogEvent,
  OperationProjection,
  SystemStatus,
} from '../api/types'

type MaintenanceOp = 'migrate' | 'rebuild' | 'retry'

const OP_LABEL: Record<string, string> = {
  migrate: '迁移',
  rebuild: '重建索引',
  retry: '重试失败项',
  generate: '生成简历',
}

// V2.0.1：operation_type / resource_type / 日志级别 → 中文稳定映射（PLAN §7.1）
const OP_TYPE_LABEL: Record<string, string> = {
  generate: '生成简历',
  extract: '提取经历',
  experience_create: '新增经历',
  experience_update: '更新经历',
  experience_delete: '删除经历',
  migrate: '迁移',
  rebuild: '重建索引',
  retry: '重试失败项',
}

const RESOURCE_LABEL: Record<string, string> = {
  LOCAL_DB: '本地数据库',
  LOCAL_FILE: '本地文件',
  LOCAL_CPU: '本地计算',
  LLM: 'LLM',
  EMBEDDING: 'Embedding',
}

function levelTone(level: string): 'neutral' | 'ok' | 'warn' | 'danger' {
  switch (level) {
    case 'ERROR':
      return 'danger'
    case 'WARNING':
      return 'warn'
    case 'INFO':
      return 'neutral'
    default:
      return 'neutral'
  }
}

interface Notice {
  ok: boolean
  text: string
}

// 候选配置：非密钥字段用快照预填；API Key 永不回填明文。
function emptyForm(snap: ConfigSnapshot | null) {
  return {
    ark_base_url: snap?.ARK_BASE_URL.value ?? '',
    llm_model: snap?.LLM_MODEL.value ?? '',
    embedding_model: snap?.EMBEDDING_MODEL.value ?? '',
    ark_api_key: '',
  }
}

/**
 * V2.1.0（DS-002「开发者后台」）：SystemPage 按 DS-002 dev 视图信息架构重塑，
 * 但所有能力保持真实：
 * - 全部后端调用改走 useServices() 端口（config / system），不直连 api/endpoints；
 * - Provider 配置 / 数据库与索引 / 最近运行活动 / 诊断（日志）四组，
 *   操作详情以模态呈现；轮询区保留 aria-live。
 */
export default function SystemPage() {
  const services = useServices()

  const [snapshot, setSnapshot] = useState<ConfigSnapshot | null>(null)
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [form, setForm] = useState(() => emptyForm(null))
  const prefilled = useRef(false)

  const [testResult, setTestResult] = useState<ConnectionTestResponse | null>(null)
  const [testing, setTesting] = useState(false)
  const [activating, setActivating] = useState(false)
  const [configNotice, setConfigNotice] = useState<Notice | null>(null)

  const [opRunning, setOpRunning] = useState<MaintenanceOp | null>(null)
  const [confirmOp, setConfirmOp] = useState<MaintenanceOp | null>(null)
  const [opNotice, setOpNotice] = useState<Notice | null>(null)
  const [loading, setLoading] = useState(true)

  // ── V2.0.1 运行活动 / 后台日志 / 诊断摘要 ──
  const [operations, setOperations] = useState<OperationProjection[]>([])
  const [diagHealth, setDiagHealth] = useState<string>('')
  const [opStatusFilter, setOpStatusFilter] = useState('')
  const [opTypeFilter, setOpTypeFilter] = useState('')
  const [selectedOpId, setSelectedOpId] = useState<string | null>(null)
  const [diag, setDiag] = useState<DiagnosticsSummary | null>(null)
  const [diagNote, setDiagNote] = useState<string | null>(null)
  const [logs, setLogs] = useState<LogEvent[]>([])
  const [afterSeq, setAfterSeq] = useState(0)
  const [logNotice, setLogNotice] = useState<string | null>(null)
  const [clearConfirm, setClearConfirm] = useState(false)

  // 选中操作的实时详情（轮询直到终态，PLAN §3.4）
  const selectedOperation = useOperation(selectedOpId, selectedOpId !== null)

  const loadOperations = useCallback(async () => {
    try {
      const params: { limit: number; status?: string; operation_type?: string } = { limit: 20 }
      if (opStatusFilter) params.status = opStatusFilter
      if (opTypeFilter) params.operation_type = opTypeFilter
      const res = await services.system.listOperations(params)
      setOperations(res.operations)
      setDiagHealth(res.diagnostics_health)
    } catch {
      // 诊断读取失败不影响主状态区；保持上一份快照
    }
  }, [services, opStatusFilter, opTypeFilter])

  const loadLogs = useCallback(
    async (incremental = true) => {
      try {
        const res = await services.system.readLogs(incremental ? afterSeq : 0, 200)
        setLogs((prev) => (incremental ? [...prev, ...res.events] : res.events).slice(-500))
        let maxSeq = afterSeq
        for (const ev of res.events) if (ev.seq > maxSeq) maxSeq = ev.seq
        setAfterSeq(maxSeq)
      } catch {
        setLogNotice('后台日志读取失败（诊断设施可能已降级）。')
      }
    },
    [services, afterSeq],
  )

  // 运行活动与日志短轮询（本地诊断，成本低）
  useEffect(() => {
    loadOperations()
    const t = setInterval(loadOperations, 2000)
    return () => clearInterval(t)
  }, [loadOperations])

  useEffect(() => {
    loadLogs(true)
    const t = setInterval(() => loadLogs(true), 2000)
    return () => clearInterval(t)
  }, [loadLogs])

  async function viewOperation(id: string) {
    setSelectedOpId(id)
    setDiag(null)
    setDiagNote(null)
    try {
      const d = await services.system.diagnostics(id)
      setDiag(d.diagnostics)
    } catch {
      setDiag(null)
      setDiagNote('诊断摘要读取失败（该操作可能已被清理）。')
    }
  }

  function closeDetail() {
    setSelectedOpId(null)
    setDiag(null)
    setDiagNote(null)
  }

  async function copyDiagnostics() {
    if (!selectedOpId) return
    setDiagNote(null)
    try {
      const d = diag ?? (await services.system.diagnostics(selectedOpId)).diagnostics
      setDiag(d)
      await navigator.clipboard.writeText(JSON.stringify(d, null, 2))
      setDiagNote('已复制脱敏诊断摘要。')
    } catch {
      setDiagNote('复制失败（浏览器未授权剪贴板或摘要不可用）。')
    }
  }

  async function doClearLogs() {
    setClearConfirm(false)
    try {
      await services.system.clearLogs()
      setLogs([])
      setAfterSeq(0)
      setLogNotice('历史日志已清理。')
    } catch (e) {
      setLogNotice(`清理失败：${e instanceof ApiError ? e.message : String(e)}`)
    }
  }

  const loadAll = useCallback(async () => {
    try {
      const [snap, st] = await Promise.all([services.config.snapshot(), services.system.status()])
      setSnapshot(snap)
      setStatus(st)
      if (!prefilled.current) {
        setForm(emptyForm(snap))
        prefilled.current = true
      }
    } catch (e) {
      setConfigNotice({
        ok: false,
        text: e instanceof ApiError ? e.message : String(e),
      })
    } finally {
      setLoading(false)
    }
  }, [services])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  const set = (k: keyof typeof form) => (v: string) => setForm((f) => ({ ...f, [k]: v }))

  async function runTest() {
    setTesting(true)
    setConfigNotice(null)
    setTestResult(null)
    try {
      const res = await services.config.test(form)
      setTestResult(res)
      setConfigNotice(
        res.ok
          ? { ok: true, text: '连接测试通过：LLM 与 Embedding 均可用。' }
          : { ok: false, text: '连接测试未完全通过，请检查字段或 Key。' },
      )
    } catch (e) {
      setConfigNotice({
        ok: false,
        text: e instanceof ApiError ? e.message : String(e),
      })
    } finally {
      setTesting(false)
    }
  }

  async function runActivate() {
    setActivating(true)
    setConfigNotice(null)
    try {
      const snap = await services.config.activate(form)
      setSnapshot(snap)
      setForm((f) => ({ ...f, ark_api_key: '' }))
      setConfigNotice({ ok: true, text: '配置已激活，后续请求将使用新配置。' })
    } catch (e) {
      setConfigNotice({
        ok: false,
        text: e instanceof ApiError ? e.message : String(e),
      })
    } finally {
      setActivating(false)
    }
  }

  async function runOp(op: MaintenanceOp) {
    setConfirmOp(null)
    const label = op === 'migrate' ? '迁移' : op === 'rebuild' ? '重建索引' : '重试失败项'
    setOpRunning(op)
    setOpNotice(null)
    try {
      if (op === 'migrate') await services.system.migrate()
      else if (op === 'rebuild') await services.system.rebuild()
      else await services.system.retry()
      setOpNotice({ ok: true, text: `${label}完成。` })
      await loadAll()
    } catch (e) {
      if (e instanceof ApiError && e.error_code === 'OPERATION_IN_PROGRESS') {
        const holder = e.details?.holder as string | undefined
        const holderLabel = holder ? OP_LABEL[holder] ?? holder : '另一项任务'
        setOpNotice({
          ok: false,
          text: `${label}未执行：检测到「${holderLabel}」仍在进行中，请等待其完成后再试。`,
        })
      } else {
        setOpNotice({
          ok: false,
          text: `${label}失败：${e instanceof ApiError ? e.message : String(e)}`,
        })
      }
    } finally {
      setOpRunning(null)
    }
  }

  const keyMeta = snapshot?.ARK_API_KEY
  const ready = status?.ready ?? false
  const providerTone = keyMeta?.configured ? 'ok' : 'warn'
  const providerBadge = keyMeta?.configured ? `Key ${keyMeta.masked}` : 'Key 未配置'

  return (
    <>
      <div className="page">
        <PageHeader
          title="开发者后台"
          description="普通导航中隐藏本页，仅经侧栏脚注进入。本页管理 Provider 配置、本地数据库与索引，并提供运行活动与脱敏日志诊断；所有写操作仅作用于本机。"
        />

        <div className="sys-grid">
          {/* ── Provider 配置 ── */}
          <Card
            title="Provider 配置"
            subtitle="候选配置 → 测试 LLM / Embedding 能力 → 激活。API Key 仅用于本次激活，浏览器不长期保存。"
            actions={
              loading ? (
                <Badge tone="neutral">读取中…</Badge>
              ) : (
                <Badge tone={providerTone}>{providerBadge}</Badge>
              )
            }
          >
            <div className="form-grid">
              <Field label="Ark Base URL" hint="豆包 / 火山方舟服务地址，http(s) 开头">
                <TextInput
                  value={form.ark_base_url}
                  onChange={(e) => set('ark_base_url')(e.target.value)}
                  placeholder="https://ark.cn-beijing.volces.com/api/v3"
                  autoComplete="off"
                  spellCheck={false}
                />
              </Field>
              <Field
                label="API Key"
                hint={
                  keyMeta?.configured
                    ? `已配置（${keyMeta.masked}，来源 ${keyMeta.source}）；留空修改会要求重新粘贴 Key`
                    : '首次设置需填写完整 Key，不会写入浏览器存储'
                }
              >
                <TextInput
                  type="password"
                  autoComplete="off"
                  value={form.ark_api_key}
                  onChange={(e) => set('ark_api_key')(e.target.value)}
                  placeholder={keyMeta?.configured ? '重新粘贴以更新' : '粘贴 API Key'}
                />
              </Field>
              <Field label="LLM model">
                <TextInput
                  value={form.llm_model}
                  onChange={(e) => set('llm_model')(e.target.value)}
                  placeholder="doubao-seed-evolving"
                  autoComplete="off"
                  spellCheck={false}
                />
              </Field>
              <Field label="Embedding model">
                <TextInput
                  value={form.embedding_model}
                  onChange={(e) => set('embedding_model')(e.target.value)}
                  placeholder="doubao-embedding-vision-251215"
                  autoComplete="off"
                  spellCheck={false}
                />
              </Field>
            </div>

            {configNotice && (
              <div className={`notice ${configNotice.ok ? 'notice--ok' : 'notice--danger'}`}>
                {configNotice.text}
              </div>
            )}

            {testResult && (
              <div className="test-result">
                <span className="test-result__item">
                  LLM{' '}
                  <Badge tone={testResult.llm.ok ? 'ok' : 'danger'}>
                    {testResult.llm.ok ? '通过' : '失败'}
                  </Badge>
                  {testResult.llm.detail && (
                    <span className="test-result__detail">{testResult.llm.detail}</span>
                  )}
                </span>
                <span className="test-result__item">
                  Embedding{' '}
                  <Badge tone={testResult.embedding.ok ? 'ok' : 'danger'}>
                    {testResult.embedding.ok ? '通过' : '失败'}
                  </Badge>
                  {testResult.embedding.detail && (
                    <span className="test-result__detail">{testResult.embedding.detail}</span>
                  )}
                </span>
              </div>
            )}

            <div className="hstack">
              <Button variant="secondary" onClick={runTest} disabled={testing || activating}>
                {testing ? '测试中…' : '测试连接'}
              </Button>
              <Button onClick={runActivate} disabled={testing || activating}>
                {activating ? '激活中…' : '激活配置'}
              </Button>
            </div>
          </Card>

          {/* ── 数据库与索引 ── */}
          <Card
            title="数据库与索引"
            subtitle="Schema、Experience / Fact / Embedding 汇总，以及初始化 / 迁移、重建索引与失败重试。"
            actions={
              loading ? (
                <Badge tone="neutral">读取中…</Badge>
              ) : status ? (
                <Badge tone={ready ? 'ok' : 'warn'}>{ready ? '就绪' : '受限模式'}</Badge>
              ) : (
                <Badge tone="danger">状态不可读</Badge>
              )
            }
          >
            {loading ? (
              <p className="muted">读取中…</p>
            ) : status ? (
              <div className="stack">
                <div className="kv">
                  <div className="kv__row">
                    <span className="kv__k">应用版本</span>
                    <span className="kv__v" style={{ fontFamily: 'var(--font-mono)' }}>
                      {status.version}
                    </span>
                  </div>
                  <div className="kv__row">
                    <span className="kv__k">数据库迁移</span>
                    <span className="kv__v">
                      {status.migrations.missing.length > 0 ? (
                        <Badge tone="warn">缺少 {status.migrations.missing.join('、')}</Badge>
                      ) : (
                        <span>已应用 {status.migrations.applied_count} 项</span>
                      )}
                    </span>
                  </div>
                  <div className="kv__row">
                    <span className="kv__k">Experience / Fact</span>
                    <span className="kv__v">
                      {status.counts.experience} / {status.counts.fact}
                    </span>
                  </div>
                  {Object.keys(status.embeddings).length > 0 && (
                    <div className="kv__row">
                      <span className="kv__k">Embedding</span>
                      <span className="kv__v">
                        {Object.entries(status.embeddings)
                          .sort(([a], [b]) => a.localeCompare(b))
                          .map(([k, v]) => `${k}=${v}`)
                          .join('  ')}
                      </span>
                    </div>
                  )}
                </div>

                <div>
                  <h3 className="section-label">下一步</h3>
                  <ul className="next-steps">
                    {(status.next_steps.length ? status.next_steps : ['就绪。']).map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </div>

                {opNotice && (
                  <div className={`notice ${opNotice.ok ? 'notice--ok' : 'notice--danger'}`}>
                    {opNotice.text}
                  </div>
                )}

                <div className="hstack">
                  <OpButton
                    label="初始化 / 迁移"
                    confirm={true}
                    confirmText="迁移会先备份现有数据库再升级 schema，确认执行？"
                    confirmOp={confirmOp}
                    op="migrate"
                    busy={opRunning}
                    onConfirm={setConfirmOp}
                    onRun={runOp}
                  />
                  <OpButton
                    label="重建索引"
                    confirm={true}
                    confirmText="全量重建会重新计算所有 Embedding，期间生成不可用，确认执行？"
                    confirmOp={confirmOp}
                    op="rebuild"
                    busy={opRunning}
                    onConfirm={setConfirmOp}
                    onRun={runOp}
                  />
                  <OpButton
                    label="重试失败项"
                    confirm={false}
                    confirmText=""
                    confirmOp={confirmOp}
                    op="retry"
                    busy={opRunning}
                    onConfirm={setConfirmOp}
                    onRun={runOp}
                  />
                </div>
              </div>
            ) : (
              <p className="muted">无法读取状态。</p>
            )}
          </Card>

          {/* ── 最近运行活动 ── */}
          <Card
            title="最近运行活动"
            subtitle="真实操作轮询：状态、当前阶段、资源类型、总耗时与诊断码；支持按类型 / 结果筛选并查看阶段明细。"
            className="sys-grid__span"
            actions={
              <Button variant="secondary" size="sm" onClick={loadOperations}>
                刷新
              </Button>
            }
          >
            <div className="toolbar">
              <Select
                value={opStatusFilter}
                onChange={(e) => setOpStatusFilter(e.target.value)}
                style={{ width: 'auto' }}
                aria-label="按操作状态筛选"
              >
                <option value="">全部状态</option>
                <option value="RUNNING">执行中</option>
                <option value="SUCCEEDED">成功</option>
                <option value="FAILED">失败</option>
                <option value="TIMED_OUT">超时</option>
                <option value="INTERRUPTED">已中断</option>
              </Select>
              <Select
                value={opTypeFilter}
                onChange={(e) => setOpTypeFilter(e.target.value)}
                style={{ width: 'auto' }}
                aria-label="按操作类型筛选"
              >
                <option value="">全部类型</option>
                {Object.entries(OP_TYPE_LABEL).map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </Select>
              <span className="muted" style={{ marginLeft: 'auto' }}>
                诊断健康：{diagHealth || '—'}
              </span>
            </div>

            <div role="region" aria-label="运行活动列表（自动轮询）" aria-live="polite">
              {operations.length === 0 ? (
                <p className="muted">暂无操作记录。</p>
              ) : (
                <ul className="ops-list">
                  {operations.map((op) => (
                    <li className="ops-item" key={op.operation_id}>
                      <span className="ops-item__time">{fmtTime(op.started_at)}</span>
                      <Badge tone={statusTone(op.status)}>{statusLabel(op.status)}</Badge>
                      <span className="ops-item__stage">
                        {OP_TYPE_LABEL[op.operation_type] ?? op.operation_type}
                      </span>
                      {op.stage_name && <span className="tag">{op.stage_name}</span>}
                      <span className="tag">{RESOURCE_LABEL[op.resource_type] ?? op.resource_type}</span>
                      <span className="muted">{fmtMs(op.elapsed_ms)}</span>
                      {op.diagnostic_code && <span className="op-id">{op.diagnostic_code}</span>}
                      <span className="ops-item__spacer" />
                      <Button size="sm" variant="ghost" onClick={() => viewOperation(op.operation_id)}>
                        详情
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Card>

          {/* ── 诊断：后台日志 ── */}
          <Card
            title="诊断"
            subtitle="按事件序号增量读取的脱敏结构化日志；不含凭据、正文、PII 或本机绝对路径。"
            className="sys-grid__span"
            actions={
              <div className="hstack" style={{ marginTop: 0, gap: 'var(--s2)' }}>
                <Button variant="secondary" size="sm" onClick={() => loadLogs(false)}>
                  刷新全部
                </Button>
                {clearConfirm ? (
                  <>
                    <Button variant="danger" size="sm" onClick={doClearLogs}>
                      确认清理
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setClearConfirm(false)}>
                      取消
                    </Button>
                  </>
                ) : (
                  <Button variant="ghost" size="sm" onClick={() => setClearConfirm(true)}>
                    清理日志
                  </Button>
                )}
              </div>
            }
          >
            {logNotice && <div className="notice notice--warn">{logNotice}</div>}
            <div role="log" aria-live="polite" aria-label="后台日志流（增量读取）">
              {logs.length === 0 ? (
                <p className="muted">暂无日志事件。</p>
              ) : (
                <ul className="log-list">
                  {logs.slice(-200).map((ev, i) => (
                    <li className="log-row" key={`${ev.seq}-${i}`}>
                      <span className="log-row__time">{fmtTime(ev.ts)}</span>
                      <span className="log-row__meta">
                        <Badge tone={levelTone(ev.level)}>{ev.level}</Badge>
                      </span>
                      <span className="log-row__message">
                        {ev.component && `[${ev.component}] `}
                        {ev.event_code && `${ev.event_code} `}
                        {ev.operation_id && `#${ev.operation_id.slice(0, 8)} `}
                        {ev.stage_code && `${ev.stage_code} `}
                        {ev.message}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Card>
        </div>
      </div>

      {/* ── 操作详情模态（轮询阶段 + 脱敏诊断摘要） ── */}
      {selectedOpId && (
        <div
          className="modal-backdrop"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) closeDetail()
          }}
        >
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="op-detail-title"
            onKeyDown={(e) => {
              if (e.key === 'Escape') closeDetail()
            }}
          >
            <div className="modal__head">
              <h2 className="modal__title" id="op-detail-title">
                操作详情
              </h2>
              <Button variant="ghost" size="sm" onClick={closeDetail} autoFocus>
                关闭
              </Button>
            </div>
            <div className="modal__body">
              <div className="stack">
                <div className="hstack" style={{ marginTop: 0 }}>
                  {selectedOperation ? (
                    <>
                      <Badge tone={statusTone(selectedOperation.status)}>
                        {statusLabel(selectedOperation.status)}
                      </Badge>
                      <span style={{ color: 'var(--ink)' }}>
                        {OP_TYPE_LABEL[selectedOperation.operation_type] ??
                          selectedOperation.operation_type}
                      </span>
                      <span className="op-id">#{selectedOperation.operation_id.slice(0, 8)}</span>
                      <span className="muted">已用时 {fmtMs(selectedOperation.elapsed_ms)}</span>
                      {selectedOperation.attempt > 1 || selectedOperation.max_attempts > 1 ? (
                        <span className="muted">
                          尝试 {selectedOperation.attempt}/{selectedOperation.max_attempts}
                        </span>
                      ) : null}
                    </>
                  ) : (
                    <span className="muted">读取中…</span>
                  )}
                </div>

                {selectedOperation ? (
                  <OperationTimeline operation={selectedOperation} />
                ) : (
                  <p className="muted">阶段明细读取中…</p>
                )}

                <div className="section-label">脱敏诊断摘要</div>
                {diag ? (
                  <pre className="diag" style={{ marginTop: 0 }}>
                    {JSON.stringify(diag, null, 2)}
                  </pre>
                ) : (
                  <p className="muted">诊断摘要读取中…（若该操作已被清理，可稍后重试复制）。</p>
                )}

                {diagNote && (
                  <div className={`notice ${diagNote.includes('失败') ? 'notice--warn' : 'notice--ok'}`}>
                    {diagNote}
                  </div>
                )}

                <div className="hstack" style={{ justifyContent: 'space-between', marginTop: 'var(--s3)' }}>
                  <span className="muted">摘要已脱敏：不含凭据、正文与本机绝对路径。</span>
                  <Button variant="secondary" size="sm" onClick={copyDiagnostics}>
                    复制摘要
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

function OpButton({
  label,
  op,
  confirm,
  confirmText,
  confirmOp,
  busy,
  onConfirm,
  onRun,
}: {
  label: string
  op: MaintenanceOp
  confirm: boolean
  confirmText: string
  confirmOp: MaintenanceOp | null
  busy: MaintenanceOp | null
  onConfirm: (op: MaintenanceOp | null) => void
  onRun: (op: MaintenanceOp) => void
}) {
  if (!confirm) {
    return (
      <Button variant="secondary" onClick={() => onRun(op)} disabled={busy !== null}>
        {busy === op ? '执行中…' : label}
      </Button>
    )
  }
  if (confirmOp === op) {
    return (
      <span className="confirm">
        <span className="confirm__text">{confirmText}</span>
        <Button variant="danger" size="sm" onClick={() => onRun(op)} disabled={busy !== null}>
          确认执行
        </Button>
        <Button variant="ghost" size="sm" onClick={() => onConfirm(null)} disabled={busy !== null}>
          取消
        </Button>
      </span>
    )
  }
  return (
    <Button variant="secondary" onClick={() => onConfirm(op)} disabled={busy !== null}>
      {busy === op ? '执行中…' : label}
    </Button>
  )
}
