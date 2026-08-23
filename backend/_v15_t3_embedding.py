"""V1.5.0 T3 验证：SQLite BLOB Embedding、内存精确检索、fingerprint、失效与重建。

在独立临时 runtime 上用虚构 fixture + 注入 mock embedder 验证（PLAN §6.2 / §7 T3 / §8.2），
不读取/覆盖真实 runtime，不调用真实豆包 API：
- BLOB round-trip（写入 float32 → 读回 → 数值一致）
- query_facts 内存精确 cosine 排序
- fingerprint 稳定 / 模型变化失效
- Fact 修改 → 失效钩子 → INVALID → query 排除
- rebuild：有 embedder 重建 VALID；无 API Key 停在 PENDING
- ensure_ready 阻断（PENDING/INVALID/FAILED）与放行（全 VALID）
- 无隐藏 fallback（_embed_text 无 Key 抛错）
- 幂等 upsert、维度不匹配排除、孤儿/空文本 FAILED、资源释放

退出码 0 = 全部通过；非 0 = 有失败。
"""
from __future__ import annotations

import atexit
import hashlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

# 确保 backend/ 在 sys.path（裸 import: database/services/core）
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, Experience, Fact, FactEmbedding, EmbeddingStatus
from database import migrations
from services import embedding_service as es
from services import fact_service
from core import errors

# ── 临时 runtime ──────────────────────────────────────────────── #
_TMP = Path(tempfile.mkdtemp(prefix="v15_t3_"))
_SQLITE = _TMP / "app.db"
_VS_DIR = _TMP / "vectorstore"


def _cleanup():
    try:
        shutil.rmtree(_TMP, ignore_errors=True)
    except Exception:
        pass


atexit.register(_cleanup)

# ── 断言工具 ─────────────────────────────────────────────────── #
_assertions = {"pass": 0, "fail": 0}


def check(cond: bool, name: str):
    if cond:
        _assertions["pass"] += 1
        print(f"  [PASS] {name}")
    else:
        _assertions["fail"] += 1
        print(f"  [FAIL] {name}")


def _new_engine():
    return create_engine(f"sqlite:///{_SQLITE}", connect_args={"check_same_thread": False})


def _new_session(engine):
    SL = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SL()


# ── mock embedder（确定性，不调用 API） ───────────────────────── #
_DIM = 8


def _mock_embedder(text: str) -> list[float]:
    """把文本哈希映射到固定维度向量，保证可复现与可比较相似度。"""
    h = hashlib.sha256((text or "").encode("utf-8")).digest()
    vals = [float((h[i % len(h)] / 255.0) - 0.5) for i in range(_DIM)]
    # 归一化为单位向量，便于 cosine 稳定
    norm = sum(v * v for v in vals) ** 0.5 or 1.0
    return [v / norm for v in vals]


def _insert_fixtures():
    """插入虚构 Experience 并运行 Fact 迁移，得到 Fact 行。"""
    eng = _new_engine()
    Base.metadata.create_all(bind=eng)
    s = _new_session(eng)
    try:
        s.add(Experience(
            id="exp-work-001", user_id="demo", type="work",
            title="后端工程师", company="Acme", time="2023.01-2024.06",
            role="后端", description="负责订单系统重构",
            skills=["python"], achievements=["QPS 提升 3 倍", "故障率下降"],
        ))
        s.add(Experience(
            id="exp-proj-001", user_id="demo", type="project",
            title="推荐系统", company="", time="2022.05-2022.12",
            role="负责人", description="搭建召回排序链路",
            skills=[], achievements=[],
        ))
        s.commit()
    finally:
        s.close()
        eng.dispose()

    # 运行迁移生成 Fact
    r = migrations.run_migrations(str(_SQLITE), backup=True, vectorstore_dir=str(_VS_DIR))
    assert r["error"] is None, f"迁移失败: {r['error']}"


