import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { ApiError, newOperationId } from '../../api/client'
import { taskApi } from '../../api/endpoints'
import type { TaskInput, TaskOut, TaskStatus, TaskSseDone, TaskSseEvent, TaskSseSnapshot } from '../../api/types'

/**
 * V2.2.0 T03：工作台任务工作流（绑定真实后端 /api/task）。
 *
 * - 支持 保存确认（dirty/saving/saved）+ 刷新恢复（GET 权威视图）；
 * - 生成：DRAFT 天系列 freeze → start → generate（后端异步执行 P1–P4）；
 * - SSE 只读订阅（run 期间渐进返回 snapshot/event），重连幂等，绝不触发生成；
 * - 所有成功态都以后端确认的 TaskOut 为准，不伪造本地假保存。
 */

const TASK_STORAGE_KEY = 'resume_assistant.lastTaskId'

export const EMPTY_TASK_INPUT: TaskInput = { name: '', phone: '', email: '', location: '', jd: '' }

export type LoadState = 'loading' | 'ready' | 'error'
export type WorkbenchPage = 'identity' | 'understand' | 'match' | 'download'

/** V2.2.0 T05：fact.done 瞬时事件载荷（快照还未纳入前，UI 临时呈现的来源）。 */
export interface LiveFactDone {
  experience_id?: string
  headline: string
  body: string
  fact_refs: string[]
}

export interface WorkbenchTaskValue {
  taskId: string | null
  status: TaskStatus | null
  input: TaskInput
  snapshotPhase: string
  /** 覆盖式/权威快照的 payload（P1/P2 渲染与历史回看的唯一业务真源）。 */
  snapshotPayload: Record<string, unknown> | null
  loadState: LoadState
  loadError: string | null
  saving: boolean
  dirty: boolean
  saveError: string | null
  generateError: string | null
  generatePending: boolean
  /** V2.2.0 T08：终态 FAILED/CANCELLED 的错误码（后端稳定 code，如 GENERATION_FAILED/TASK_CANCELLED）。 */
  terminalError: string | null
  /** 步骤状态数组（active / done / future / failed）。 */
  stepStates: Array<'active' | 'done' | 'future' | 'failed'>
  /** V2.2.0 T05：fact.reason 增量累积（按 fact_id）。快照已有全量理由时以快照为准。 */
  reasons: Record<string, string>
  /** V2.2.0 T05：via fact.done 已发布、但快照尚未纳管的 fact_id 列表（供 UI 实时冒泡）。 */
  liveFacts: string[]
  /** V2.2.0 T05：fact.done 瞬时事件载荷（快照未反映时 UI 的临时呈现来源）。 */
  factDone: Record<string, LiveFactDone>
  /** V2.2.0 T05：SSE 流是否已结束（done 帧 / error）→ 用于诚实断连提示。 */
  streamEnded: boolean
  /** V2.2.0 T06：终态发布的 artifact 相对路径（output/<file>.docx/pdf；为空表示该 artifact 不可用）。 */
  publishedDocxPath: string | null
  publishedPdfPath: string | null
  /** 当前应该落到哪一步工作页（DRAFT/READY→identity；RUNNING→按 snapshot phase）。 */
  routingPage: WorkbenchPage
  setInputField: (key: keyof TaskInput, value: string) => void
  saveNow: () => void
  generate: () => Promise<void>
  cancel: () => Promise<void>
  /** 「只重试失败范围」：从 FAILED 源任务创建续试任务（新 task_id），复用已完成、仅重跑失败范围。 */
  continueScope: () => Promise<void>
  retryLoad: () => void
  startNewTask: () => void
}

const WorkbenchTaskContext = createContext<WorkbenchTaskValue | null>(null)

function toError(e: unknown): string {
  if (e instanceof ApiError) return e.message
  return e instanceof Error ? e.message : String(e)
}

/** 从 snapshot.phase 推断生成所处用户阶段（P1–P4 / 步骤 1–4），失败返回 null。 */
function phaseToStep(phase: string): number | null {
  if (!phase) return null
  const m = phase.match(/(\d)/)
  if (!m) return null
  const n = Number(m[1])
  if (n >= 1 && n <= 4) return n - 1
  return null
}

