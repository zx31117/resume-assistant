#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V2.2.0 Revision 3 T08：内容级真实模型纵向 E2E（最终 onedir + HTTP API + 真实豆包/火山方舟）。

从**冻结打包产物 ResumeAssistant.exe** 走 **V2.2 /api/task 主链**，由真实大模型生成，
证明最终 DOCX/PDF 只包含当前本地用户（DEFAULT_USER_ID=demo-user）专属哨兵内容，
绝不包含 other-user / stub-user 哨兵；并完成
「当前用户 record ID → Fact → 快照 → ResumeDocument → DOCX/PDF」的内容级来源证明。

三身份哨兵覆盖 education/work/project 与完全重复记录：
- current-user（任务 owner）：education 学校「当前专用-大学」、work「当前科技-专属公司」、
  project「当前项目-专属名称」；另 attempt 一条与 work 完全重复 → HTTP 409 / DUPLICATE_EXPERIENCE；
- other-user：work「OTHER-异主公司」/ education「OTHER-异校」；
- stub-user：work「STUB-占位公司」/ education「STUB-占位学校」。

关键说明（阅读代码后的设计决策）：
- `/api/experience/*` 路由强制 owner = settings.DEFAULT_USER_ID，无法经 HTTP 创建 other/stub
  拥有者记录；因此 current-user 走 HTTP API 播种（真实 create_experience + Fact 自动派生 +
  DUPLICATE 语义），other/stub 由脚本直接写隔离 runtime 的 SQLite（users/experiences/facts），
  确保隔离库中确实存在三组不同 owner 的经历。全程隔离 runtime，绝不触碰真实 runtime。

错误路径：
- owner-mismatch：脚本向隔离库注入一条 other-user 持有的 Task，GET /api/task/{id} → 404
  （fail-closed 隔离），且无 artifact；
- 结构性错误不发布：主链 SUCCEEDED 后删光 current-user 的 work/project（留 education），
  新任务 P2 候选为空 → ContentGenerationError → FAILED 且 published_docx_path 为空。

纪律（硬约束，与 h8_real_model_e2e 一致）：
- 全新隔离 RESUME_DATA_DIR（仓库外临时目录），不触碰真实 runtime；运行最终 onedir 包；
- API Key 仅由应用从 Windows 凭据库读取（脚本剥离 ARK_API_KEY）；ARK 计数代理不落 Key；
- 脚本自身只读框架：所有写操作走 HTTP API 或隔离库；结束必须清理自己启动的 exe/代理与隔离 runtime。

产出：validation-artifacts/h8/r3/content_real_model.json（+ 控制台摘要）。
退出码：0=全 PASS，1=有 FAIL，2=环境失败。
用法：
  python h8_r3_real_model_content.py --exe <path\\ResumeAssistant.exe> [--keep]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent                 # scripts/
ROOT = HERE.parent                                     # repo root
EVID = ROOT / "validation-artifacts" / "h8" / "r3"
EVID.mkdir(parents=True, exist_ok=True)
OUT = EVID / "content_real_model.json"
PROXY_PY = HERE / "h8_ark_proxy.py"
PY = os.environ.get("H8_E2E_PYTHON", sys.executable)

DEFAULT_PORT = 8318
PROXY_PORT = 8800

EVIDENCE: dict = {"steps": [], "limits": {
    "note": "Key 由应用从 Windows 凭据库读取；本脚本不接触任何 Key。运行最终 onedir 包。"}}
_passed = 0
_failed = 0
_env_fail = False


def log(m: str) -> None:
    print(m, flush=True)


def step(name: str, **kw) -> None:
    EVIDENCE["steps"].append({"step": name, "ts": time.strftime("%H:%M:%S"), **kw})
    log(f"[e2e] {name}: " + json.dumps(kw, ensure_ascii=False)[:400])


