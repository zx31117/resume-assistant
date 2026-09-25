"""V1.3 统一领域异常与错误码。

规则：
- 所有关键失败（JD 分析、内容生成、索引失败等）必须抛子类，不得返回空成功；
- API Route 层捕获 DomainError，映射为统一 HTTP 4xx/5xx 响应；
- error_code 与 PLAN §4.3 保持一致；retryable 标识调用方是否可无脑重试。
"""
from __future__ import annotations

from typing import Any, Optional


class DomainError(Exception):
    """所有领域异常的基类。"""

    error_code: str = "DOMAIN_ERROR"
    stage: str = "unknown"
    retryable: bool = False
    http_status: int = 500

    def __init__(
        self,
        message: str,
        *,
        stage: Optional[str] = None,
        error_code: Optional[str] = None,
        retryable: Optional[bool] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        if stage is not None:
            self.stage = stage
        if error_code is not None:
            self.error_code = error_code
        if retryable is not None:
            self.retryable = retryable
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error_code": self.error_code,
            "stage": self.stage,
            "message": self.message,
            "retryable": self.retryable,
            "details": self.details,
        }


# ── Profile / 请求层 ──────────────────────────────────────────── #

class ProfileIncompleteError(DomainError):
    """Profile 必填字段缺失（复用 V1.2 语义，但统一为 DomainError 子类）。"""

    error_code = "PROFILE_INCOMPLETE"
    stage = "request_validation"
    retryable = False
    http_status = 400

    def __init__(self, missing_fields: list[str], profile_source: str = ""):
        super().__init__(
            f"必填 profile 字段缺失: {missing_fields}",
            details={"missing_fields": missing_fields, "profile_source": profile_source},
        )
        self.missing_fields = missing_fields
        self.profile_source = profile_source


# ── JD 分析 / LLM 层 ──────────────────────────────────────────── #

class JDValidationError(DomainError):
    """JD 分析返回 position 为空或结构严重损坏。"""

    error_code = "JD_INVALID"
    stage = "jd_analysis"
    retryable = True
    http_status = 422


class LLMOutputInvalidError(DomainError):
    """LLM 结构化输出全部校验失败且没有默认值可兜底。"""

    error_code = "LLM_OUTPUT_INVALID"
    stage = "content_generation"
    retryable = True
    http_status = 502


class ContentGenerationError(DomainError):
    """简历内容生成阶段的关键失败（无有效 bullets / 无匹配条目）。"""

    error_code = "CONTENT_GENERATION_FAILED"
    stage = "content_generation"
    retryable = True
    http_status = 502


# ── 索引 / 向量一致性 ──────────────────────────────────────────── #

class VectorIndexNotReadyError(DomainError):
    """有未完成的 PENDING / FAILED 索引任务，生成前无法保证召回完整。"""

    error_code = "VECTOR_INDEX_NOT_READY"
    stage = "index_check"
    retryable = True
    http_status = 503

    def __init__(self, message: str, *, failed_ids: Optional[list[str]] = None, pending_ids: Optional[list[str]] = None):
        super().__init__(
            message,
            details={"failed_ids": failed_ids or [], "pending_ids": pending_ids or []},
        )


class VectorIndexOperationError(DomainError):
    """单次索引写入/删除操作失败（写入 job FAILED）。"""

    error_code = "VECTOR_INDEX_OPERATION_FAILED"
    stage = "index_sync"
    retryable = True
    http_status = 502


# ── 匹配 / 构建层 ─────────────────────────────────────────────── #

class NoMatchedExperienceError(DomainError):
    """RAG 没有返回任何命中，或命中后 SQL 全部为空。"""

    error_code = "NO_MATCHED_EXPERIENCE"
    stage = "rag_match"
    retryable = False
    http_status = 422


class ResumeBuildError(DomainError):
    """ResumeBuilder 构建 ResumeDocument 失败。"""

    error_code = "BUILD_FAILED"
    stage = "resume_build"
    retryable = False
    http_status = 500


# ── 模板 / 渲染 / 保存 ────────────────────────────────────────── #

class TemplateError(DomainError):
    """模板资产缺失、样式定位错误或渲染逻辑错误。"""

    error_code = "TEMPLATE_ERROR"
    stage = "render"
    retryable = False
    http_status = 400


class FileSaveError(DomainError):
    """DOCX 本地保存失败。"""

    error_code = "FILE_SAVE_FAILED"
    stage = "save_docx"
    retryable = True
    http_status = 500



# ── V2.2.0 P0 owner / 来源完整性 / artifact 校验（PLAN Revision 3） ── #

class OwnerScopeViolationError(DomainError):
    """操作跨越 owner 边界（读取/列选/清理/下载异主或无主 LEGACY 数据）。

    Revision 3 owner 契约：本地单用户，所有 owner 限定以 current_user_id() 为准。
    对 LEGACY_UNOWNED（user_id IS NULL）与其他身份一律拒绝并隔离，不修改/不清理。
    """

    error_code = "OWNER_SCOPE_VIOLATION"
    stage = "owner_scope"
    retryable = False
    http_status = 403


class SourceContentLostError(DomainError):
    """来源完整性校验失败：source 中非空 role/degree/company/title 等字段被清空。

    P0：document_assembler 不得硬编码清空 source 非空字段；若校验发现字段丢失，
    视为结构性错误，任务 FAILED 且不发布。
    """

    error_code = "SOURCE_CONTENT_LOST"
    stage = "assembler_validation"
    retryable = False
    http_status = 500


