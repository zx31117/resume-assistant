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