/** 依据任务状态推导步骤导轨状态。 */
function computeStepStates(status: TaskStatus | null, phase: string): Array<'active' | 'done' | 'future' | 'failed'> {
  const future: Array<'active' | 'done' | 'future' | 'failed'> = ['future', 'future', 'future', 'future']
  switch (status) {
    case null:
    case 'DRAFT':
      future[0] = 'active'
      return future
    case 'READY':
      future[0] = 'done'
      future[1] = 'active'
      return future
    case 'RUNNING': {
      future[0] = 'done'
      const step = phaseToStep(phase)
      const active = step == null ? 1 : step
      for (let i = 1; i < 4; i++) {
        if (i < active) future[i] = 'done'
        else if (i === active) future[i] = 'active'
      }
      return future
    }
    case 'SUCCEEDED':
      return ['done', 'done', 'done', 'done']
    case 'FAILED': {
      future[0] = 'done'
      const step = phaseToStep(phase)
      future[step == null ? 1 : step] = 'failed'
      return future
    }
    case 'CANCELLED':
      future[0] = 'done'
      return future
    default:
      return future
  }
}

function pageForStatus(status: TaskStatus | null, phase: string): WorkbenchPage {
  switch (status) {
    case 'DRAFT':
    case 'READY':
    case null:
      return 'identity'
    case 'RUNNING':
      return (phaseToStep(phase) ?? 1) >= 1 ? 'understand' : 'identity'
    case 'SUCCEEDED':
      return 'download'
    case 'FAILED':
    case 'CANCELLED':
    default:
      return 'identity'
  }
}