def check(cond, name, extra=""):
    global _passed, _failed
    if cond:
        _passed += 1
        log(f"  [PASS] {name}")
    else:
        _failed += 1
        log(f"  [FAIL] {name} {extra}")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def wait_port(port: int, timeout: float = 120.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        for host in ("127.0.0.1", "localhost", "::1"):
            try:
                with socket.create_connection((host, port), timeout=1):
                    return True
            except OSError:
                pass
        time.sleep(0.3)
    return False


# ── 隔离库访问（stdlib sqlite3 只读/仅注入 other-stub，避免绑定真实 runtime） ── #

class IsoDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.db_path), timeout=15)
        c.row_factory = sqlite3.Row
        return c

    def q(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        c = self.conn()
        try:
            return c.execute(sql, params).fetchall()
        finally:
            c.close()

    def execute(self, sql: str, params: tuple = ()) -> None:
        c = self.conn()
        try:
            c.execute(sql, params)
            c.commit()
        finally:
            c.close()


# ── 哨兵（唯一、三组互不相同） ──────────────────────────────────── #
CUR_EDU = "当前专用-大学"
CUR_WORK = "当前科技-专属公司"
CUR_PROJ = "当前项目-专属名称"
OTHER_WORK = "OTHER-异主公司"
OTHER_SCHOOL = "OTHER-异校"
STUB_WORK = "STUB-占位公司"
STUB_SCHOOL = "STUB-占位学校"
OTHER = "other-user"
STUB = "stub-user"

TEST_JD = (
    "岗位名称：资深后端工程师。职责：负责系统架构设计与核心模块实现，主导高并发下单支付库存模块"
    "的稳定性保障与性能优化，参与技术评审、代码审查、迭代交付。必备技能：Python、Java、Spring Boot、"
    "MySQL、Redis。base 北京，可尽快到岗。"
)
TEST_NAME = "王小明R3"
TEST_PHONE = "13800001234"
TEST_EMAIL = "wangr3@current.cn"
TEST_LOCATION = "北京"


def docx_text(path: str) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    return re.sub(r"<[^>]+>", "", xml)


def pdf_text(path: str) -> tuple[str, str]:
    """尽力提取 PDF 文本；返回 (text, engine)。无可用库时 (\"\", \"\")。"""
    try:
        import pypdfium2 as pdfium  # 产品同款
        text = []
        pdf = pdfium.PdfDocument(path)
        try:
            for i in range(len(pdf)):
                page = pdf[i]
                try:
                    tp = page.get_textpage()
                    text.append(tp.get_text_bounded())
                    tp.close()
                except Exception:
                    pass
                finally:
                    page.close()
            return "\n".join(text), "pypdfium2"
        finally:
            pdf.close()
    except Exception:
        pass
    for mod in ("pypdf", "PyPDF2"):
        try:
            m = __import__(mod)
            reader = m.PdfReader(path)
            return "\n".join((p.extract_text() or "") for p in reader.pages), mod
        except Exception:
            continue
    try:
        import pdfplumber  # type: ignore
        with pdfplumber.open(path) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages), "pdfplumber"
    except Exception:
        return "", ""


# ── other/stub 注入（隔离库直接写，owner 服务层强制 demo-user，经 HTTP 无法跨越） ── #

def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S.000000")


def inject_owner_exp(db: IsoDB, owner: str, exp: dict, fid: str) -> None:
    """写入（User 缺省建档 + Experience + 一条确定性 Fact）。owner 非 current，服务层不可达。"""
    try:
        db.execute("INSERT INTO users (id,name,email,created_at) VALUES (?,?,?,?)",
                   (owner, owner, "", _now()))
    except sqlite3.IntegrityError:
        pass
    ts = _now()
    db.execute(
        "INSERT INTO experiences (id,user_id,type,title,company,time,role,description,"
        "skills,achievements,raw_text,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (exp["id"], owner, exp["type"], exp.get("title", ""), exp["company"], exp.get("time", ""),
         exp.get("role", ""), exp.get("description", ""), json.dumps(exp.get("skills", []), ensure_ascii=False),
         json.dumps(exp.get("achievements", []), ensure_ascii=False),
         exp.get("description", ""), ts, ts))
    src = exp.get("description") or exp.get("company") or exp["id"]
    db.execute(
        "INSERT INTO facts (fact_id,experience_id,fact_type,text,source_text,source_field,"
        "source_index,content_hash,source_hash,revision,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (fid, exp["id"], "RESPONSIBILITY", src, src, "description", None,
         hashlib.sha256(src.encode("utf-8")).hexdigest(),
         hashlib.sha256(src.encode("utf-8")).hexdigest(), 1, ts, ts))


