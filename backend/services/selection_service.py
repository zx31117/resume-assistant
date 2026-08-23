"""V1.5.0 T4：两层选材与 SelectedEvidenceSet（PLAN §4.2 / §4.3 / §5）。

两层决策严格分离（PLAN §2 / §5.3）：
- 第一层 select_experiences：固定槽位规则产出 CandidateExperienceSet（经历名单）
  - 工作/实习最近最多 3 次（倒序，在职=最新，缺位不补）
  - 项目/论文同一池，三年窗口内按 JD 相关性最多 2 项（缺位不补）
  - 前两类合计 <2 时补 1 项校园；无校园素材保持缺失+告警
  - 名单形成后后续阶段不得改变
- 第二层 select_evidence：只在入选经历中选择 fact_refs + expression_focus
  - 用 embedding_service.query_facts 做 Fact 级语义选材
  - fact_refs 带 revision/hash，过期可核对
  - 不改变经历名单，不写回事实

确定性规则（PLAN §5.1.6）：日期解析、相关性评分由本模块固化为确定性实现，
不依赖旧 Chroma/numpy+JSON 向量后端；质量不作为 V1.5 PASS 条件（§8.4）。
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from core.errors import ContentGenerationError, VectorIndexNotReadyError
from database.models import Experience, Fact
from services import embedding_service, fact_service

logger = logging.getLogger(__name__)

# 固定规则版本（变化即令旧 SelectedEvidenceSet 过期）
RULE_VERSION = "v1.5.0-slot-rules-v1"
# 三年窗口（日历年）
_WINDOW_YEARS = 3
# 槽位上限
_MAX_WORK = 3
_MAX_PROJECT = 2
_MIN_COMBINED_FOR_CAMPUS = 2  # 工作实习+项目论文合计少于该值才触发校园补位
_MAX_CAMPUS = 1

_IN_PROGRESS_TOKENS = {"至今", "present", "now", "current", "current", "至今"}
_DATE_RE = re.compile(r"(\d{4})[\.\-/年](\d{1,2})?")


# ── 日期解析（确定性，PLAN §5.1.6） ────────────────────────────── #

def _parse_date_part(part: str) -> Optional[tuple[int, int]]:
    """解析 'YYYY.MM' / 'YYYY年MM月' / 'YYYY' → (year, month)。无法解析返回 None。"""
    if not part:
        return None
    m = _DATE_RE.search(part.strip())
    if not m:
        return None
    year = int(m.group(1))
    month = int(m.group(2)) if m.group(2) else 1
    if month < 1 or month > 12:
        month = 1
    return (year, month)


def _to_ordinal(year_month: Optional[tuple[int, int]]) -> Optional[int]:
    """(year, month) → 可比较整数序值 (year*12 + month)。None 不可比较。"""
    if year_month is None:
        return None
    y, mo = year_month
    return y * 12 + mo


def parse_experience_time(time_str: str) -> dict:
    """解析 Experience.time 字符串为结构化日期。

    支持格式：'2023.01-2024.06' / '2023.01-至今' / '2023.01' / ''。
    返回 {start: (y,m)|None, end: (y,m)|None, in_progress: bool, parseable: bool}。
    """
    s = (time_str or "").strip()
    if not s:
        return {"start": None, "end": None, "in_progress": False, "parseable": False}

    # 分隔起止：取第一个 '-' 或 '至' 或 '~'
    parts = re.split(r"[-–—~至]", s, maxsplit=1)
    start_part = parts[0].strip()
    end_part = parts[1].strip() if len(parts) > 1 else ""

    start = _parse_date_part(start_part)
    in_progress = False
    end = None
    if end_part:
        low = end_part.lower()
        if low in _IN_PROGRESS_TOKENS or "至今" in end_part or "现在" in end_part:
            in_progress = True
        else:
            end = _parse_date_part(end_part)
    elif start is not None and not end_part:
        # 只有起始无结束 → 视为在职（PLAN §5.1.2 在职=最新）
        in_progress = True

    parseable = start is not None
    return {"start": start, "end": end, "in_progress": in_progress, "parseable": parseable}


# ── 相关性评分（确定性，不依赖旧向量后端） ────────────────────── #

def _jd_term_pool(jd_analysis: dict) -> set[str]:
    """JD 技能/关键词池（小写化）。"""
    pool: set[str] = set()
    for key in ("required_skills", "preferred_skills", "keywords", "responsibilities"):
        for item in (jd_analysis.get(key) or []):
            t = (item or "").strip().lower()
            if len(t) >= 2:
                pool.add(t)
    pos = (jd_analysis.get("position") or "").strip().lower()
    if pos:
        pool.add(pos)
    return pool


def _exp_terms(exp: Experience) -> set[str]:
    """经历可匹配术语（skills + title + role，小写化）。"""
    terms: set[str] = set()
    for s in (exp.skills or []):
        t = (s or "").strip().lower()
        if len(t) >= 2:
            terms.add(t)
    for fld in (exp.title, exp.role):
        t = (fld or "").strip().lower()
        if len(t) >= 2:
            terms.add(t)
    return terms


def score_relevance(exp: Experience, jd_analysis: dict) -> float:
    """确定性相关性评分（Jaccard + 子串弱匹配），0-1。

    不调用 LLM/Embedding，不依赖旧向量后端（PLAN §5.1.6）。
    同分时由调用方按时间倒序决断。
    """
    exp_t = _exp_terms(exp)
    jd_t = _jd_term_pool(jd_analysis)
    if not exp_t or not jd_t:
        return 0.0
    exact = len(exp_t & jd_t)
    sub = 0
    for e in exp_t:
        for j in jd_t:
            if e != j and (e in j or j in e):
                sub += 0.5
                break
    union = len(exp_t | jd_t)
    if union == 0:
        return 0.0
    return min(1.0, (exact + sub) / union)


def _jd_hash(jd_analysis: dict) -> str:
    """JD 快照哈希（稳定排序后 sha256）。"""
    raw = json.dumps(jd_analysis, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ── 数据结构 ──────────────────────────────────────────────────── #

@dataclass
class ExperienceSlot:
    experience_id: str
    slot_type: str   # work | project | campus
    slot_rank: int
    selection_basis: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CandidateExperienceSet:
    """第一层结果（PLAN §4.2）。名单形成后不得改变。"""
    generation_baseline_date: str
    rule_version: str
    slots: list[ExperienceSlot] = field(default_factory=list)
    excluded_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "generation_baseline_date": self.generation_baseline_date,
            "rule_version": self.rule_version,
            "slots": [s.to_dict() for s in self.slots],
            "excluded_ids": list(self.excluded_ids),
            "warnings": list(self.warnings),
        }

    def selected_ids(self) -> list[str]:
        return [s.experience_id for s in self.slots]

    def slot_for(self, experience_id: str) -> Optional[ExperienceSlot]:
        for s in self.slots:
            if s.experience_id == experience_id:
                return s
        return None


@dataclass
class FactRef:
    fact_id: str
    revision: int
    content_hash: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EvidenceEntry:
    experience_id: str
    slot_type: str
    slot_rank: int
    fact_refs: list[FactRef] = field(default_factory=list)
    selection_reason: str = ""
    expression_focus: str = ""
    scores: dict = field(default_factory=dict)
    source_text: str = ""

    def to_dict(self) -> dict:
        return {
            "experience_id": self.experience_id,
            "slot_type": self.slot_type,
            "slot_rank": self.slot_rank,
            "fact_refs": [r.to_dict() for r in self.fact_refs],
            "selection_reason": self.selection_reason,
            "expression_focus": self.expression_focus,
            "scores": dict(self.scores),
            "source_text": self.source_text,
        }


@dataclass
class SelectedEvidenceSet:
    """第二层结果（PLAN §4.3）。可序列化、可重新核对、过期明确。"""
    selection_id: str
    jd_hash: str
    rule_version: str
    generation_baseline_date: str
    entries: list[EvidenceEntry] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "selection_id": self.selection_id,
            "jd_hash": self.jd_hash,
            "rule_version": self.rule_version,
            "generation_baseline_date": self.generation_baseline_date,
            "entries": [e.to_dict() for e in self.entries],
            "created_at": self.created_at,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    def all_fact_refs(self) -> list[FactRef]:
        refs: list[FactRef] = []
        for e in self.entries:
            refs.extend(e.fact_refs)
        return refs

    def is_expired(
        self,
        session: Session,
        current_jd_hash: Optional[str] = None,
        current_rule_version: str = RULE_VERSION,
        current_baseline_date: Optional[str] = None,
    ) -> bool:
        """核对是否过期（PLAN §4.3）。

        JD hash、rule_version、baseline_date 变化或任一 fact_ref 的 revision/hash
        与当前 Fact 不匹配 → 过期。
        """
        if current_jd_hash is not None and current_jd_hash != self.jd_hash:
            return True
        if current_rule_version != self.rule_version:
            return True
        if current_baseline_date is not None and current_baseline_date != self.generation_baseline_date:
            return True
        for ref in self.all_fact_refs():
            fact = session.get(Fact, ref.fact_id)
            if fact is None:
                return True
            if (fact.revision or 1) != ref.revision or (fact.content_hash or "") != ref.content_hash:
                return True
        return False


# ── 第一层：固定槽位选材 ──────────────────────────────────────── #

def select_experiences(
    experiences: list[Experience],
    jd_analysis: dict,
    *,
    baseline_date: Optional[date] = None,
) -> CandidateExperienceSet:
    """执行第一层固定槽位规则（PLAN §5.1）。

    - 工作/实习：最近最多 3 次（倒序，在职=最新，缺位不补）
    - 项目/论文：三年窗口内按 JD 相关性最多 2 项（缺位不补）
    - 前两类合计 <2 时补 1 项校园；无校园素材保持缺失+告警
    """
    if baseline_date is None:
        baseline_date = date.today()
    baseline_iso = baseline_date.isoformat()
    baseline_ord = baseline_date.year * 12 + baseline_date.month
    window_start_ord = (baseline_date.year - _WINDOW_YEARS) * 12 + baseline_date.month

    cset = CandidateExperienceSet(
        generation_baseline_date=baseline_iso,
        rule_version=RULE_VERSION,
    )

    work_pool: list[Experience] = []
    project_pool: list[Experience] = []
    campus_pool: list[Experience] = []

    for exp in experiences:
        t = (exp.type or "").strip().lower()
        parsed = parse_experience_time(exp.time or "")
        if t in ("work", "internship", "实习", "工作"):
            if not parsed["parseable"]:
                # W2: 缺失/不可解析日期的工作/实习从 work 槽位排除，告警与行为一致
                cset.excluded_ids.append(exp.id)
                cset.warnings.append(f"work date missing/unparseable: {exp.id}")
                continue
            work_pool.append(exp)
        elif t in ("project", "paper", "项目", "论文"):
            project_pool.append(exp)
        elif t in ("campus", "校园"):
            campus_pool.append(exp)
        elif t in ("education", "教育"):
            # R5: formal education stays in deterministic structure,
            # never enters campus pool (degree-granting education)
            pass
        else:
            # 未知类型：不计入任何槽位，告警
            cset.warnings.append(f"unknown type skip: {exp.id} type={t}")

    # ── 工作/实习：最近最多 3 次 ─────────────────────────────── #
    work_ranked = _rank_work(work_pool, baseline_ord)
    for rank, exp in enumerate(work_ranked[:_MAX_WORK], start=1):
        parsed = parse_experience_time(exp.time or "")
        basis = "in-progress(latest)" if parsed["in_progress"] else f"time desc (end={_fmt(parsed['end']) or _fmt(parsed['start'])})"
        cset.slots.append(ExperienceSlot(
            experience_id=exp.id, slot_type="work", slot_rank=rank, selection_basis=basis,
        ))
    for exp in work_ranked[_MAX_WORK:]:
        cset.excluded_ids.append(exp.id)
        cset.warnings.append(f"work slot full: {exp.id} 超出最近 {_MAX_WORK} 次")

    # ── 项目/论文：三年窗口 + 相关性最多 2 项 ────────────────── #
    project_in_window: list[tuple[float, Experience]] = []
    for exp in project_pool:
        parsed = parse_experience_time(exp.time or "")
        if not parsed["parseable"]:
            cset.excluded_ids.append(exp.id)
            cset.warnings.append(f"project date unparseable: {exp.id}")
            continue
        in_window = _project_in_window(parsed, baseline_ord, window_start_ord)
        if not in_window:
            cset.excluded_ids.append(exp.id)
            cset.warnings.append(
                f"project out of 3y window: {exp.id} time={exp.time}"
            )
            continue
        rel = score_relevance(exp, jd_analysis)
        project_in_window.append((rel, exp))

    # 相关性降序；同分时进行中视为最新，否则按结束时间倒序
    def _proj_time_key(exp: Experience) -> int:
        parsed = parse_experience_time(exp.time or "")
        if parsed["in_progress"]:
            return baseline_ord + 1  # 在进行中视为最新
        return _to_ordinal(parsed["end"]) or _to_ordinal(parsed["start"]) or 0

    project_in_window.sort(key=lambda x: (-x[0], -_proj_time_key(x[1]), x[1].id))
    for rank, (rel, exp) in enumerate(project_in_window[:_MAX_PROJECT], start=1):
        cset.slots.append(ExperienceSlot(
            experience_id=exp.id, slot_type="project", slot_rank=rank,
            selection_basis=f"relevance={rel:.3f} within 3y window",
        ))
    for rel, exp in project_in_window[_MAX_PROJECT:]:
        cset.excluded_ids.append(exp.id)
        cset.warnings.append(f"project slot full: {exp.id} relevance={rel:.3f}")

    # ── 校园补位（前两类合计 <2 才触发） ────────────────────── #
    combined = len([s for s in cset.slots if s.slot_type in ("work", "project")])
    if combined < _MIN_COMBINED_FOR_CAMPUS and campus_pool:
        # R5: campus by JD relevance + time + experience_id (not just time)
        def _campus_key(e):
            rel = score_relevance(e, jd_analysis)
            parsed = parse_experience_time(e.time or "")
            if parsed["in_progress"]:
                time_ord = baseline_ord + 1
            else:
                time_ord = _to_ordinal(parsed["end"]) or _to_ordinal(parsed["start"]) or 0
            return (-rel, -time_ord, e.id)
        campus_ranked = sorted(campus_pool, key=_campus_key)
        exp = campus_ranked[0]
        cset.slots.append(ExperienceSlot(
            experience_id=exp.id, slot_type="campus", slot_rank=1,
            selection_basis=f"campus fill (combined={combined}<{_MIN_COMBINED_FOR_CAMPUS}, relevance={score_relevance(exp, jd_analysis):.3f})",
        ))
    elif combined < _MIN_COMBINED_FOR_CAMPUS and not campus_pool:
        cset.warnings.append("campus fill triggered but no campus material; 保持缺失不生成虚构内容")

    logger.info(
        "select_experiences: baseline=%s slots=%d excluded=%d warnings=%d",
        baseline_iso, len(cset.slots), len(cset.excluded_ids), len(cset.warnings),
    )
    return cset


def _fmt(year_month: Optional[tuple[int, int]]) -> str:
    if year_month is None:
        return ""
    return f"{year_month[0]}.{year_month[1]:02d}"


def _rank_work(work_pool: list[Experience], baseline_ord: int) -> list[Experience]:
    """R5: work by end date desc; in_progress = latest; tie-break by experience_id asc."""
    def key(exp: Experience):
        parsed = parse_experience_time(exp.time or "")
        if parsed["in_progress"]:
            end_ord = baseline_ord + 1
        else:
            end_ord = _to_ordinal(parsed["end"]) or _to_ordinal(parsed["start"]) or 0
        return (-end_ord, exp.id)  # end_ord desc, id asc
    return sorted(work_pool, key=key)


def _project_in_window(parsed: dict, baseline_ord: int, window_start_ord: int) -> bool:
    """项目是否在三年窗口内（PLAN §5.1.3 / §5.1.4）。"""
    if parsed["in_progress"]:
        # 在进行中：视为截至基准日仍在窗口内
        return True
    end_ord = _to_ordinal(parsed["end"])
    start_ord = _to_ordinal(parsed["start"])
    if end_ord is not None:
        return window_start_ord <= end_ord <= baseline_ord
    if start_ord is not None:
        # 只有起始：若起始在窗口内则纳入（保守）
        return window_start_ord <= start_ord <= baseline_ord
    return False


# ── 第二层：事实与表达侧重选材 ────────────────────────────────── #

def select_evidence(
    session: Session,
    candidate_set: CandidateExperienceSet,
    jd_analysis: dict,
    *,
    embedder: Optional[callable] = None,
    top_k_facts: int = 5,
) -> SelectedEvidenceSet:
    """执行第二层事实选材（PLAN §5.2 / §4.3）。

    - 只遍历第一层入选经历（不改变名单）
    - 每个经历取其 Fact，用 embedding_service.query_facts 做语义选材
    - fact_refs 带 revision/hash，过期可核对
    - 不写回事实库
    - 嵌入未就绪时抛 VectorIndexNotReadyError（阻断生成，PLAN §8.2）
    """
    selected_ids = candidate_set.selected_ids()
    if not selected_ids:
        raise ContentGenerationError("第一层未入选任何经历，无法进行第二层选材")

    # 收集所有入选经历的 Fact
    all_facts = fact_service.list_facts_for_experiences(session, selected_ids)
    fact_id_to_exp: dict[str, str] = {}
    for f in all_facts:
        fact_id_to_exp[f.fact_id] = f.experience_id

    # 嵌入前置检查（PLAN §8.2：候选 Fact 向量必须就绪）
    candidate_fact_ids = [f.fact_id for f in all_facts]
    if candidate_fact_ids:
        embedding_service.ensure_ready(session, candidate_fact_ids)

    # 计算 JD 查询向量
    resolve = embedding_service._resolve_embedder(embedder)
    jd_query_text = " ".join([
        jd_analysis.get("position", ""),
        " ".join(jd_analysis.get("required_skills") or []),
        " ".join(jd_analysis.get("keywords") or []),
        " ".join(jd_analysis.get("responsibilities") or []),
    ]).strip()
    query_vector: list[float] = []
    if jd_query_text and all_facts:
        try:
            query_vector = resolve(jd_query_text)
        except Exception as e:
            raise ContentGenerationError(f"JD 查询向量计算失败: {e}") from e

    evidence = SelectedEvidenceSet(
        selection_id=str(uuid.uuid4()),
        jd_hash=_jd_hash(jd_analysis),
        rule_version=RULE_VERSION,
        generation_baseline_date=candidate_set.generation_baseline_date,
        created_at=datetime.utcnow().isoformat(),
    )

    # 按经历分组选材
    for slot in candidate_set.slots:
        exp_facts = [f for f in all_facts if f.experience_id == slot.experience_id]
        if not exp_facts:
            evidence.entries.append(EvidenceEntry(
                experience_id=slot.experience_id,
                slot_type=slot.slot_type,
                slot_rank=slot.slot_rank,
                selection_reason="no facts for this experience",
            ))
            continue

        ranked = embedding_service.query_facts(
            session, query_vector, [f.fact_id for f in exp_facts], top_k=top_k_facts,
        ) if query_vector else []

        # 构建 fact_refs（只引用版本匹配的 VALID 向量命中的 Fact）
        refs: list[FactRef] = []
        source_texts: list[str] = []
        scores_list: list[float] = []
        for r in ranked:
            fact = session.get(Fact, r["fact_id"])
            if fact is None:
                continue
            if (fact.revision or 1) != r["revision"]:
                continue
            refs.append(FactRef(
                fact_id=fact.fact_id,
                revision=fact.revision or 1,
                content_hash=fact.content_hash or "",
            ))
            source_texts.append(fact.text or "")
            scores_list.append(r["score"])

        # expression_focus：取 JD 关键词与最高分 Fact 的交集作为侧重（不新增事实）
        jd_terms = _jd_term_pool(jd_analysis)
        focus_terms = []
        for st in source_texts[:2]:
            for t in jd_terms:
                if t and t in (st or "").lower() and t not in focus_terms:
                    focus_terms.append(t)
        expression_focus = "、".join(focus_terms[:4]) if focus_terms else "职责与成果"

        avg_score = sum(scores_list) / len(scores_list) if scores_list else 0.0
        reason = (
            f"语义相关 top{len(refs)}，平均相似度 {avg_score:.3f}"
            if refs else "无可用向量命中，保留全部已知 Fact（粒度粗）"
        )

        # R6: 无向量命中时回退引用全部已知 Fact
        # 仅在索引健康但相关性低时触发（query_facts 健康故障已抛 RetrievalHealthError 阻断）
        # PLAN §5.2.5 / §6.1.3 粗粒度 Fact 可参与流程
        if not refs:
            for f in exp_facts:
                refs.append(FactRef(
                    fact_id=f.fact_id, revision=f.revision or 1, content_hash=f.content_hash or "",
                ))
                source_texts.append(f.text or "")

        evidence.entries.append(EvidenceEntry(
            experience_id=slot.experience_id,
            slot_type=slot.slot_type,
            slot_rank=slot.slot_rank,
            fact_refs=refs,
            selection_reason=reason,
            expression_focus=expression_focus,
            scores={"avg": round(avg_score, 4), "count": len(refs), "top": round(scores_list[0], 4) if scores_list else 0.0},
            source_text="\n".join(source_texts),
        ))

    logger.info(
        "select_evidence: selection_id=%s entries=%d fact_refs=%d",
        evidence.selection_id, len(evidence.entries), len(evidence.all_fact_refs()),
    )
    return evidence


def verify_evidence_set(
    session: Session,
    evidence_set: SelectedEvidenceSet,
    current_jd_analysis: dict,
) -> bool:
    """核对 SelectedEvidenceSet 是否仍有效（未过期）。"""
    return not evidence_set.is_expired(session, current_jd_hash=_jd_hash(current_jd_analysis))
