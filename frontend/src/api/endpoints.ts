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