class TemplateStructureInvalidError(DomainError):
    """模板结构校验失败（required 章节缺失 / 原型段落定位失败等），阻断发布。"""

    error_code = "TEMPLATE_STRUCTURE_INVALID"
    stage = "render_validation"
    retryable = False
    http_status = 422


class ArtifactInvalidError(DomainError):
    """artifact 可读性校验失败（已在磁盘但打开/哈希失败或内容不完整），不发布。"""

    error_code = "ARTIFACT_INVALID"
    stage = "artifact_validation"
    retryable = False
    http_status = 500


class OptionalContentAbsentError(DomainError):
    """可选内容（summary/awards/photo）校验失败：非空输入却产生了空原型/空标题。"""

    error_code = "OPTIONAL_CONTENT_ABSENT"
    stage = "assembler_validation"
    retryable = False
    http_status = 422


class AnchorUnavailableError(DomainError):
    """预览锚点不可用（无法从 Word 转换结果可靠定位），不影响 DOCX/PDF 本身。"""

    error_code = "ANCHOR_UNAVAILABLE"
    stage = "preview_anchor"
    retryable = False
    http_status = 503


class DuplicateExperienceError(DomainError):
    """创建完全重复 Experience（同 owner 精确内容键已存在）时返回的稳定明确结果。

    Revision 3 G03：同一用户下完全等价经历用确定性内容键识别；创建重复内容直接返回
    稳定 DUPLICATE_EXPERIENCE，不写入二次 Fact/Embedding。既有重复由选材层按同键去重。
    """

    error_code = "DUPLICATE_EXPERIENCE"
    stage = "experience_write"
    retryable = False
    http_status = 409


# ── V1.5.0 Fact / 迁移层 ──────────────────────────────────────── #

class FactNotFoundError(DomainError):
    """Fact 不存在（修改/引用时未找到）。"""

    error_code = "FACT_NOT_FOUND"
    stage = "fact_service"
    retryable = False
    http_status = 404


class FactModificationError(DomainError):
    """Fact 修改被拒绝（空文本、越权来源等）。"""

    error_code = "FACT_MODIFICATION_REJECTED"
    stage = "fact_service"
    retryable = False
    http_status = 400


class MigrationError(DomainError):
    """数据库迁移失败（schema 或数据迁移中途异常，可重试）。"""

    error_code = "MIGRATION_FAILED"
    stage = "migration"
    retryable = True
    http_status = 500


class MigrationRequiredError(DomainError):
    """V1.5.0：生成链路前置迁移检查未通过（facts/schema_versions 未就绪）。

    生成阻断；用户须显式运行 services.migrations.run_migrations 完成 Fact 迁移后再生成。
    """

    error_code = "MIGRATION_REQUIRED"
    stage = "migration_check"
    retryable = False
    http_status = 412


class ConcurrencyConflictError(DomainError):
    """V2.0.0：迁移/重建/重试/生成共享并发门禁被占用（拒绝并发执行，PLAN §3.3）。"""

    error_code = "OPERATION_IN_PROGRESS"
    stage = "concurrency_gate"
    retryable = True
    http_status = 409


class ConfigInvalidError(DomainError):
    """V2.0.0：连接配置候选字段缺失/非法，或测试/激活失败。"""

    error_code = "CONFIG_INVALID"
    stage = "config"
    retryable = False
    http_status = 400


class CredentialStorageError(DomainError):
    """V2.0.0：凭据库写入/删除失败，无明文降级（PLAN §3.2）。"""

    error_code = "CREDENTIAL_STORAGE_FAILED"
    stage = "credential"
    retryable = False
    http_status = 500


class RetrievalHealthError(DomainError):
    """R6: 检索健康检查失败（维度/fingerprint/revision/hash 不匹配）。

    区分健康低相关与索引/模型故障：
    - 健康索引上的真实低相关/零分 → 正常返回（不抛错）
    - 维度/fingerprint/revision/hash 故障 → 抛此错误阻断选材
    """

    error_code = "RETRIEVAL_HEALTH_ERROR"
    stage = "retrieval"
    retryable = True
    http_status = 503

    def __init__(self, message: str, *, issues: Optional[list[str]] = None):
        super().__init__(message, details={"issues": issues or []})
        self.issues = issues or []


# ── V2.0.1 诊断 API ───────────────────────────────────────────── #


class DiagnosticsError(DomainError):
    """二值诊断读取/清理接口的非业务错误基类（PLAN §7.2）。"""

    stage = "diagnostics"
    retryable = False


class DiagnosticsInvalidParamError(DiagnosticsError):
    """诊断接口参数非法（非法 UUID / 非法枚举筛选）。"""

    error_code = "DIAGNOSTICS_INVALID_PARAM"
    http_status = 400


class OperationNotFoundError(DiagnosticsError):
    """按 operation_id 未在内存或 JSONL 中找到对应操作（含已被轮转清理）。"""

    error_code = "OPERATION_NOT_FOUND"
    http_status = 404


class DiagnosticsUnavailableError(DiagnosticsError):
    """诊断摘要不可用（诊断设施降级或日志已轮转，无法从文件重建）。"""

    error_code = "DIAGNOSTICS_UNAVAILABLE"
    http_status = 404


class LogsClearError(DiagnosticsError):
    """历史日志清理失败（受保护写操作，非任意文件操作）。"""

    error_code = "LOGS_CLEAR_FAILED"
    http_status = 500
