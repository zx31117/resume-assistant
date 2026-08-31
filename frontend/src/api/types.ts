/**
 * V2.0.0 强类型 API 契约（与 backend/api/schemas.py 对齐）。
 *
 * 仅声明类型，不承载任何业务规则；字段名与后端序列化结果一一对应。
 */

// ———— 统一错误结构（backend/core/errors.py → schemas.DomainErrorOut） ————

export interface DomainErrorBody {
  ok: false
  error_code: string
  stage: string
  message: string
  retryable: boolean
  details?: Record<string, unknown>
}

// ———— Experience（经历） ————

export interface ExperienceItem {
  type: string
  title: string
  company: string
  time: string
  role: string
  description: string
  skills: string[]
  achievements: string[]
  raw_text: string
}

export interface ExperienceOut extends ExperienceItem {
  id: string
  user_id?: string | null
  fact_count?: number
  summary_status?: 'empty' | 'pending' | 'ready' | 'failed'
}

export interface ExtractRequest {
  resume_text: string
}

export interface ExtractResponse {
  experiences: ExperienceItem[]
}

// ———— JD 分析 ————

export interface JDRequest {
  jd_text: string
}

export interface JDAnalysis {
  position: string
  industry: string
  required_skills: string[]
  preferred_skills: string[]
  responsibilities: string[]
  keywords: string[]
  experience_preferences: string[]
}

// ———— 简历上传 / 解析 ————

export interface ResumeTextOut {
  text: string
}

// ———— 核心生成（POST /api/resume/generate-docx） ————

export interface RequestProfile {
  name: string
  phone?: string
  email?: string
  location?: string | null
  target_position?: string
  summary?: string | null
}

export interface ResumeDocxGenerateRequest {
  user_id?: string | null
  template_id?: string
  jd_text: string
  profile: RequestProfile
  top_k?: number
}

export interface StageStatus {
  stage: string
  status: string
  duration_ms?: number | null
  note?: string | null
}

export interface BuildCounts {
  education: number
  work: number
  projects: number
  awards: number
  skill_groups: number
}

export interface BuildMeta {
  profile_source: string
  ai_covered_experience_ids: string[]
  fallback_sql_experience_ids: string[]
  ai_unrecognized_experience_ids: string[]
  max_items_trimmed: Record<string, string[]>
  bullet_fact_refs: Record<string, string[][]>
  fact_refs_per_experience: Record<string, string[]>
  builder_mode: string
  counts: BuildCounts
}

export interface RenderSectionItemCount {
  section_id: string
  input_items: number
  rendered_items: number
}

export interface RenderStats {
  sections: RenderSectionItemCount[]
  unreplaced_placeholders: string[]
  capacity_warnings: string[]
}

export interface ResumeDocxGenerateResponse {
  ok: true
  file_path: string
  file_name: string
  download_url: string
  stages: StageStatus[]
  matched_experience_ids: string[]
  rendered_experience_ids: string[]
  profile_source: string
  page_count?: number | null
  warnings: string[]
  build_counts: BuildCounts
  build_meta: BuildMeta
  render_stats: RenderStats
  template_id: string
}

// ———— 模板（GET /api/template/list） ————

export interface TemplateInfo {
  template_id: string
  display_name: string
  version: string
  page_limit: number
  sections: string[]
  is_default: boolean
}

export interface TemplateListResponse {
  templates: TemplateInfo[]
}

// ———— 连接配置与系统维护（V2.0.0 / PLAN §4.1） ————

export interface ConnectionConfigRequest {
  ark_base_url: string
  ark_api_key: string
  llm_model: string
  embedding_model: string
}

export interface ConnectionTestItem {
  ok: boolean
  detail: string
}

export interface ConnectionTestResponse {
  llm: ConnectionTestItem
  embedding: ConnectionTestItem
  ok: boolean
}

export interface ConfigFieldMeta {
  value: string
  source: string
  configured: boolean
}

export interface ConfigKeyMeta {
  masked: string
  source: string
  configured: boolean
}

export interface ConfigSnapshot {
  ARK_BASE_URL: ConfigFieldMeta
  LLM_MODEL: ConfigFieldMeta
  EMBEDDING_MODEL: ConfigFieldMeta
  ARK_API_KEY: ConfigKeyMeta
}

export interface SystemStatus {
  version: string
  migrations: {
    applied: string[]
    missing: string[]
    applied_count: number
  }
  counts: {
    experience: number
    fact: number
  }
  embeddings: Record<string, number>
  ready: boolean
  next_steps: string[]
}

export interface OperationResult {
  ok: boolean
  summary?: unknown
}