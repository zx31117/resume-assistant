import { api } from './client'
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
  OperationResult,
  ResumeDocxGenerateRequest,
  ResumeDocxGenerateResponse,
  ResumeTextOut,
  SystemStatus,
  TemplateListResponse,
} from './types'

export const resumeApi = {
  generateDocx(req: ResumeDocxGenerateRequest) {
    return api.post<ResumeDocxGenerateResponse>('/resume/generate-docx', req)
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

  create(data: ExperienceItem) {
    return api.post<ExperienceOut>('/experience/', data)
  },

  update(id: string, data: ExperienceItem) {
    return api.put<ExperienceOut>(`/experience/${id}`, data)
  },

  remove(id: string) {
    return api.del<{ ok: boolean }>(`/experience/${id}`)
  },

  extract(req: ExtractRequest) {
    return api.post<ExtractResponse>('/experience/extract', req)
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

  migrate() {
    return api.post<OperationResult>('/system/migrate')
  },

  rebuild() {
    return api.post<OperationResult>('/system/rebuild')
  },

  retry() {
    return api.post<OperationResult>('/system/retry')
  },
}