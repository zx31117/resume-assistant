"""经历检索服务（LLM 调用方 / 向量编排层）。

V1.1：多因素评分（语义 0.5 + 技能 0.3 + 岗位 0.2）+ 匹配原因生成。

边界约束：
- 本文件直接调用豆包多模态向量化 API（/embeddings/multimodal）计算 embedding。
  不使用 langchain-openai，原因：
  1. langchain-openai 会用 tiktoken 把文本编码成 token ID 再传给接口，
     豆包 API 期望接收原始字符串，导致 BadRequestError。
  2. 豆包 vision embedding 使用专属 endpoint 和请求格式，OpenAI 原生客户端不兼容。
- 向量的物理增删查委托给 vectorstore/chroma_store.py（无 LangChain）。
- 业务层（experience_service）通过本模块完成"向量写入编排"，自身不接触 LLM。

职责：
- index_experience: 计算文本 embedding → 写入 Chroma
- delete_experience: 删除向量
- retrieve: 基于 JD 分析结果做语义检索 + 多因素评分，返回 TopK 命中
"""
import json
import re
import urllib.request
import urllib.error
from typing import Optional

from core.config import settings
from vectorstore import chroma_store

# 评分权重
_W_SEMANTIC = 0.5
_W_SKILL = 0.3
_W_ROLE = 0.2


