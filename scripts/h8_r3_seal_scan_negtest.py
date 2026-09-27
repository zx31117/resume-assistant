#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V2.2.0 R3-28 §28.7-2 返工：中央封存脱敏/复扫的**离线正反向矩阵**。

对应 RESULT §R3-28 §28.7-2/§28.7-4。它不依赖任何真实模型 / 浏览器 / 付费 Gate：
在一次性临时目录里构造“原始证据”文本，**真实启动** `scripts/h8_r3_seal.py stage`
子进程，读取其真实退出码与脱敏后的 staging 字节，逐项断言。

Part A（端到端 stage 用例，逐例断言 stage rc + 脱敏后字节 + STAGE_REPORT 复扫零命中）：
  S1_live_root_forward_slash   现场工作区路径的**正斜杠**写法 → 必须被动态规则脱敏
  S2_live_root_json_doubled    现场工作区路径的 **JSON 双反斜杠**写法 → 必须被脱敏
  S3_system_data_abs_path      system-data 绝对盘符路径 → 必须被通用规则脱敏
  S4_unc_path                  UNC（`\\\\srv\\share`）路径 → 必须被脱敏
  S5_long_context              超长行内嵌现场路径 → 必须被脱敏且不残留
  S6_public_url_preserved      公开 HTTP(S) URL → 必须逐字节保留且复扫零误报
  X1_extra_forbidden_hit       `--extra-forbidden` 命中真实文本 → 必须 fail-closed
  X2_extra_forbidden_absent    `--extra-forbidden` 未命中 → 必须 rc 0（对照）

Part B（`_rescan_local_paths` 单元断言，仅记录布尔，不向输出写入路径字面量）：
  盘符 / UNC / 类 Unix 用户目录必须命中；`<home>` / `<local-path>` 占位符与
  **经 URL 掩蔽后**的公开 URL 必须零命中，且掩蔽/还原可逆。

退出码 0 = 全部用例成立；非 0 = 存在逃逸（并写明 failures）。

纪律：输出 JSON **只写布尔/计数**，不写任何真实用户名或本机绝对路径字面量，
以免该证据本身在后续 stage 中命中。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
_SEAL = HERE / "h8_r3_seal.py"

sys.path.insert(0, str(HERE))
import h8_r3_seal as SEAL  # noqa: E402


def _rmtree_force(path, attempts: int = 8) -> bool:
    """删除目录树，兼容只读文件（与其它矩阵脚本同源实现）。"""
    import inspect as _inspect
    import os
    import stat as _stat
    import time as _time

    def _fix(func, p, exc=None):
        try:
            os.chmod(p, _stat.S_IWRITE)
            func(p)
        except Exception:  # noqa: BLE001
            pass

    _params = _inspect.signature(shutil.rmtree).parameters
    _kw = {"onexc": _fix} if "onexc" in _params else {"onerror": _fix}
    for _ in range(attempts):
        try:
            shutil.rmtree(path, **_kw)
        except Exception:  # noqa: BLE001
            pass
        if not os.path.exists(path):
            return True
        _time.sleep(0.4)
    return not os.path.exists(path)


def _sh(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)


def _stage(raw: Path, staged: Path, extra_forbidden: str | None = None) -> dict:
    argv = [sys.executable, str(_SEAL), "stage",
            "--evidence-dir", str(raw), "--staged-dir", str(staged)]
    if extra_forbidden is not None:
        argv += ["--extra-forbidden", extra_forbidden]
    p = _sh(argv)
    report = None
    rp = staged / "STAGE_REPORT.json"
    if rp.is_file():
        try:
            report = json.loads(rp.read_text(encoding="utf-8-sig"))
        except Exception:  # noqa: BLE001
            report = None
    return {"rc": p.returncode, "stdout": p.stdout, "stderr": p.stderr,
            "report": report}


