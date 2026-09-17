import { api, operationHeaders } from './client'
import type {
  ConfigSnapshot,
  ConnectionConfigRequest,
  ConnectionTestResponse,
  ExperienceItem,
  ExperienceOut,
  ExtractRequest,
  ExtractResponse,
  JDAnalysis,
  JDRequest,
  LogsResponse,
  OperationDetailResponse,
  OperationsListResponse,
  OperationResult,
  ResumeDocxGenerateRequest,
  ResumeDocxGenerateResponse,
  ResumeTextOut,
  SystemStatus,
  TaskInput,
  TaskOut,
  TaskRecordOut,
  TemplateListResponse,
  DiagnosticsResponse,
} from './types'

export const resumeApi = {
  generateDocx(req: ResumeDocxGenerateRequest, operationId?: string) {
    return api.post<ResumeDocxGenerateResponse>(
      '/resume/generate-docx',
      req,
      operationHeaders(operationId),
    )
  },

  uploadPdf(file: File) {
    const form = new FormData()
    form.append('file', file)
    return api.postForm<ResumeTextOut>('/resume/upload', form)
  },
}

export const experienceApi = {
  list() {
    return api.get<ExperienceOut[]>('/experience/')
  },

  create(data: ExperienceItem, operationId?: string, groupId?: string) {
    return api.post<ExperienceOut>(
      '/experience/',
      data,
      operationHeaders(operationId, groupId),
    )
  },

  update(id: string, data: ExperienceItem, operationId?: string) {
    return api.put<ExperienceOut>(`/experience/${id}`, data, operationHeaders(operationId))
  },

  remove(id: string, operationId?: string) {
    return api.del<{ ok: boolean }>(`/experience/${id}`, operationHeaders(operationId))
  },

  extract(req: ExtractRequest, operationId?: string) {
    return api.post<ExtractResponse>('/experience/extract', req, operationHeaders(operationId))
  },
}

export const jdApi = {
  analyze(req: JDRequest) {
    return api.post<JDAnalysis>('/jd/analyze', req)
  },
}

export const templateApi = {
  list() {
    return api.get<TemplateListResponse>('/template/list')
  },
}

export const configApi = {
  snapshot() {
    return api.get<ConfigSnapshot>('/config')
  },

  test(req: ConnectionConfigRequest) {
    return api.post<ConnectionTestResponse>('/config/test', req)
  },

  activate(req: ConnectionConfigRequest) {
    return api.post<ConfigSnapshot>('/config/activate', req)
  },
}

export const systemApi = {
  status() {
    return api.get<SystemStatus>('/system/status')
  },

  migrate(operationId?: string) {
    return api.post<OperationResult>('/system/migrate', undefined, operationHeaders(operationId))
  },

  rebuild(operationId?: string) {
    return api.post<OperationResult>('/system/rebuild', undefined, operationHeaders(operationId))
  },

  retry(operationId?: string) {
    return api.post<OperationResult>('/system/retry', undefined, operationHeaders(operationId))
  },

  // ── V2.0.1 诊断 API（PLAN §7.2） ──
  listOperations(params?: { status?: string; operation_type?: string; limit?: number }) {
    const q = new URLSearchParams()
    if (params?.status) q.set('status', params.status)
    if (params?.operation_type) q.set('operation_type', params.operation_type)
    if (params?.limit) q.set('limit', String(params.limit))
    const qs = q.toString()
    return api.get<OperationsListResponse>(`/system/operations${qs ? `?${qs}` : ''}`)
  },

  getOperation(operationId: string) {
    return api.get<OperationDetailResponse>(`/system/operations/${operationId}`)
  },

  readLogs(afterSeq = 0, limit = 100) {
    return api.get<LogsResponse>(`/system/logs?after_seq=${afterSeq}&limit=${limit}`)
  },

  diagnostics(operationId: string) {
    return api.get<DiagnosticsResponse>(`/system/diagnostics/${operationId}`)
  },

  clearLogs() {
    return api.del<{ ok: boolean }>('/system/logs')
  },
}

/** V2.2.0 T3：Task 工作台 API。绑定真实后端 Task 契约。 */
export const taskApi = {
  create(operationId?: string) {
    return api.post<TaskOut>('/task', undefined, operationHeaders(operationId))
  },

  save(taskId: string, data: TaskInput, operationId?: string) {
    return api.put<TaskOut>(`/task/${taskId}/save`, data, operationHeaders(operationId))
  },

  freeze(taskId: string, data: TaskInput, operationId?: string) {
    return api.post<TaskOut>(`/task/${taskId}/freeze`, data, operationHeaders(operationId))
  },

  start(taskId: string, operationId?: string) {
    return api.post<TaskOut>(`/task/${taskId}/start`, undefined, operationHeaders(operationId))
  },

  generate(taskId: string, operationId?: string) {
    return api.post<TaskOut>(`/task/${taskId}/generate`, undefined, operationHeaders(operationId))
  },

  cancel(taskId: string, operationId?: string) {
    return api.post<TaskOut>(`/task/${taskId}/cancel`, undefined, operationHeaders(operationId))
  },

  /** 「只重试失败范围」：从 FAILED 源任务创建续试任务（新 task_id），复用已完成、仅重跑失败范围。 */
  continue(taskId: string, operationId?: string) {
    return api.post<TaskOut>(`/task/${taskId}/continue`, undefined, operationHeaders(operationId))
  },

  get(taskId: string) {
    return api.get<TaskOut>(`/task/${taskId}`)
  },

  records() {
    return api.get<TaskRecordOut[]>(`/task/records`)
  },

  streamUrl(taskId: string) {
    return `/api/task/${taskId}/stream`
  },
}