export function WorkbenchTaskProvider({ children }: { children: ReactNode }) {
  const [taskId, setTaskId] = useState<string | null>(null)
  const [status, setStatus] = useState<TaskStatus | null>(null)
  const [input, setInput] = useState<TaskInput>(EMPTY_TASK_INPUT)
  const [confirmed, setConfirmed] = useState<TaskInput>(EMPTY_TASK_INPUT)
  const [snapshotPhase, setSnapshotPhase] = useState('')
  const [snapshotPayload, setSnapshotPayload] = useState<Record<string, unknown> | null>(null)
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [generateError, setGenerateError] = useState<string | null>(null)
  const [generatePending, setGeneratePending] = useState(false)
  const [terminalError, setTerminalError] = useState<string | null>(null)

  // V2.2.0 T05：事实理由增量流 / 实时 fact.done 冒泡 / SSE 断连状态
  const [reasons, setReasons] = useState<Record<string, string>>({})
  const [liveFacts, setLiveFacts] = useState<string[]>([])
  const [factDone, setFactDone] = useState<Record<string, LiveFactDone>>({})
  const [streamEnded, setStreamEnded] = useState(false)
  // V2.2.0 T06：终态发布的 artifact 相对路径（output/<file>.docx/pdf）
  const [publishedDocxPath, setPublishedDocxPath] = useState<string | null>(null)
  const [publishedPdfPath, setPublishedPdfPath] = useState<string | null>(null)
  // 已在权威快照 reasons 中出现过的 fact_id（全量理由已由快照兜底，增量应停止追加）
  const authoritativeReasonIdsRef = useRef<Set<string>>(new Set())

  // 去重/时序 refs
  const lastSeenSeqRef = useRef(-1)
  const inputRef = useRef(input)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const inFlightRef = useRef(false)
  const loadingRef = useRef(true)
  const saveFnRef = useRef<((t: TaskInput) => Promise<void>) | null>(null)
  // V2.2.0 R3-§7：权威任务 id 的 ref 镜像。generate() 的 finally 对账与 refresh 必须读取它，
  // 避免闭包捕获的 taskId 在点击生成时仍为 null（过期闭包 → refresh 空操作 → 前端永远
  // 学不到后端终态）。凡 setTaskId 处同步维护。
  const taskIdRef = useRef<string | null>(null)
  // V2.2.0 R3-§7：生成期间同步门禁 ref。预防 750ms 预填自动保存 debounce 在生成已启动后
  // in-flight 再创建孤儿 DRAFT 任务并顶掉 lastTaskId（导致终态后 restore 到 DRAFT）。
  const generatingRef = useRef(false)

  useEffect(() => {
    inputRef.current = input
  }, [input])

  const dirty = useMemo(
    () => JSON.stringify(input) !== JSON.stringify(confirmed),
    [input, confirmed],
  )

  const persistTaskId = useCallback((id: string | null) => {
    if (id) sessionStorage.setItem(TASK_STORAGE_KEY, id)
    else sessionStorage.removeItem(TASK_STORAGE_KEY)
  }, [])

  /** 用后端权威视图更新状态（恢复 / 保存 / SSE 快照共用）。 */
  const applyView = useCallback((t: TaskOut) => {
    setTaskId(t.task_id)
    taskIdRef.current = t.task_id
    setStatus(t.status)
    setSnapshotPhase(t.snapshot?.phase ?? '')
    setSnapshotPayload(t.snapshot?.payload ?? null)
    // V2.2.0 T08：终态错误码（FAILED/CANCELLED 稳定 code；成功为空）
    setTerminalError(t.terminal_error || null)
    // V2.2.0 T06：终态发布的 artifact 路径（仅 SUCCEEDED 后非空；空 = 该 artifact 不可用）
    setPublishedDocxPath(t.published_docx_path || null)
    setPublishedPdfPath(t.published_pdf_path || null)
    // V2.2.0 T05：权威快照的 reasons 以全量文本覆盖增量累积，并标记已兜底（该 fact 停止 delta 追加）
    const payload = t.snapshot?.payload
    if (payload && typeof payload === 'object' && payload.reasons != null && typeof payload.reasons === 'object') {
      const rm = payload.reasons as Record<string, unknown>
      const settled: Record<string, string> = {}
      for (const [k, v] of Object.entries(rm)) {
        if (typeof v === 'string' && v.length > 0) {
          settled[k] = v
        }
      }
      const settledIds = Object.keys(settled)
      if (settledIds.length > 0) {
        setReasons((prev) => ({ ...prev, ...settled }))
        for (const id of settledIds) authoritativeReasonIdsRef.current.add(id)
      }
    }
    // ~ 刷新/恢复时用后端 latest_input 覆盖本地；仅在未开始编辑时应用输入
    if (loadingRef.current) {
      setConfirmed((prev) => ({ ...prev, ...(t.latest_input ?? EMPTY_TASK_INPUT) }))
      setInput(t.latest_input ?? EMPTY_TASK_INPUT)
    } else if (t.latest_input) {
      setConfirmed(t.latest_input)
    }
    if (typeof t.seq === 'number' && t.seq > lastSeenSeqRef.current) {
      lastSeenSeqRef.current = t.seq
    }
  }, [])

  const refresh = useCallback(async () => {
    const id = taskIdRef.current
    if (!id) return
    try {
      const t = await taskApi.get(id)
      const confirmedNow = t.latest_input ?? confirmed
      applyView({ ...t, latest_input: confirmedNow })
    } catch (e) {
      // 读取失败不打断编辑；保留输入
      setSaveError(toError(e))
    }
  }, [applyView, confirmed])

  // V2.2.0 R3-§7：生成后的有界终态对账（终态收敛保险）。
  // 生成请求抛错/断流或 SSE 未订阅时，前端可能停在 DRAFT/READY 而学不到后端 FAILED。
  // 此处以权威 GET 轮询直到终止态（≤90s），对成功/常规流程幂等（SSE 也走同一 applyView）。
  const reconcileTerminal = useCallback(async () => {
    const id = taskIdRef.current
    if (!id) return
    const deadline = Date.now() + 90_000
    while (Date.now() < deadline) {
      let t: TaskOut
      try {
        t = await taskApi.get(id)
      } catch {
        return
      }
      if (t.status === 'FAILED' || t.status === 'SUCCEEDED' || t.status === 'CANCELLED') {
        applyView(t)
        return
      }
      applyView(t) // 顺带推进 RUNNING 快照，不阻断
      await new Promise((r) => setTimeout(r, 1500))
    }
  }, [applyView])

  // —— 挂载恢复（权威 GET；不重复触发生成） ——
  const restore = useCallback(async () => {
    const id = sessionStorage.getItem(TASK_STORAGE_KEY)
    if (!id) {
      setLoadState('ready')
      return
    }
    setLoadState('loading')
    setLoadError(null)
    loadingRef.current = true
    try {
      const t = await taskApi.get(id)
      if (!t || !t.task_id) {
        persistTaskId(null)
        setLoadState('ready')
        return
      }
      applyView(t)
      setLoadState('ready')
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        persistTaskId(null)
        taskIdRef.current = null
        setLoadState('ready')
      } else {
        setLoadError(toError(e))
        setLoadState('error')
      }
    } finally {
      loadingRef.current = false
    }
  }, [applyView, persistTaskId])

  useEffect(() => {
    void restore()
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [restore])

  // —— 保存（仅在 DRAFT；后端确认后才视为已保存）——
  const commitSave = useCallback(
    async (targetInput: TaskInput) => {
      let id = taskId
      if (!id) {
        // V2.2.0 R3-§7：生成已启动期间，禁止自动保存再创建孤儿任务（避免顶掉 lastTaskId）。
        if (generatingRef.current) return
        try {
          const created = await taskApi.create(newOperationId())
          id = created.task_id
          taskIdRef.current = id
          setTaskId(id)
          setStatus(created.status)
          persistTaskId(id)
        } catch (e) {
          setSaveError(toError(e))
          return
        }
      }
      if (status !== null && status !== 'DRAFT') {
        // 非 DRAFT 不可编辑保存（已冻结），仅确认状态
        setConfirmed(targetInput)
        return
      }
      inFlightRef.current = true
      setSaving(true)
      setSaveError(null)
      try {
        const t = await taskApi.save(id, targetInput, newOperationId())
        const saved = t.latest_input ?? targetInput
        setConfirmed(saved)
        setInput(saved)
        setStatus(t.status)
        setSnapshotPhase(t.snapshot?.phase ?? '')
        if (typeof t.seq === 'number' && t.seq > lastSeenSeqRef.current) lastSeenSeqRef.current = t.seq
      } catch (e) {
        setSaveError(toError(e))
      } finally {
        inFlightRef.current = false
        setSaving(false)
      }
      // 保存期间若有更新输入，继续补一次
      if (JSON.stringify(inputRef.current) !== JSON.stringify(targetInput)) {
        if (timerRef.current) clearTimeout(timerRef.current)
        timerRef.current = setTimeout(() => {
          void saveFnRef.current?.(inputRef.current)
        }, 750)
      }
    },
    [taskId, status, persistTaskId],
  )

  useEffect(() => {
    saveFnRef.current = commitSave
  })

  const doSave = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = null
    // 姓名未填无法通过后端校验：诚实保持未保存，不反复打断输入
    if (!inputRef.current.name.trim()) return
    void commitSave(inputRef.current)
  }, [commitSave])

  const saveNow = useCallback(() => {
    void doSave()
  }, [doSave])

  const setInputField = useCallback(
    (key: keyof TaskInput, value: string) => {
      setInput((prev) => {
        const next = { ...prev, [key]: value }
        inputRef.current = next
        return next
      })
      setSaveError(null)
      setGenerateError(null)
      if (timerRef.current) clearTimeout(timerRef.current)
      // 仅 DRAFT / 尚未建任务时自动保存；其余状态（已冻结）输入只读，不触发
      if (status === null || status === 'DRAFT') {
        timerRef.current = setTimeout(() => doSave(), 750)
      }
    },
    [status, doSave],
  )

  // —— 生成（冻结→启动→异步生成；SSE 随后接管）——
  const generate = useCallback(async () => {
    if (generatePending) return
    // V2.2.0 R3-§7：点击生成即停止预填自动保存（debounce）。
    // 否则它会在生成已建立的 RUNNING 任务之外，异步再造一个孤儿 DRAFT 任务并覆写
    // lastTaskId，导致刷新/恢复时 restore 到 DRAFT 而看不到 FAILED 终态面板。
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    setGenerateError(null)
    setGeneratePending(true)
    generatingRef.current = true
    try {
      let id = taskId
      if (!id) {
        const created = await taskApi.create(newOperationId())
        id = created.task_id
        setTaskId(id)
        taskIdRef.current = id
        persistTaskId(id)
      } else {
        // 既有任务也可能被清除前的 debounce 竞态顶掉 lastTaskId；
        // 以本次生成任务为权威 current，确保终态后刷新 restore 到正确的任务。
        taskIdRef.current = id
        persistTaskId(id)
      }
      const finalInput = inputRef.current
      if (!finalInput.name.trim()) {
        setGenerateError('请填写姓名。')
        return
      }
      if (finalInput.jd.trim().length < 60) {
        setGenerateError('请粘贴包含职责与任职要求的完整 JD（至少 60 字）。')
        return
      }
      // 1) 保存草稿（仅 DRAFT 可保存）
      if (status === null || status === 'DRAFT') {
        const saved = await taskApi.save(id, finalInput, newOperationId())
        setConfirmed(saved.latest_input ?? finalInput)
      }
      // 2) 冻结 → 3) 启动 → 4) 生成
      if (status === null || status === 'DRAFT') {
        await taskApi.freeze(id, finalInput, newOperationId())
      }
      await taskApi.start(id, newOperationId())
      const run = await taskApi.generate(id, newOperationId())
      setConfirmed(finalInput)
      applyView(run)
    } catch (e) {
      setGenerateError(toError(e))
    } finally {
      setGeneratePending(false)
      generatingRef.current = false
      // V2.2.0 R3-§7：生成请求抛错/断流时，必须以权威后端终态为准做对账。
      // DEAD/不可达 provider 下 generate 请求可能同步抛错而任务后端已 FAILED；
      // 若不收敛，前端 status 停在 DRAFT/READY，永不渲染 .wb-failed 终态面板。
      // 有界终态轮询（而非单次 refresh）：覆盖 generate 抛错/SSE 未订阅的全部分支。
      void reconcileTerminal()
    }
  }, [taskId, status, generatePending, persistTaskId, applyView, refresh, reconcileTerminal])

  // —— 取消（仅 RUNNING/CANCELLING）——
  const cancel = useCallback(async () => {
    if (!taskId) return
    try {
      const t = await taskApi.cancel(taskId, newOperationId())
      applyView(t)
    } catch (e) {
      setGenerateError(toError(e))
    }
  }, [taskId, applyView])

  // —— 「只重试失败范围」续试（仅 FAILED；创建新 task_id，复用已完成、仅重跑失败范围）——
  const continueScope = useCallback(async () => {
    if (!taskId || status !== 'FAILED') return
    if (generatePending) return
    setGenerateError(null)
    setGeneratePending(true)
    try {
      const t = await taskApi.continue(taskId, newOperationId())
      setTaskId(t.task_id)
      persistTaskId(t.task_id)
      applyView(t)
    } catch (e) {
      setGenerateError(toError(e))
    } finally {
      setGeneratePending(false)
    }
  }, [taskId, status, generatePending, persistTaskId, applyView])

  // —— SSE 只读订阅（run 期间；重连幂等，绝不触发生成）——
  useEffect(() => {
    if (!taskId || status !== 'RUNNING') return
    const es = new EventSource(taskApi.streamUrl(taskId))
    let closed = false
    const close = () => {
      if (!closed) {
        closed = true
        es.close()
      }
    }
    const parse = <T,>(e: Event): T => JSON.parse((e as MessageEvent).data) as T

    es.addEventListener('event', (e) => {
      const d = parse<TaskSseEvent>(e)
      if (d.seq > lastSeenSeqRef.current) {
        lastSeenSeqRef.current = d.seq
        if (d.phase) setSnapshotPhase(d.phase)
      }
      // V2.2.0 T05：事实理由增量流与 fact.done 冒泡（仅 P3）
      if (d.phase === 'P3' && d.type === 'reason.delta') {
        const fid = d.payload?.fact_id as string | undefined
        const delta = d.payload?.delta as string | undefined
        if (typeof fid === 'string' && typeof delta === 'string') {
          // 快照已含全量理由 → 停止增量追加，避免与全量文本重复拼接
          if (authoritativeReasonIdsRef.current.has(fid)) return
          setReasons((prev) => ({ ...prev, [fid]: (prev[fid] ?? '') + delta }))
        }
      }
      if (d.phase === 'P3' && d.type === 'fact.done') {
        const p = d.payload
        const fid = p?.fact_id as string | undefined
        if (typeof fid === 'string') {
          setLiveFacts((prev) => (prev.includes(fid) ? prev : [...prev, fid]))
        }
        const headline = p?.headline as string | undefined
        const body = p?.body as string | undefined
        if (typeof fid === 'string' && typeof headline === 'string' && typeof body === 'string') {
          const refs = Array.isArray(p.fact_refs) ? (p.fact_refs as string[]) : []
          setFactDone((prev) => ({
            ...prev,
            [fid]: { experience_id: p.experience_id as string | undefined, headline, body, fact_refs: refs },
          }))
        }
      }
    })
    es.addEventListener('snapshot', (e) => {
      const d = parse<TaskSseSnapshot>(e)
      if (d.seq > lastSeenSeqRef.current) lastSeenSeqRef.current = d.seq
      if (d.phase) setSnapshotPhase(d.phase)
      void refresh()
    })
    es.addEventListener('refetch', () => {
      void refresh()
    })
    es.addEventListener('done', (e) => {
      const d = parse<TaskSseDone>(e)
      setStreamEnded(true)
      close()
      if (d.status) refresh()
    })
    es.onopen = () => {
      void refresh()
    }
    es.onerror = () => {
      // 断流/缺口：如实标记并关闭连接，再做幂等的权威快照 re-poll 恢复
      // （refresh 仅 GET 权威快照并 applyView，不触发生成，保证增量 0 不变）
      setStreamEnded(true)
      close()
      void refresh()
    }
    return close
  }, [taskId, status, refresh])

  const startNewTask = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    persistTaskId(null)
    setTaskId(null)
    taskIdRef.current = null
    setStatus(null)
    setInput(EMPTY_TASK_INPUT)
    setConfirmed(EMPTY_TASK_INPUT)
    setSnapshotPhase('')
    setSnapshotPayload(null)
    setPublishedDocxPath(null)
    setPublishedPdfPath(null)
    setGenerateError(null)
    setSaveError(null)
    setTerminalError(null)
    loadingRef.current = false
  }, [persistTaskId])

  // V2.2.0 T05：切换任务时重置理由增量流 / 实时事实 / 断连标记
  useEffect(() => {
    setReasons({})
    setLiveFacts([])
    setFactDone({})
    setStreamEnded(false)
    authoritativeReasonIdsRef.current.clear()
  }, [taskId])

  const stepStates = useMemo(() => computeStepStates(status, snapshotPhase), [status, snapshotPhase])
  const routingPage = useMemo(() => pageForStatus(status, snapshotPhase), [status, snapshotPhase])

  const value = useMemo<WorkbenchTaskValue>(
    () => ({
      taskId,
      status,
      input,
      snapshotPhase,
      snapshotPayload,
      loadState,
      loadError,
      saving,
      dirty,
      saveError,
      generateError,
      generatePending,
      terminalError,
      stepStates,
      reasons,
      liveFacts,
      factDone,
      streamEnded,
      publishedDocxPath,
      publishedPdfPath,
      routingPage,
      setInputField,
      saveNow,
      generate,
      cancel,
      continueScope,
      retryLoad: () => void restore(),
      startNewTask,
    }),
    [taskId, status, input, snapshotPhase, snapshotPayload, loadState, loadError, saving,
     dirty, saveError, generateError, generatePending, terminalError, stepStates, reasons, liveFacts,
     factDone, streamEnded, publishedDocxPath, publishedPdfPath, routingPage, setInputField,
     saveNow, generate, cancel, continueScope, restore, startNewTask],
  )

  return <WorkbenchTaskContext.Provider value={value}>{children}</WorkbenchTaskContext.Provider>
}

export function useWorkbenchTask(): WorkbenchTaskValue {
  const ctx = useContext(WorkbenchTaskContext)
  if (!ctx) throw new Error('useWorkbenchTask 必须在 <WorkbenchTaskProvider> 内使用')
  return ctx
}