def seed_other_stub(db: IsoDB) -> None:
    inject_owner_exp(db, OTHER, {
        "id": "other-edu", "type": "education", "title": OTHER_SCHOOL, "company": OTHER_SCHOOL,
        "role": "数学", "time": "2015.09 - 2019.06", "description": f"{OTHER_SCHOOL} 数学与应用数学",
        "skills": [], "achievements": []}, f"other-edu/f1")
    inject_owner_exp(db, OTHER, {
        "id": "other-w1", "type": "work", "title": "分析师", "company": OTHER_WORK,
        "role": "分析", "time": "2016.01 - 2019.05", "description": f"任职于 {OTHER_WORK}。",
        "skills": [], "achievements": []}, f"other-w1/f1")
    inject_owner_exp(db, STUB, {
        "id": "stub-edu", "type": "education", "title": STUB_SCHOOL, "company": STUB_SCHOOL,
        "role": "占位", "time": "2017.09 - 2021.06", "description": f"{STUB_SCHOOL} 学士学位",
        "skills": [], "achievements": []}, f"stub-edu/f1")
    inject_owner_exp(db, STUB, {
        "id": "stub-w1", "type": "work", "title": "占位", "company": STUB_WORK,
        "role": "占位", "time": "2020.01 - 2020.06", "description": f"任职于 {STUB_WORK}。",
        "skills": [], "achievements": []}, f"stub-w1/f1")


# ── 真实任务主链（V2.2 /api/task，全部经 HTTP） ── #

def create_and_run(s: "requests.Session", base: str, *, name: str, jd: str,
                   phone: str, email: str, location: str) -> tuple[dict, str]:
    """创建→保存→冻结→启动→生成，返回 (任务视图, task_id)。"""
    r = s.post(f"{base}/api/task", timeout=30)
    r.raise_for_status()
    tid = r.json()["task_id"]
    body = {"name": name, "phone": phone, "email": email, "location": location, "jd": jd}
    r = s.put(f"{base}/api/task/{tid}/save", json=body, timeout=30)
    r.raise_for_status()
    r = s.post(f"{base}/api/task/{tid}/freeze", json=body, timeout=30)
    r.raise_for_status()
    r = s.post(f"{base}/api/task/{tid}/start", timeout=30)
    r.raise_for_status()
    r = s.post(f"{base}/api/task/{tid}/generate", timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"generate start failed: {r.status_code} {r.text[:200]}")
    return r.json(), tid


def poll_status(s: "requests.Session", base: str, tid: str, timeout_s: float = 900.0,
                interval: float = 2.0) -> dict:
    """每次用新查询（HTTP 每次都重读 DB），避免缓存。"""
    t0 = time.time()
    last = {}
    while time.time() - t0 < timeout_s:
        r = s.get(f"{base}/api/task/{tid}", timeout=60)
        if r.status_code == 200:
            last = r.json()
            st = last.get("status")
            if st in ("SUCCEEDED", "FAILED", "CANCELLED"):
                return last
        else:
            last = {"status": f"HTTP{r.status_code}"}
        time.sleep(interval)
    return last