def _write_raw(raw: Path, name: str, text: str) -> None:
    raw.mkdir(parents=True, exist_ok=True)
    with open(raw / name, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def _read_staged(staged: Path, name: str) -> str:
    p = staged / name
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def _stage_case(root: Path, case_id: str, name: str, files: dict[str, str], *,
                expect_rc: int, must_contain: list[str] | None = None,
                must_absent: list[str] | None = None,
                extra_forbidden: str | None = None,
                report_problem_substr: str | None = None,
                detail: str = "") -> dict:
    """通用端到端用例：构造 raw → stage → 断言 rc / 字节 / 复扫。"""
    raw = root / f"raw_{case_id}"
    staged = root / f"staged_{case_id}"
    for d in (raw, staged):
        if d.exists():
            _rmtree_force(d)
    raw.mkdir(parents=True, exist_ok=True)
    for fname, text in files.items():
        _write_raw(raw, fname, text)

    res = _stage(raw, staged, extra_forbidden)
    problems: list[str] = []
    if res["rc"] != expect_rc:
        problems.append(f"stage 退出码应为 {expect_rc}，实际 {res['rc']}: "
                        f"{(res['stderr'] or '')[-200:]}")

    joined = "\n".join(_read_staged(staged, f) for f in files)
    for token in (must_contain or []):
        if token not in joined:
            problems.append(f"staging 缺少预期占位符/内容: {token}")
    for token in (must_absent or []):
        if token in joined:
            problems.append("staging 仍残留未脱敏字面量（内容已省略，避免二次泄漏）")

    rep = res["report"] or {}
    rescan_zero = rep.get("local_path_rescan_zero_hit")
    if rep and rescan_zero is not True:
        problems.append(f"STAGE_REPORT.local_path_rescan_zero_hit 非 true: {rescan_zero}")
    if rep and rep.get("local_path_rescan_fail_closed") is not True:
        problems.append("STAGE_REPORT.local_path_rescan_fail_closed 非 true")
    if report_problem_substr is not None:
        blob = json.dumps(rep.get("problems") or [], ensure_ascii=False)
        if report_problem_substr not in blob:
            problems.append("STAGE_REPORT.problems 未指出预期的禁止子串命中")

    return {"id": case_id, "case": name, "part": "A", "stage_rc": res["rc"],
            "expected_rc": expect_rc, "rescan_zero_hit": rescan_zero,
            "text_files": (rep.get("counts") or {}).get("text_files"),
            "forbidden_hits": (rep.get("counts") or {}).get("forbidden_hits"),
            "problems": problems, "detail": detail, "ok": not problems}


def run_matrix(root: Path) -> dict:
    cases: list[dict] = []
    live = str(SEAL.LIVE_ROOT)
    live_fwd = live.replace("\\", "/")
    live_json = live.replace("\\", "\\\\")

    # S1：现场工作区路径的正斜杠写法
    cases.append(_stage_case(
        root, "S1_live_root_forward_slash", "现场工作区路径（正斜杠）",
        {"a.txt": f"workspace={live_fwd}/backend/core/config.py\n"},
        expect_rc=0, must_contain=["<current-workspace>/backend/core/config.py"],
        must_absent=[live_fwd],
        detail="动态现场根规则必须覆盖 `\\` 与 `/` 两种分隔符"))

    # S2：现场工作区路径的 JSON 双反斜杠写法
    cases.append(_stage_case(
        root, "S2_live_root_json_doubled", "现场工作区路径（JSON 双反斜杠）",
        {"b.json": json.dumps({"dir": live_json + r"\\backend"}, ensure_ascii=False)},
        expect_rc=0, must_contain=["<current-workspace>"],
        must_absent=[live_json],
        detail="JSON 转义后的双反斜杠路径必须被脱敏"))

    # S3：system-data 绝对盘符路径（通用规则）
    cases.append(_stage_case(
        root, "S3_system_data_abs_path", "system-data 绝对盘符路径",
        {"c.log": "db=C:\\ProgramData\\SomeApp\\data\\app.db size=1\n"},
        expect_rc=0, must_contain=["<local-path>"],
        must_absent=["C:\\ProgramData\\SomeApp"],
        detail="通用盘符规则必须覆盖 system-data 绝对路径"))

    # S4：UNC 路径
    cases.append(_stage_case(
        root, "S4_unc_path", "UNC 路径",
        {"d.txt": "share=\\\\fileserver\\share\\dir\\file.txt\n"},
        expect_rc=0, must_contain=["<unc-path>"],
        must_absent=["\\\\fileserver\\share"],
        detail="UNC / 双反斜杠路径必须被脱敏"))

    # S5：超长行内嵌现场路径
    filler = "lorem ipsum dolor sit amet " * 900
    cases.append(_stage_case(
        root, "S5_long_context", "超长行内嵌现场路径",
        {"e.txt": f"{filler}{live}\\frontend\\src\\main.tsx\n"},
        expect_rc=0, must_contain=["<current-workspace>\\frontend\\src\\main.tsx"],
        must_absent=[live],
        detail="超长上下文不得使动态脱敏或复扫失效"))

    # S6：公开 HTTP(S) URL 必须保留且零误报
    url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions?x=1"
    cases.append(_stage_case(
        root, "S6_public_url_preserved", "公开 HTTP(S) URL",
        {"f.json": json.dumps({"endpoint": url, "note": "ok"}, ensure_ascii=False)},
        expect_rc=0, must_contain=[url],
        detail="公开 URL 必须逐字节保留，且不得被误报为本地路径"))

    # X1：--extra-forbidden 命中真实文本 → fail-closed
    token = "ZZ_EXTRA_FORBIDDEN_9F3A2B"
    cases.append(_stage_case(
        root, "X1_extra_forbidden_hit", "--extra-forbidden 命中",
        {"g.txt": f"payload={token}\n"},
        expect_rc=1, extra_forbidden=token,
        report_problem_substr=token[:12].lower(),
        detail="传入的 extra-forbidden 必须实际参与扫描（命中即非零退出）"))

    # X2：--extra-forbidden 未命中 → rc 0（对照，证明上一例非恒真）
    cases.append(_stage_case(
        root, "X2_extra_forbidden_absent", "--extra-forbidden 未命中",
        {"h.txt": "payload=clean\n"},
        expect_rc=0, extra_forbidden="ZZ_ABSENT_TOKEN_4C7D",
        detail="未命中的 extra-forbidden 不得使 stage 失败"))

    # ── Part B：_rescan_local_paths 单元断言（只记录布尔）──
    def unit(cid: str, name: str, text: str, *, expect_hit: bool,
             detail: str = "") -> None:
        probs: list[str] = []
        n = SEAL._rescan_local_paths(text, "unit", probs)
        ok = (n > 0) if expect_hit else (n == 0)
        cases.append({"id": cid, "case": name, "part": "B",
                      "expect_hit": expect_hit, "hits": n,
                      "problems": probs[:4] if not ok else [],
                      "detail": detail, "ok": ok})

    unit("B1_drive_path_hit", "盘符绝对路径必须命中",
         "C:\\Users\\nobody\\x\\y.txt", expect_hit=True)
    unit("B2_unc_hit", "UNC 路径必须命中",
         "\\\\srv\\share\\f.txt", expect_hit=True)
    unit("B3_unix_home_hit", "类 Unix 用户目录必须命中",
         "/home/nobody/project/x", expect_hit=True)
    unit("B4_placeholders_clean", "占位符必须零命中",
         "<home>/a/b <local-path> <unc-path> <current-workspace>/x",
         expect_hit=False)
    unit("B5_plain_clean", "无路径纯文本必须零命中",
         "all good, no paths here at all", expect_hit=False)

    # B6：URL 掩蔽 → 复扫零命中 → 还原可逆（证明公开 URL 不被误报为本地路径）
    url_with_users = "https://example.com/Users/nobody/profile"
    store: dict[str, str] = {}
    masked = SEAL._mask_urls(f"see {url_with_users} end", store)
    probs_b6: list[str] = []
    n_b6 = SEAL._rescan_local_paths(masked, "unit-masked", probs_b6)
    restored = SEAL._restore_urls(masked, store)
    b6_ok = (n_b6 == 0) and (restored == f"see {url_with_users} end")
    cases.append({"id": "B6_url_masked_roundtrip", "case": "URL 掩蔽零误报且可逆",
                  "part": "B", "masked_hits": n_b6, "roundtrip_ok": b6_ok,
                  "problems": [] if b6_ok else ["掩蔽后仍命中或还原不可逆"],
                  "detail": "含用户目录段的公开 URL 经掩蔽后不得被误报，且还原必须可逆",
                  "ok": b6_ok})

    failures = [c["id"] for c in cases if not c["ok"]]
    return {
        "schema": "resume-assistant/r3-seal-scan-negtest",
        "version": 1,
        "generated_at_local": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "generator": "scripts/h8_r3_seal_scan_negtest.py",
        "seal_script": _SEAL.name,
        "seal_script_sha256": SEAL.sha256_file(_SEAL),
        "case_count": len(cases),
        "cases": cases,
        "failures": failures,
        "all_ok": not failures,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="h8_r3_seal_scan_negtest_"))
    try:
        result = run_matrix(tmp)
    finally:
        _rmtree_force(tmp)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[seal-scan-negtest] cases={result['case_count']} "
          f"failures={result['failures']} all_ok={result['all_ok']}")
    for c in result["cases"]:
        flag = "OK " if c["ok"] else "FAIL"
        print(f"  [{flag}] {c['id']} ({c['part']}) {c['detail']}")
        for p in c["problems"]:
            print(f"         - {p}")
    return 0 if result["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())