def _embed(text: str) -> list:
    """调用豆包多模态向量化接口，返回向量列表。

    API 文档：/docs/82379/1409291
    - Endpoint: POST /api/v3/embeddings/multimodal
    - 请求体: { model, encoding_format, input: [{type: "text", text: "..."}] }
    - 响应体: { data: { embedding: [...] } }  — data 是 dict，不是 list
    """
    url = f"{settings.ARK_BASE_URL}/embeddings/multimodal"
    payload = json.dumps({
        "model": settings.EMBEDDING_MODEL,
        "encoding_format": "float",
        "input": [{"type": "text", "text": text}],
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.ARK_API_KEY}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body["data"]["embedding"]
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8")[:500]
        raise RuntimeError(f"Embedding API HTTP {e.code}: {detail}") from e


def index_experience(exp_id: str, text: str, metadata: dict) -> None:
    """计算 embedding 并写入向量库。text 由业务层拼好传入。"""
    embedding = _embed(text)
    chroma_store.upsert(exp_id, embedding, text, metadata)


def delete_experience(exp_id: str) -> None:
    chroma_store.delete(exp_id)


# --------------------------------------------------------------------------- #
# 多因素评分（V1.1）
# --------------------------------------------------------------------------- #
def _score_semantic(distance: Optional[float]) -> float:
    """语义分：cosine distance → similarity，越大越相关。"""
    if distance is None:
        return 0.0
    return max(0.0, 1.0 - distance)


def _normalize_skill_terms(items: list[str]) -> set[str]:
    """将技能列表规范化为可匹配的术语集合。

    支持：
    - 中文顿号/逗号分隔（如 "Python、AI、大模型" → {"python", "ai", "大模型"}）
    - 整体字符串的子串切分（按常见分隔符和模式）
    - 去除长度 <= 1 的无意义词
    """
    terms: set[str] = set()
    for item in items:
        item = (item or "").strip().lower()
        if not item:
            continue
        # 按中文顿号、逗号、分号切分
        for part in re.split(r"[、，,；;]", item):
            part = part.strip()
            if len(part) >= 2:
                terms.add(part)
            # 对长句进一步切分：按"的""等""和"等词拆分
            if len(part) > 20:
                for sub in re.split(r"[的和与及或]", part):
                    sub = sub.strip()
                    if len(sub) >= 2:
                        terms.add(sub)
    return terms


def _score_skill(metadata: dict, jd_skills: list[str], jd_keywords: list[str]) -> float:
    """技能分：基于技能术语的 Jaccard + 子串匹配。

    评分逻辑：
    1. 从 metadata.skills 提取经历技能
    2. 从 jd_skills + jd_keywords 组合构建 JD 技能池
    3. 同时考虑精确匹配和子串匹配（如 "ai" 匹配 "ai产品"）
    """
    raw = metadata.get("skills", "")
    exp_terms: set[str] = set()
    if raw:
        for s in raw.split(","):
            s = s.strip().lower()
            if len(s) >= 2:
                exp_terms.add(s)
            # 对长技能名，也加入子串（如 "ai批改作业" 加入 "ai"）
            if len(s) > 4:
                for sub in re.findall(r"[a-z]{2,}|[\u4e00-\u9fff]{2,}", s):
                    exp_terms.add(sub)

    # JD 技能池 = required_skills 原子化 + keywords
    jd_terms = _normalize_skill_terms(jd_skills) | _normalize_skill_terms(jd_keywords)

    if not exp_terms or not jd_terms:
        return 0.0

    # 精确匹配
    exact_match = len(exp_terms & jd_terms)

    # 子串匹配（弱匹配，权重 0.5）
    substring_match = 0
    for exp_t in exp_terms:
        for jd_t in jd_terms:
            if exp_t != jd_t and (exp_t in jd_t or jd_t in exp_t):
                substring_match += 0.5
                break

    union = len(exp_terms | jd_terms)
    if union == 0:
        return 0.0

    raw_score = (exact_match + substring_match) / union
    return min(1.0, raw_score)


def _score_role(text: str, jd_keywords: list[str]) -> float:
    """岗位相关性：经历文本与 JD 关键词重合度。"""
    if not jd_keywords:
        return 0.0
    lower_text = text.lower()
    matched = sum(1 for kw in jd_keywords if kw.strip() and kw.strip().lower() in lower_text)
    return matched / len(jd_keywords)


def _build_reason(scores: dict) -> str:
    """根据评分生成自然语言匹配原因。"""
    parts: list[str] = []

    sem = scores["semantic"]
    if sem >= 0.8:
        parts.append("语义高度匹配")
    elif sem >= 0.6:
        parts.append("语义较为相关")
    else:
        parts.append("语义相关性较低")

    skill_pct = round(scores["skill"] * 100)
    parts.append(f"技能匹配 {skill_pct}%")

    role = scores["role"]
    if role >= 0.8:
        parts.append("岗位高度匹配")
    elif role >= 0.6:
        parts.append("岗位较为相关")
    else:
        parts.append("岗位相关性较低")

    return "，".join(parts) + "。"


def retrieve(
    jd_analysis: dict,
    user_id: Optional[str] = None,
    k: int = 5,
) -> list:
    """基于 JD 分析结果检索相关经历，返回多因素评分结果。

    返回格式：[{ "id": ..., "text": ..., "metadata": ..., "distance": ...,
                 "scores": {...}, "reason": "..." }, ...]
    """
    # 兼容 V1（requirements）和 V1.1（required_skills）
    required_skills = jd_analysis.get("required_skills") or jd_analysis.get("requirements") or []
    keywords = jd_analysis.get("keywords") or []
    responsibilities = jd_analysis.get("responsibilities") or []

    query = " ".join(
        [
            jd_analysis.get("position", ""),
            " ".join(required_skills),
            " ".join(keywords),
            " ".join(responsibilities),
        ]
    ).strip()

    embedding = _embed(query)
    where = {"user_id": user_id} if user_id else None

    # 多取候选（k*3）用于多因素重排序
    pool = min(k * 3, k + 10)
    res = chroma_store.query_by_embedding(embedding, n_results=pool, where=where)

    ids = (res.get("ids") or [[]])[0]
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]

    # 岗位关键词 = keywords + responsibilities（用于 role 评分）
    role_keywords = list(keywords) + list(responsibilities)

    scored: list[dict] = []
    for i, doc, meta, dist in zip(ids, docs, metas, dists):
        sem = _score_semantic(dist)
        sk = _score_skill(meta, required_skills, keywords)
        rl = _score_role(doc, role_keywords)
        final = sem * _W_SEMANTIC + sk * _W_SKILL + rl * _W_ROLE
        scores = {"semantic": round(sem, 4), "skill": round(sk, 4), "role": round(rl, 4), "final": round(final, 4)}
        scored.append({
            "id": i,
            "text": doc,
            "metadata": meta,
            "distance": dist,
            "scores": scores,
            "reason": _build_reason(scores),
        })

    # 按 final 分降序，取 TopK
    scored.sort(key=lambda x: x["scores"]["final"], reverse=True)
    return scored[:k]