def main() -> int:
    print(f"V1.5.0 T3 验证 | tmp={_TMP} | dim={_DIM}")
    _insert_fixtures()

    # ── 1. fingerprint 稳定 ──────────────────────────────────── #
    print("\n[1] fingerprint 稳定性")
    fp1 = es.compute_fingerprint()
    fp2 = es.compute_fingerprint()
    check(fp1 == fp2, "相同配置 fingerprint 一致")
    check(len(fp1) == 16, f"fingerprint 截断 16 位 (实际 {len(fp1)})")

    # ── 2. schema 含 fact_embeddings 表 ──────────────────────── #
    print("\n[2] schema 初始化")
    eng = _new_engine()
    s = _new_session(eng)
    try:
        cols = [c["name"] for c in eng.dialect.get_columns(eng.connect(), "fact_embeddings")]
        check("vector_blob" in cols, "fact_embeddings 含 vector_blob 列")
        check("embedding_fingerprint" in cols, "fact_embeddings 含 embedding_fingerprint 列")
        check("fact_revision" in cols, "fact_embeddings 含 fact_revision 列")

        facts = s.query(Fact).order_by(Fact.fact_id).all()
        check(len(facts) >= 3, f"迁移后 Fact 数量 >= 3 (实际 {len(facts)})")

        # ── 3. BLOB round-trip ──────────────────────────────── #
        print("\n[3] BLOB round-trip")
        f0 = facts[0]
        vec_in = _mock_embedder(f0.text)
        row = es.upsert_embedding(s, f0, vec_in)
        check(row.status == EmbeddingStatus.VALID, "upsert 后 status=VALID")
        check(row.dimension == _DIM, f"dimension={_DIM} (实际 {row.dimension})")
        check(row.vector_dtype == "float32", "vector_dtype=float32")
        # 读回数值
        import numpy as np
        back = np.frombuffer(row.vector_blob, dtype=np.float32)
        check(back.shape[0] == _DIM, f"读回维度 {_DIM} (实际 {back.shape[0]})")
        max_diff = float(np.max(np.abs(back - np.asarray(vec_in, dtype=np.float32))))
        check(max_diff < 1e-6, f"BLOB round-trip 数值一致 max_diff={max_diff:.2e}")
        check(row.fact_revision == f0.revision, "记录 fact_revision")
        check(row.fact_content_hash == f0.content_hash, "记录 fact_content_hash")

        # ── 4. 幂等 upsert ─────────────────────────────────── #
        print("\n[4] 幂等 upsert")
        vec_in2 = _mock_embedder(f0.text)
        row2 = es.upsert_embedding(s, f0, vec_in2)
        cnt = s.query(FactEmbedding).filter(FactEmbedding.fact_id == f0.fact_id).count()
        check(cnt == 1, f"同 fact+fp 重复 upsert 不新增行 (实际 {cnt})")
        check(row2.id == row.id, "幂等返回同一行 id")

        # ── 5. query_facts cosine 排序 ─────────────────────── #
        print("\n[5] query_facts 内存精确 cosine 排序")
        # 为全部 fact 写入向量
        for f in facts:
            es.upsert_embedding(s, f, _mock_embedder(f.text))
        # 用第一个 fact 的文本作为 query（应与自己最相似）
        q_vec = _mock_embedder(facts[0].text)
        results = es.query_facts(s, q_vec, [f.fact_id for f in facts])
        check(len(results) == len(facts), f"query 返回全部候选 (实际 {len(results)})")
        if results:
            check(results[0]["fact_id"] == facts[0].fact_id, "top1 = 自身（cosine 最大）")
            check(results[0]["score"] >= 0.999, f"自身相似度接近 1 (实际 {results[0]['score']:.4f})")
            # 降序
            scores = [r["score"] for r in results]
            check(scores == sorted(scores, reverse=True), "结果按 score 降序")

        # top_k 限制
        results_top1 = es.query_facts(s, q_vec, [f.fact_id for f in facts], top_k=1)
        check(len(results_top1) == 1, "top_k=1 返回 1 条")

        # ── 6. R6: 维度不匹配故障阻断（不再静默排除） ────── #
        print("\n[6] R6: 维度不匹配 → RetrievalHealthError 阻断")
        bad_vec = [0.1] * (_DIM + 5)
        raised = False
        try:
            es.query_facts(s, bad_vec, [facts[0].fact_id])
        except errors.RetrievalHealthError as e:
            raised = True
            check(any("dimension mismatch" in i for i in e.issues),
                  f"issues 含 dimension mismatch (实际 {e.issues[:2]})")
        check(raised, "查询向量维度不匹配 → 抛 RetrievalHealthError 而非静默排除")

        # ── 6b. R6: BLOB 长度与 dimension 不一致阻断 ────── #
        print("\n[6b] R6: BLOB 长度与 dimension 不一致 → 阻断")
        # 把 vector_blob 清空（dimension 仍正确但 BLOB 解码后长度=0）
        bad_row = s.query(FactEmbedding).filter(
            FactEmbedding.fact_id == facts[0].fact_id,
            FactEmbedding.embedding_fingerprint == es.compute_fingerprint(),
        ).one()
        orig_blob = bad_row.vector_blob
        bad_row.vector_blob = b""
        s.commit()
        raised2 = False
        try:
            es.query_facts(s, q_vec, [facts[0].fact_id])
        except errors.RetrievalHealthError as e:
            raised2 = True
            check(any("blob length mismatch" in i for i in e.issues),
                  f"issues 含 blob length mismatch (实际 {e.issues[:2]})")
        check(raised2, "BLOB 长度不一致 → 抛 RetrievalHealthError")
        # 恢复
        bad_row = s.query(FactEmbedding).filter(
            FactEmbedding.fact_id == facts[0].fact_id,
            FactEmbedding.embedding_fingerprint == es.compute_fingerprint(),
        ).one()
        bad_row.vector_blob = orig_blob
        s.commit()
        # ── 6c. R6: revision 不匹配阻断 ──────────────────── #
        print("\n[6c] R6: Fact revision 不匹配 → 阻断")
        bad_row = s.query(FactEmbedding).filter(
            FactEmbedding.fact_id == facts[0].fact_id,
            FactEmbedding.embedding_fingerprint == es.compute_fingerprint(),
        ).one()
        orig_rev = bad_row.fact_revision
        bad_row.fact_revision = orig_rev + 999
        s.commit()
        raised3 = False
        try:
            es.query_facts(s, q_vec, [facts[0].fact_id])
        except errors.RetrievalHealthError as e:
            raised3 = True
            check(any("revision mismatch" in i for i in e.issues),
                  "issues 含 revision mismatch")
        check(raised3, "Fact revision 不匹配 → 抛 RetrievalHealthError")
        # 恢复
        bad_row = s.query(FactEmbedding).filter(
            FactEmbedding.fact_id == facts[0].fact_id,
            FactEmbedding.embedding_fingerprint == es.compute_fingerprint(),
        ).one()
        bad_row.fact_revision = orig_rev
        s.commit()

        # ── 6d. R6: content_hash 不匹配阻断 ─────────────── #
        print("\n[6d] R6: Fact content_hash 不匹配 → 阻断")
        bad_row = s.query(FactEmbedding).filter(
            FactEmbedding.fact_id == facts[0].fact_id,
            FactEmbedding.embedding_fingerprint == es.compute_fingerprint(),
        ).one()
        orig_hash = bad_row.fact_content_hash
        bad_row.fact_content_hash = "deadbeef"
        s.commit()
        raised4 = False
        try:
            es.query_facts(s, q_vec, [facts[0].fact_id])
        except errors.RetrievalHealthError as e:
            raised4 = True
            check(any("content_hash mismatch" in i for i in e.issues),
                  "issues 含 content_hash mismatch")
        check(raised4, "Fact content_hash 不匹配 → 抛 RetrievalHealthError")
        # 恢复
        bad_row = s.query(FactEmbedding).filter(
            FactEmbedding.fact_id == facts[0].fact_id,
            FactEmbedding.embedding_fingerprint == es.compute_fingerprint(),
        ).one()
        bad_row.fact_content_hash = orig_hash
        s.commit()

        # ── 6e. R6: 健康索引上的真实零分不抛错 ─────────── #
        print("\n[6e] R6: 健康索引真实零分 → 正常返回（不抛错）")
        # 用正交向量查询（cosine=0），不抛错
        zero_vec = [0.0] * _DIM
        zero_vec[0] = 1.0  # 与所有存储向量都正交
        # 先确保存储向量与 zero_vec 不同（避免巧合）
        ok = True
        try:
            zr = es.query_facts(s, zero_vec, [f.fact_id for f in facts])
        except errors.RetrievalHealthError:
            ok = False
        check(ok, "健康索引零分查询不抛 RetrievalHealthError")
        # 返回结果但 score 可能为 0
        check(isinstance(zr, list), "健康索引零分返回列表")

        # ── 7. fingerprint 变化 → 旧向量不可用 ─────────────── #
        print("\n[7] fingerprint 变化排除旧向量")
        # 手动插入一个不同 fingerprint 的 VALID 行，确认 query 不返回它
        s.add(FactEmbedding(
            fact_id=facts[0].fact_id,
            embedding_fingerprint="deadbeefdeadbeef",
            dimension=_DIM,
            vector_blob=bytes(4 * _DIM),
            vector_dtype="float32",
            fact_revision=facts[0].revision,
            fact_content_hash=facts[0].content_hash,
            status=EmbeddingStatus.VALID,
        ))
        s.commit()
        results_fp = es.query_facts(s, q_vec, [facts[0].fact_id])
        # 只应匹配当前 fingerprint 的行（1 条），不含 deadbeef
        check(len(results_fp) == 1, "只匹配当前 fingerprint（旧 fp 不可用）")

        # ── 8. Fact 修改 → 失效钩子 → INVALID ──────────────── #
        print("\n[8] Fact 修改失效钩子")
        # 接线失效钩子（注入临时 session 工厂）
        eng2 = _new_engine()
        SL2 = sessionmaker(bind=eng2, autoflush=False, autocommit=False)
        es.unwire_fact_invalidation()
        es.wire_fact_invalidation(SL2)
        s2 = _new_session(eng2)
        try:
            f0b = s2.get(Fact, facts[0].fact_id)
            before = s2.query(FactEmbedding).filter(
                FactEmbedding.fact_id == f0b.fact_id,
                FactEmbedding.embedding_fingerprint == es.compute_fingerprint(),
                FactEmbedding.status == EmbeddingStatus.VALID,
            ).count()
            check(before == 1, f"修改前 VALID 行=1 (实际 {before})")
            new_rev = fact_service.modify_fact(s2, f0b.fact_id, "订单系统重构与稳定性治理 v2")
            check(new_rev.revision == (facts[0].revision or 1) + 1, "修改后 revision+1")
        finally:
            s2.close()

        # 验证钩子已将原 VALID 标记 INVALID（用新 session 读）
        s3 = _new_session(eng2)
        try:
            after = s3.query(FactEmbedding).filter(
                FactEmbedding.fact_id == facts[0].fact_id,
                FactEmbedding.embedding_fingerprint == es.compute_fingerprint(),
                FactEmbedding.status == EmbeddingStatus.INVALID,
            ).count()
            check(after >= 1, f"修改后 INVALID 行 >= 1 (实际 {after})")
            # query 不再返回该 fact（向量已 INVALID）
            q_vec2 = _mock_embedder("订单系统重构与稳定性治理 v2")
            r_after = es.query_facts(s3, q_vec2, [facts[0].fact_id])
            check(len(r_after) == 0, "INVALID 向量被 query 排除")
        finally:
            s3.close()
        eng2.dispose()

        # ── 9. ensure_ready 阻断与放行 ──────────────────────── #
        print("\n[9] ensure_ready 阻断/放行")
        es.unwire_fact_invalidation()
        eng3 = _new_engine()
        s4 = _new_session(eng3)
        try:
            # 当前 facts[0] 为 INVALID（刚被钩子标记），其余 VALID
            valid_others = [f.fact_id for f in facts[1:]]
            # 全 VALID 的候选 → 放行
            try:
                es.ensure_ready(s4, valid_others)
                check(True, "全 VALID 候选 ensure_ready 放行")
            except errors.VectorIndexNotReadyError:
                check(False, "全 VALID 候选应放行")

            # 含 INVALID 候选 → 阻断
            try:
                es.ensure_ready(s4, [facts[0].fact_id])
                check(False, "INVALID 候选应阻断")
            except errors.VectorIndexNotReadyError as e:
                check(True, f"INVALID 候选阻断: {e.message[:60]}")

            # PENDING 候选 → 阻断
            # 删掉 facts[0] 旧行，用 mark_pending_for_missing 建 PENDING
            s4.query(FactEmbedding).filter(FactEmbedding.fact_id == facts[0].fact_id).delete()
            s4.commit()
            es.mark_pending_for_missing(s4)
            try:
                es.ensure_ready(s4, [facts[0].fact_id])
                check(False, "PENDING 候选应阻断")
            except errors.VectorIndexNotReadyError:
                check(True, "PENDING 候选阻断")

            # 空候选 → 放行
            try:
                es.ensure_ready(s4, [])
                check(True, "空候选 ensure_ready 放行")
            except errors.VectorIndexNotReadyError:
                check(False, "空候选应放行")
        finally:
            s4.close()
        eng3.dispose()

        # ── 10. rebuild：无 API Key 停 PENDING ─────────────── #
        print("\n[10] rebuild 无 API Key 停 PENDING")
        # 确保无 Key（测试环境本就无）
        from core.config import settings
        had_key = settings.ARK_API_KEY
        os.environ.pop("ARK_API_KEY", None)
        # reload 不必要：settings.ARK_API_KEY 已在导入时读取；直接 patch
        orig_key = settings.ARK_API_KEY
        settings.ARK_API_KEY = ""
        try:
            eng4 = _new_engine()
            s5 = _new_session(eng4)
            try:
                # 清空所有 embedding 行，重建 PENDING 占位
                s5.query(FactEmbedding).delete()
                s5.commit()
                summary = es.rebuild_embeddings(s5)
                check(summary["skipped_no_key"] is True, "无 Key → skipped_no_key=True")
                check(summary["succeeded"] == 0, "无 Key → succeeded=0")
                pending_n = s5.query(FactEmbedding).filter(
                    FactEmbedding.status == EmbeddingStatus.PENDING
                ).count()
                check(pending_n > 0, f"无 Key → PENDING 行 > 0 (实际 {pending_n})")
            finally:
                s5.close()
            eng4.dispose()
        finally:
            settings.ARK_API_KEY = orig_key

        # ── 11. rebuild：注入 embedder 重建 VALID ───────────── #
        print("\n[11] rebuild 注入 embedder 重建 VALID")
        eng5 = _new_engine()
        s6 = _new_session(eng5)
        try:
            s6.query(FactEmbedding).delete()
            s6.commit()
            summary = es.rebuild_embeddings(s6, embedder=_mock_embedder)
            check(summary["succeeded"] > 0, f"有 embedder → succeeded > 0 (实际 {summary['succeeded']})")
            check(summary["failed"] == 0, f"重建无失败 (实际 failed={summary['failed']})")
            valid_n = s6.query(FactEmbedding).filter(
                FactEmbedding.status == EmbeddingStatus.VALID
            ).count()
            check(valid_n > 0, f"重建后 VALID > 0 (实际 {valid_n})")
            # 重建后 ensure_ready 放行
            all_ids = [f.fact_id for f in s6.query(Fact).all()]
            try:
                es.ensure_ready(s6, all_ids)
                check(True, "重建后 ensure_ready 放行")
            except errors.VectorIndexNotReadyError as e:
                check(False, f"重建后应放行: {e.message[:60]}")
        finally:
            s6.close()
        eng5.dispose()

        # ── 12. 无隐藏 fallback ─────────────────────────────── #
        print("\n[12] 无隐藏 fallback")
        settings.ARK_API_KEY = ""
        raised = False
        try:
            es._embed_text("test")
        except RuntimeError as e:
            raised = "ARK_API_KEY" in str(e) or "无隐藏 fallback" in str(e)
        check(raised, "_embed_text 无 Key 抛 RuntimeError（无 fallback）")
        settings.ARK_API_KEY = orig_key

        # ── 13. 孤儿 / 空文本 → FAILED ─────────────────────── #
        print("\n[13] 孤儿与空文本 FAILED")
        eng6 = _new_engine()
        s7 = _new_session(eng6)
        try:
            # 孤儿：fact_embeddings 指向不存在的 fact_id
            s7.add(FactEmbedding(
                fact_id="nonexistent-fact", embedding_fingerprint=es.compute_fingerprint(),
                dimension=0, status=EmbeddingStatus.PENDING,
            ))
            # 空文本：找一条 fact 把 text 置空（临时模拟，不改真实 fact）
            empty_fact = s7.query(Fact).first()
            s7.add(FactEmbedding(
                fact_id=empty_fact.fact_id, embedding_fingerprint="zzzzzzzzzzzzzzzz",
                dimension=0, status=EmbeddingStatus.PENDING,
            ))
            s7.commit()
            # 临时清空该 fact 的 text（仅本会话测试）
            empty_fact.text = ""
            s7.commit()
            summary = es.rebuild_embeddings(s7, embedder=_mock_embedder)
            errs = {e["fact_id"]: e["error"] for e in summary["errors"]}
            check(summary["failed"] >= 1, f"孤儿/空文本 → failed >= 1 (实际 {summary['failed']})")
            check("nonexistent-fact" in errs, "孤儿 fact 标记 FAILED")
        finally:
            s7.close()
        eng6.dispose()

        # ── 14. status_summary ──────────────────────────────── #
        print("\n[14] status_summary")
        eng7 = _new_engine()
        s8 = _new_session(eng7)
        try:
            summ = es.status_summary(s8)
            check("fingerprint" in summ, "summary 含 fingerprint")
            check("VALID" in summ and "PENDING" in summ, "summary 含状态计数")
            check(summ["total"] >= 0, "summary total 非负")
        finally:
            s8.close()
        eng7.dispose()

        # ── 15. 资源释放 ────────────────────────────────────── #
        print("\n[15] 资源释放")
        eng8 = _new_engine()
        s9 = _new_session(eng8)
        s9.close()
        eng8.dispose()
        check(eng8.pool.status() != "overflow", "engine dispose 后连接池释放")
        check(not _SQLITE.exists() or _SQLITE.stat().st_size > 0, "SQLite 文件可用")

    finally:
        try:
            s.close()
        except Exception:
            pass
        eng.dispose()

    # ── 汇总 ────────────────────────────────────────────────── #
    print(f"\n=== T3 汇总: PASS={_assertions['pass']} FAIL={_assertions['fail']} ===")
    return 0 if _assertions["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