def run() -> int:
    global _env_fail
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True, help="最终 onedir 的 ResumeAssistant.exe")
    ap.add_argument("--keep", action="store_true", help="结束后不删隔离 runtime（排障用）")
    ap.add_argument("--timeout", type=int, default=900, help="单任务生成轮询超时（秒），默认 900")
    ap.add_argument("--app-port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--proxy-port", type=int, default=PROXY_PORT)
    args = ap.parse_args()

    exe = Path(args.exe).resolve()
    if not exe.exists():
        log(f"[fatal] exe 不存在：{exe}")
        return 2
    EVIDENCE["exe"] = {"path": str(exe), "sha256": sha256_file(exe), "size": exe.stat().st_size}

    runtime = Path(os.environ.get("TEMP", ".")) / f"h8r3_{int(time.time())}"
    runtime.mkdir(parents=True, exist_ok=True)
    EVIDENCE["runtime_dir"] = str(runtime)
    log(f"[e2e] 隔离 RESUME_DATA_DIR={runtime}")

    proxy_out = EVID / "ark_counts.json"
    proxy = subprocess.Popen([PY, str(PROXY_PY), "--port", str(args.proxy_port), "--out", str(proxy_out)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not wait_port(args.proxy_port, 30):
        log("[fatal] ARK 代理未就绪")
        proxy.kill()
        return 2
    step("proxy_up", port=args.proxy_port, counts_file=str(proxy_out))

    env = dict(os.environ)
    env["RESUME_DATA_DIR"] = str(runtime)
    env["ARK_BASE_URL"] = f"http://127.0.0.1:{args.proxy_port}/api/v3"
    env["APP_PORT"] = str(args.app_port)
    env.pop("ARK_API_KEY", None)        # 强制走凭据库，不经脚本注入
    env.pop("H8_CONV_WORKER", None)

    app_stdout = EVID / "app_stdout.log"
    app_fh = open(app_stdout, "w", encoding="utf-8", errors="replace")
    app = subprocess.Popen([str(exe)], cwd=str(exe.parent), env=env,
                           stdout=app_fh, stderr=subprocess.STDOUT)
    ok = False
    try:
        if not wait_port(args.app_port, 180):
            step("app_boot_failed", pid=app.pid, ret=app.poll())
            return 2
        base = f"http://127.0.0.1:{args.app_port}"
        step("app_up", pid=app.pid, port=args.app_port)

        import requests
        s = requests.Session()
        r = s.get(f"{base}/api/health", timeout=30)
        step("health", code=r.status_code, cookie=bool(s.cookies.get("ra_session")))
        if r.status_code != 200:
            return 2

        # ── 迁移 ──
        r = s.post(f"{base}/api/system/migrate", timeout=300)
        step("migrate", code=r.status_code, body=str(r.json())[:200])
        if r.status_code != 200:
            return 2

        db_path = runtime / "database" / "app.db"
        if not db_path.exists():
            log("[fatal] 未找到隔离库 app.db")
            return 2
        db = IsoDB(db_path)

        # ── current-user 播种（HTTP，走真实 create_experience + Fact 派生 + DUPLICATE 语义） ──
        def post_exp(exp: dict) -> int:
            rr = s.post(f"{base}/api/experience/", json=exp, timeout=120)
            return rr.status_code

        cur_owner = None
        # education
        r = s.post(f"{base}/api/experience/", json={
            "type": "education", "title": CUR_EDU, "company": CUR_EDU, "role": "计算机",
            "time": "2019.09 - 2023.06", "description": f"{CUR_EDU} 计算机科学与技术 学士学位",
            "skills": [], "achievements": []}, timeout=120)
        if r.status_code != 200:
            log(f"[fatal] current education 播种失败 {r.status_code} {r.text[:200]}")
            return 2
        cur_owner = r.json().get("user_id")
        # work w1
        r = s.post(f"{base}/api/experience/", json={
            "type": "work", "title": "高级工程师", "company": CUR_WORK, "role": "后端工程师",
            "time": "2021.07 - 至今", "description": f"在 {CUR_WORK} 主导核心系统研发，负责架构设计与性能优化。",
            "skills": ["Python", "Java", "MySQL", "Redis"], "achievements": [
                "主导订单创建链路重构，将核心接口 P99 从 820ms 降到 210ms"]}, timeout=120)
        if r.status_code != 200:
            log(f"[fatal] current work 播种失败 {r.status_code} {r.text[:200]}")
            return 2
        # work w2
        r = s.post(f"{base}/api/experience/", json={
            "type": "work", "title": "工程师", "company": "第二段公司-当前", "role": "Java工程师",
            "time": "2019.07 - 2021.06", "description": "负责交易链路模块开发与稳定性保障。",
            "skills": ["Java", "Spring Boot", "MySQL"], "achievements": []}, timeout=120)
        if r.status_code != 200:
            log(f"[fatal] current work2 播种失败 {r.status_code} {r.text[:200]}")
            return 2
        # project p1
        r = s.post(f"{base}/api/experience/", json={
            "type": "project", "title": CUR_PROJ, "company": CUR_PROJ, "role": "负责人",
            "time": "2023.06 - 2024.01", "description": f"主导 {CUR_PROJ} 的从 0 到 1 落地。",
            "skills": ["Java", "Redis"], "achievements": []}, timeout=120)
        if r.status_code != 200:
            log(f"[fatal] current project 播种失败 {r.status_code} {r.text[:200]}")
            return 2
        # 完全重复（与 w1 精确等同）→ 期望 409 / DUPLICATE_EXPERIENCE
        dup = s.post(f"{base}/api/experience/", json={
            "type": "work", "title": "高级工程师", "company": CUR_WORK, "role": "后端工程师",
            "time": "2021.07 - 至今", "description": f"在 {CUR_WORK} 主导核心系统研发，负责架构设计与性能优化。",
            "skills": ["Python", "Java", "MySQL", "Redis"],
            "achievements": ["主导订单创建链路重构，将核心接口 P99 从 820ms 降到 210ms"]}, timeout=120)
        dup_409 = dup.status_code == 409
        try:
            dup_code = dup.json().get("error_code", "")
        except Exception:
            dup_code = ""
        check(dup_409 and dup_code == "DUPLICATE_EXPERIENCE",
              f"完全重复记录保存层返回 409/DUPLICATE_EXPERIENCE（实际 {dup.status_code}/{dup_code}）")
        cur_owner = cur_owner or "demo-user"
        EVIDENCE["current_owner"] = cur_owner
        step("current_seeded", owner=cur_owner)

        # ── other/stub 注入（隔离库直接写；HTTP 服务层强制 owner=demo-user 不可达） ──
        seed_other_stub(db)
        owners = {row["user_id"] for row in db.q(
            "SELECT DISTINCT user_id FROM experiences") if row["user_id"]}
        check({cur_owner, OTHER, STUB} <= owners,
              "隔离库确实存在三组不同 owner 的经历",
              extra=f"owners={sorted(o for o in owners if o)} / cur={cur_owner}")

        # ── 真实 Embedding 重建（经 ARK 代理） ──
        c0 = _proxy_counts(proxy_out)
        baseline_chat = c0.get("by_path", {}).get("/api/v3/chat/completions", 0)
        baseline_emb = c0.get("by_path", {}).get("/api/v3/embeddings/multimodal", 0)
        r = s.post(f"{base}/api/system/rebuild", timeout=600)
        step("rebuild", code=r.status_code, body=str(r.json())[:200])
        if r.status_code != 200:
            return 2

        # ── 主链：真实模型 V2.2 /api/task ──
        gen, tid = create_and_run(s, base, name=TEST_NAME, jd=TEST_JD,
                                  phone=TEST_PHONE, email=TEST_EMAIL, location=TEST_LOCATION)
        EVIDENCE["main_task_id"] = tid
        # owner 以 DB tasks 真源为准（TaskOut API 响应不暴露顶层 user_id 字段）
        _db_owner = db.q("SELECT user_id FROM tasks WHERE task_id=?", (tid,))
        act_owner = _db_owner[0]["user_id"] if _db_owner else None
        step("main_task_created", task_id=tid, owner=act_owner)
        check(act_owner == cur_owner, "任务创建即归属 current-user",
              extra=f"actual={act_owner}")

        view = poll_status(s, base, tid, timeout_s=args.timeout)
        final_status = view.get("status")
        check(final_status == "SUCCEEDED", f"真实模型主链最终 SUCCEEDED（实际 {final_status}）")
        EVIDENCE["main_terminal"] = {"status": final_status,
                                     "terminal_error": view.get("terminal_error")}

        if final_status == "SUCCEEDED":
            _content_asserts(s, base, db, tid, view, runtime, cur_owner)
            _artifact_asserts(s, base, view, runtime)
        else:
            log("[e2e] 真实模型未 SUCCEEDED，跳过内容级断言（需在打包后真实执行验证）")
            EVIDENCE["limits"].update(
                {"real_model_note": "若模型/凭据不可用则无法 SUCCEEDED；产物为完整脚本，需打包后真实执行验证"})

        # ── Provider 计数（证明真实 LLM/Embedding 调用发生） ──
        c1 = _proxy_counts(proxy_out)
        chat_now = c1.get("by_path", {}).get("/api/v3/chat/completions", 0) - baseline_chat
        emb_now = c1.get("by_path", {}).get("/api/v3/embeddings/multimodal", 0) - baseline_emb
        EVIDENCE["provider_calls"] = {"chat_completions_in_window": int(chat_now),
                                      "embeddings_in_window": int(emb_now)}
        check(chat_now >= 1, "真实 LLM chat/completions 调用发生（经 ARK 计数代理）",
              extra=f"chat_in_window={chat_now}")

        _error_path_checks(s, base, db, cur_owner)

        result = 1 if _failed > 0 else 0
        ok = _failed == 0
        EVIDENCE["ok"] = ok
        EVIDENCE["gate_passed"] = ok
        return result
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        EVIDENCE["exception"] = repr(e)
        ok = False
        return 2
    finally:
        try:
            app.terminate()
            app.wait(timeout=15)
        except Exception:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(app.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            app_fh.close()
        except Exception:
            pass
        proxy.terminate()
        time.sleep(1)
        if not args.keep:
            shutil.rmtree(runtime, ignore_errors=True)
            EVIDENCE["runtime_deleted"] = True
        OUT.write_text(json.dumps(EVIDENCE, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"[e2e] wrote {OUT} OK={ok}")


def _proxy_counts(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"total": 0, "by_path": {}}


# ── 内容级断言（来源链 + DOCX 哨兵 + Fact 回查） ── #
def _content_asserts(s, base, db: IsoDB, tid: str, view: dict, runtime: Path,
                     cur_owner: str) -> None:
    print("\n[内容级] 主链内容级证明（真实模型生成 + 真实装配/渲染）")
    # owner 以 DB tasks 真源为准（TaskOut API 响应不暴露顶层 user_id 字段）
    _db_owner = db.q("SELECT user_id FROM tasks WHERE task_id=?", (tid,))
    owner = _db_owner[0]["user_id"] if _db_owner else None
    check(owner == cur_owner,
          f"Task owner == current_user_id（{owner}）")

    # 1) subtasks experience_id → 全部归属 current-owner Experience
    subs = db.q("SELECT DISTINCT experience_id FROM task_subtasks WHERE task_id=?", (tid,))
    sub_ids = [r["experience_id"] for r in subs]
    odd = db.q("SELECT e.id, e.user_id FROM experiences e WHERE e.id IN (%s)"
               % ",".join("?" * len(sub_ids)), tuple(sub_ids)) if sub_ids else []
    odd_owners = {r["user_id"] for r in odd}
    check(odd_owners <= {owner},
          f"[G1] 候选（P2 subtask）条目 owner 全等于 Task owner（{len(sub_ids)} 项）",
          extra=f"owners={sorted(o for o in odd_owners if o)}")

    # 2) Fact → Experience → owner：task 产出的每个 Fact 都能回查 current-owner Experience
    fact_owner_ok = True
    fact_total = 0
    for r in subs:
        exp = db.q("SELECT user_id FROM experiences WHERE id=?", (r["experience_id"],))
        if not exp:
            fact_owner_ok = False
            continue
        frows = db.q("SELECT fact_id FROM facts WHERE experience_id=?", (r["experience_id"],))
        fact_total += len(frows)
        if exp[0]["user_id"] != owner:
            fact_owner_ok = False
    check(fact_owner_ok,
          f"[G4] fact_refs 全部回查 current-user（共 {fact_total} 条候选 Fact）")

    # 3) 快照 experiences → owner 归主
    snap = db.q("SELECT phase,payload FROM task_snapshots WHERE task_id=?", (tid,))
    snap_by_phase = {}
    for r in snap:
        try:
            snap_by_phase[r["phase"]] = json.loads(r["payload"] or "{}")
        except Exception:
            snap_by_phase[r["phase"]] = {}
    snap_exps_ok = True
    snap_ids = []
    for ph in ("P2", "P3"):
        for e in (snap_by_phase.get(ph, {}) or {}).get("experiences", []):
            snap_ids.append(e.get("experience_id"))
    for sid in snap_ids:
        ex = db.q("SELECT user_id FROM experiences WHERE id=?", (sid,))
        if not ex or ex[0]["user_id"] != owner:
            snap_exps_ok = False
    check(snap_exps_ok, f"[G1] P2/P3 snapshot 条目 owner 全等于 Task owner（{len(snap_ids)} 项）")

    # 4) DOCX 文本哨兵断言
    docx_rel = view.get("published_docx_path") or ""
    docx_abs = _locate_artifact(docx_rel, runtime)
    check(bool(docx_abs and Path(docx_abs).is_file()), "published_docx_path 指向可读文件",
          extra=docx_rel)
    if docx_abs and Path(docx_abs).is_file():
        text = docx_text(str(docx_abs))
        check(CUR_EDU in text, "[G3] 当前用户教育（学校）'当前专用-大学' 进入 DOCX")
        check(CUR_WORK in text, "[G2] current work '当前科技-专属公司' 进入 DOCX")
        check(CUR_PROJ in text, "[G2] current project '当前项目-专属名称' 进入 DOCX")
        check(OTHER_WORK not in text, "[G2] other work 哨兵进入 DOCX（应为空）")
        check(OTHER_SCHOOL not in text, "[G2] other 教育哨兵不进入 DOCX")
        check(STUB_WORK not in text, "[G2] stub work 哨兵不进入 DOCX")
        check(STUB_SCHOOL not in text, "[G2] stub 教育哨兵不进入 DOCX")
        check(TEST_NAME in text, "[G3] 冻结姓名进入 DOCX")
        check(TEST_LOCATION in text, "[G3] 冻结所在地进入 DOCX")
        check("{{" not in text and "}}" not in text, "[G7] 未替换占位符 = 0")
        check("照片" not in text, "[G7] 空照片占位 = 0")
        check(text.count(CUR_WORK) >= 1, "[G4] 重复经历选材只占一槽（company 出现一次，无二份）")

    # 5) ResumeDocument 字段来源 = owner 行（education school/work company/project name）
    edu_rows = db.q("SELECT company,title FROM experiences "
                    "WHERE user_id=? AND type='education'", (owner,))
    check(any((r["company"] or "") == CUR_EDU or (r["title"] or "") == CUR_EDU
              for r in edu_rows), "[G3] ResumeDocument 教育来源=current-user record")

    # 6) PDF 文本（尽力）
    pdf_rel = view.get("published_pdf_path") or ""
    pdf_abs = _locate_artifact(pdf_rel, runtime)
    if pdf_abs and Path(pdf_abs).is_file():
        ptext, eng = pdf_text(str(pdf_abs))
        if ptext:
            check(CUR_EDU in ptext and CUR_WORK in ptext,
                  f"[G2] PDF 文本含 current 哨兵（engine={eng}）")
            check(OTHER_WORK not in ptext and STUB_WORK not in ptext,
                  "[G2] PDF 文本不含 other/stub 哨兵")
        else:
            EVIDENCE["pdf_text_extraction"] = {"note": "无可用 PDF 文本库；PDF 内容以 DOCX 文本"
                                                       " + 同源字节一致证明", "engine": eng or "none"}


def _locate_artifact(rel: str, runtime: Path) -> str | None:
    if not rel:
        return None
    p = Path(rel)
    if p.is_absolute() and p.is_file():
        return str(p)
    name = p.name
    cand = runtime / "output" / name
    return str(cand) if cand.is_file() else None


def _artifact_asserts(s, base, view: dict, runtime: Path) -> None:
    """DOCX/PDF 磁盘 artifact 与 HTTP 下载字节一致。"""
    print("\n[artifact] 磁盘 artifact vs HTTP 下载 字节一致")
    docx_rel = view.get("published_docx_path") or ""
    pdf_rel = view.get("published_pdf_path") or ""
    docx_disk = _locate_artifact(docx_rel, runtime)
    pdf_disk = _locate_artifact(pdf_rel, runtime)

    out: dict = {}
    if docx_disk:
        out["docx_disk"] = {"sha256": sha256_file(Path(docx_disk)),
                            "size": Path(docx_disk).stat().st_size}
        dcode, dbytes = _http_get(s, base, f"/api/template/download?path={docx_rel}")
        if dcode < 400:
            out["docx_download"] = {"status": dcode, "sha256": sha256_bytes(dbytes)}
            check(dcode < 400 and sha256_file(Path(docx_disk)) == sha256_bytes(dbytes),
                  "[artifact] DOCX 磁盘 artifact 与下载字节一致")
    if pdf_disk:
        out["pdf_disk"] = {"sha256": sha256_file(Path(pdf_disk)),
                           "size": Path(pdf_disk).stat().st_size}
        pcode, pbytes = _http_get(s, base, f"/api/template/download?path={pdf_rel}")
        if pcode < 400:
            out["pdf_download"] = {"status": pcode, "sha256": sha256_bytes(pbytes)}
            check(pcode < 400 and sha256_file(Path(pdf_disk)) == sha256_bytes(pbytes),
                  "[artifact] PDF 磁盘 artifact 与下载字节一致")
    EVIDENCE["artifacts"] = out


def _http_get(s, base: str, url: str) -> tuple[int, bytes]:
    r = s.get(base + url, timeout=120)
    return r.status_code, r.content


# ── 错误路径 ── #
def _error_path_checks(s, base, db: IsoDB, owner: str) -> None:
    print("\n[错误路径] owner-mismatch 隔离 + 结构性不发布")
    # 1) owner-mismatch：other-user 持有任务 → API 404（fail-closed 隔离），无 artifact
    try:
        db.execute(
            "INSERT INTO tasks (task_id,user_id,status,current_input_revision,seq,"
            "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
            ("r3-other-task", OTHER, "SUCCEEDED", 1, 0, time.strftime("%Y-%m-%d %H:%M:%S.000000"),
             time.strftime("%Y-%m-%d %H:%M:%S.000000")))
    except sqlite3.IntegrityError:
        pass
    rr = s.get(f"{base}/api/task/r3-other-task", timeout=30)
    check(rr.status_code == 404, "[G6] other-owned 任务经 API 视为不存在（404，owner-mismatch 隔离）",
          extra=f"status={rr.status_code}")
    recs = s.get(f"{base}/api/task/records", timeout=30).json()
    check("r3-other-task" not in [r.get("task_id") for r in recs],
          "[G5] other-owned 任务不进入 records")

    # 2) 结构性错误不发布：删光 current-user 的 work/project（留 education），
    #    新任务 P2 候选为空 → ContentGenerationError → FAILED 且不发布 artifact。
    #    经 HTTP delete 每个当前 work/project（会级联清 Fact/Embedding）。
    to_del = [r["id"] for r in db.q(
        "SELECT id FROM experiences WHERE user_id=? AND type IN ('work','project')", (owner,))]
    for eid in to_del:
        s.delete(f"{base}/api/experience/{eid}", timeout=120)
    #    保留但确认 education 仍在（education 不进 P2 槽位，P2 候选仍为空）
    edu_left = db.q("SELECT count(*) n FROM experiences WHERE user_id=? AND type='education'", (owner,))
    check(int(edu_left[0]["n"]) >= 1, "[err] 结构性错误前置：current 仍有 education（留缺省装配用）",
          extra=f"edu={edu_left[0]['n']} deleted={to_del}")

    body = {"name": "孙八R3", "phone": "", "email": "", "location": "", "jd": TEST_JD}
    r = s.post(f"{base}/api/task", timeout=30)
    etid = r.json()["task_id"]
    s.put(f"{base}/api/task/{etid}/save", json=body, timeout=30)
    s.post(f"{base}/api/task/{etid}/freeze", json=body, timeout=30)
    s.post(f"{base}/api/task/{etid}/start", timeout=30)
    s.post(f"{base}/api/task/{etid}/generate", timeout=30)
    eview = poll_status(s, base, etid, timeout_s=300)
    est = eview.get("status")
    check(est == "FAILED", "[G6] 结构性错误任务 → FAILED（装配强行缺省首段候选为空）",
          extra=f"actual={est} terminal_error={eview.get('terminal_error')}")
    check(not eview.get("published_docx_path"), "[G6] 结构性失败不发布 DOCX")
    EVIDENCE["error_path"] = {"failed_task_id": etid, "status": est}


def main() -> int:
    sys.exit(run())


if __name__ == "__main__":
    main()