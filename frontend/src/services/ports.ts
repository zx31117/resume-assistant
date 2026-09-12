/**
 * V2.1.0 typed frontend service 端口契约（PLAN §6.3）。
 *
 * 页面与组件只依赖本文件声明的端口；Real API、测试 Mock 与设计 fixture
 * 实现同一契约。端口方法签名直接复用 ../api/types 的 wire 类型，不建立
 * 第二套领域类型真源。
 *
 * 错误语义：所有端口方法在请求失败、响应解析失败或响应不合法时 reject
 * （ApiError / 类型断言由实现负责），调用方进入 Error/Blocked；普通运行
 * 模式不得自动 fallback 到 Mock 或假数据。
 */
import type {
  ConfigSnapshot,
  ConnectionConfigRequest,
  ConnectionTestResponse,
  DiagnosticsResponse,
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
} from '../api/types'

export interface ResumeServicePort {
  generateDocx(req: ResumeDocxGenerateRequest, operationId?: string): Promise<ResumeDocxGenerateResponse>
  uploadPdf(file: File): Promise<ResumeTextOut>
}

export interface ExperienceServicePort {
  list(): Promise<ExperienceOut[]>
  create(data: ExperienceItem, operationId?: string, groupId?: string): Promise<ExperienceOut>
  update(id: string, data: ExperienceItem, operationId?: string): Promise<ExperienceOut>
  remove(id: string, operationId?: string): Promise<{ ok: boolean }>
  extract(req: ExtractRequest, operationId?: string): Promise<ExtractResponse>
}

export interface JdServicePort {
  analyze(req: JDRequest): Promise<JDAnalysis>
}

export interface TemplateServicePort {
  list(): Promise<TemplateListResponse>
}

export interface ConfigServicePort {
  snapshot(): Promise<ConfigSnapshot>
  test(req: ConnectionConfigRequest): Promise<ConnectionTestResponse>
  activate(req: ConnectionConfigRequest): Promise<ConfigSnapshot>
}

export interface SystemServicePort {
  status(): Promise<SystemStatus>
  migrate(operationId?: string): Promise<OperationResult>
  rebuild(operationId?: string): Promise<OperationResult>
  retry(operationId?: string): Promise<OperationResult>
  listOperations(params?: { status?: string; operation_type?: string; limit?: number }): Promise<OperationsListResponse>
  getOperation(operationId: string): Promise<OperationDetailResponse>
  readLogs(afterSeq?: number, limit?: number): Promise<LogsResponse>
  diagnostics(operationId: string): Promise<DiagnosticsResponse>
  clearLogs(): Promise<{ ok: boolean }>
}

/** 应用级服务聚合：单一注入点。 */
export interface AppServices {
  resume: ResumeServicePort
  experience: ExperienceServicePort
  jd: JdServicePort
  template: TemplateServicePort
  config: ConfigServicePort
  system: SystemServicePort
}
