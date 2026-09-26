#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V2.2.0 R3 §R3-20：封存 / manifest 一致性负向矩阵（真实子进程，读取真实退出码）。

覆盖文档要求（§R3-20 §20.5 点 6）：
  1. 脱敏 / 任意后处理改变证据字节 → manifest verify 非零退出（hash 断链 fail-closed）；
  2. 中央复制后证据 hash 变化 → verify 非零退出；
  3. manifest 记录 stale hash → verify 非零退出；
  4. checksum 缺失 / 额外未登记文件 / hash 不一致 → verify-checksums 非零退出；
  5. verify 有问题却输出 `final_verdict=True` 摘要 → 必须输出 false 摘要（输出一致性）。

纪律：不硬编码预期退出码，一律读取子进程真实返回；只用一次性临时目录 + 临时 Git repo，
不触碰真实 runtime / 仓库。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PY = "C:/Users/31117/AppData/Local/Programs/Python/Python310/python.exe"

MANIFEST = HERE / "h8_r3_manifest.py"
SEAL = HERE / "h8_r3_seal.py"
FIXTURES = HERE / "h8_r3_gate_fixtures.py"

RESULT_PATH = "docs/versions/v2.2.0/RESULT.md"
PLAN_BLOB = "7d8a249a5ec3e607855f20d794bb7ed9cda351ee"


def _env() -> dict:
    import os
    e = dict(os.environ)
    for k in ("PYTHONPATH", "NODE_OPTIONS", "HTTP_PROXY", "HTTPS_PROXY",
              "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        e.pop(k, None)
    return e


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _git(repo: Path, *args: str) -> str:
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return p.stdout.strip()


def _make_repo(root: Path) -> tuple[str, str]:
    """建一个临时 Git repo：SRC commit + HANDOFF commit（仅改 RESULT.md）。返回 (src, handoff)。"""
    repo = root / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "dev@example.test")
    _git(repo, "config", "user.name", "dev")
    (repo / "README.md").write_text("# fake repo\n", encoding="utf-8")
    rd = repo / "docs" / "versions" / "v2.2.0"
    rd.mkdir(parents=True)
    (rd / "PLAN.md").write_text("plan\n", encoding="utf-8")
    (rd / "RESULT.md").write_text("# result\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "src")
    src = _git(repo, "rev-parse", "HEAD")
    # HANDOFF：仅改 RESULT.md
    (rd / "RESULT.md").write_text("# result updated\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "handoff")
    handoff = _git(repo, "rev-parse", "HEAD")
    return src, handoff


def _make_package(root: Path) -> tuple[Path, str]:
    """造一个最小假包（ResumeAssistant.exe + bundle），返回 (pkg_dir, exe_sha)。"""
    pkg = root / "pkg" / "ResumeAssistant"
    (pkg / "_internal" / "frontend" / "dist" / "assets").mkdir(parents=True)
    exe_bytes = b"FAKE-EXE-" + b"\x00" * 64
    (pkg / "ResumeAssistant.exe").write_bytes(exe_bytes)
    (pkg / "_internal" / "frontend" / "dist" / "assets" / "index-FAKE.js").write_bytes(b"bundle")
    return pkg, _sha256(exe_bytes)


def _manifest_build(ev: Path, repo: Path, pkg: Path, exe_sha: str,
                    src: str, handoff: str) -> int:
    args = [PY, str(MANIFEST), "build", "--repo", str(repo),
            "--expected-src", src, "--expected-handoff", handoff,
            "--exe-sha", exe_sha, "--bundle", "index-FAKE.js",
            "--package-dir", str(pkg),
            "--gates-meta", str(ev / "gates_run.json"),
            "--evidence-dir", str(ev), "--out", str(ev / "gate_manifest.json")]
    p = subprocess.run(args, capture_output=True, text=True, env=_env())
    return p.returncode


def _manifest_verify(ev: Path, repo: Path, src: str, handoff: str) -> tuple[int, str]:
    args = [PY, str(MANIFEST), "verify", "--out", str(ev / "gate_manifest.json"),
            "--repo", str(repo), "--expected-src", src, "--expected-handoff", handoff,
            "--evidence-dir", str(ev)]
    p = subprocess.run(args, capture_output=True, text=True, env=_env())
    return p.returncode, (p.stdout or "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "validation-artifacts" / "h8" / "r3rework4"
                                        / "seal_manifest_negtest.json"))
    args = ap.parse_args()

    cases: list[dict] = []
    problems: list[str] = []

    root = Path(tempfile.mkdtemp(prefix="h8sealneg_"))
    try:
        src, handoff = _make_repo(root)
        pkg, exe_sha = _make_package(root)

        # 有效证据 → stage（脱敏）→ build manifest → 正向 verify 应通过
        import importlib.util
        spec = importlib.util.spec_from_file_location("fixtures", str(FIXTURES))
        fx = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fx)

        raw = root / "raw"
        runs = fx.write_valid_evidence(raw, exe_sha)
        (raw / "gates_run.json").write_text(json.dumps(runs, ensure_ascii=False, indent=2),
                                            encoding="utf-8")

        staged = root / "staged"
        sp = subprocess.run([PY, str(SEAL), "stage", "--evidence-dir", str(raw),
                             "--staged-dir", str(staged)], capture_output=True, text=True, env=_env())
        if sp.returncode != 0:
            problems.append(f"stage 正向失败 rc={sp.returncode}")
            cases.append({"id": "S0_stage_positive", "ok": False,
                          "exit_code": sp.returncode})
        else:
            cases.append({"id": "S0_stage_positive", "ok": True, "exit_code": 0})

        rc = _manifest_build(staged, root / "repo", pkg, exe_sha, src, handoff)
        if rc != 0:
            problems.append(f"manifest build 正向失败 rc={rc}")
        cases.append({"id": "M0_build_positive", "ok": rc == 0, "exit_code": rc})

        vrc, vout = _manifest_verify(staged, root / "repo", src, handoff)
        cases.append({"id": "V0_verify_positive", "ok": vrc == 0, "exit_code": vrc})

        # N1 脱敏/后处理改变证据字节 → verify 失败 + 摘要为 false（不得打印 true）
        tampered = root / "tampered"
        subprocess.run([PY, str(SEAL), "stage", "--evidence-dir", str(raw),
                        "--staged-dir", str(tampered)], capture_output=True, text=True, env=_env())
        _manifest_build(tampered, root / "repo", pkg, exe_sha, src, handoff)
        # 修改一个证据文件字节（等价于中央复制后 hash 变化）
        f = tampered / "package_audit.json"
        f.write_text(f.read_text(encoding="utf-8") + "\n// tampered", encoding="utf-8")
        vrc, vout = _manifest_verify(tampered, root / "repo", src, handoff)
        n1_ok = vrc != 0 and "final_verdict=False" in vout and "final_verdict=True" not in vout
        cases.append({"id": "N1_byte_change_detected", "ok": n1_ok, "exit_code": vrc})
        if not n1_ok:
            problems.append(f"N1 byte-change 未 fail-closed rc={vrc} out_tail={vout[-300:]}")

        # N2 manifest stale hash：篡改 manifest 里记录的 evidence sha256 → verify 失败
        stale = root / "stale"
        subprocess.run([PY, str(SEAL), "stage", "--evidence-dir", str(raw),
                        "--staged-dir", str(stale)], capture_output=True, text=True, env=_env())
        _manifest_build(stale, root / "repo", pkg, exe_sha, src, handoff)
        m = json.loads((stale / "gate_manifest.json").read_text(encoding="utf-8-sig"))
        m["gates"]["package_audit"]["sha256"] = "0" * 64
        (stale / "gate_manifest.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
        vrc, vout = _manifest_verify(stale, root / "repo", src, handoff)
        n2_ok = vrc != 0 and "final_verdict=False" in vout
        cases.append({"id": "N2_stale_hash_detected", "ok": n2_ok, "exit_code": vrc})
        if not n2_ok:
            problems.append(f"N2 stale-hash 未 fail-closed rc={vrc} out_tail={vout[-300:]}")

        # N6 中央副本 verify（字节一致应通过）——正向对照，先于 checksum 篡改场景。
        central = root / "central"
        central.mkdir()
        subprocess.run([PY, str(SEAL), "seal", "--pkg-dir", str(pkg),
                        "--staged-dir", str(staged), "--staging-root", str(central),
                        "--src", "abc12345"], capture_output=True, text=True, env=_env())
        evc = central / "abc12345-evidence"
        vrc, vout = _manifest_verify(evc, root / "repo", src, handoff)
        n6_ok = vrc == 0
        cases.append({"id": "N6_central_verify_positive", "ok": n6_ok, "exit_code": vrc})
        if not n6_ok:
            problems.append(f"N6 中央副本 verify 未通过 rc={vrc} out_tail={vout[-400:]}")

        # N3/N4/N5 checksum 缺失 / 额外 / 不一致：每个场景用独立 fresh 封存副本，避免互相污染。
        def _fresh_seal(name: str) -> Path:
            subprocess.run([PY, str(SEAL), "seal", "--pkg-dir", str(pkg),
                            "--staged-dir", str(staged), "--staging-root", str(central),
                            "--src", name], capture_output=True, text=True, env=_env())
            return central / f"{name}-evidence"

        # N3 缺失：删一个已登记文件
        ev3 = _fresh_seal("n3aaaaaa")
        (ev3 / "package_audit.json").unlink()
        vcrc = subprocess.run([PY, str(SEAL), "verify-checksums", "--evidence-dir", str(ev3)],
                              capture_output=True, text=True, env=_env()).returncode
        n3_ok = vcrc != 0
        cases.append({"id": "N3_checksum_missing", "ok": n3_ok, "exit_code": vcrc})
        if not n3_ok:
            problems.append("N3 checksum-missing 未 fail-closed")

        # N4 额外未登记文件
        ev4 = _fresh_seal("n4bbbbbb")
        (ev4 / "EXTRA_UNLISTED.txt").write_text("extra", encoding="utf-8")
        vcrc = subprocess.run([PY, str(SEAL), "verify-checksums", "--evidence-dir", str(ev4)],
                              capture_output=True, text=True, env=_env()).returncode
        n4_ok = vcrc != 0
        cases.append({"id": "N4_checksum_extra", "ok": n4_ok, "exit_code": vcrc})
        if not n4_ok:
            problems.append("N4 checksum-extra 未 fail-closed")

        # N5 不一致：改一个文件内容
        ev5 = _fresh_seal("n5cccccc")
        f = ev5 / "pyz_check.json"
        f.write_text(f.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        vcrc = subprocess.run([PY, str(SEAL), "verify-checksums", "--evidence-dir", str(ev5)],
                              capture_output=True, text=True, env=_env()).returncode
        n5_ok = vcrc != 0
        cases.append({"id": "N5_checksum_mismatch", "ok": n5_ok, "exit_code": vcrc})
        if not n5_ok:
            problems.append("N5 checksum-mismatch 未 fail-closed")

    except Exception as e:  # noqa: BLE001
        import traceback
        problems.append(f"exception:{type(e).__name__}:{e}")
        traceback.print_exc()
    finally:
        import shutil
        shutil.rmtree(root, ignore_errors=True)

    all_ok = all(c["ok"] for c in cases) and not problems
    out = {
        "generator": "scripts/h8_r3_seal_manifest_negtest.py",
        "cases": cases,
        "all_ok": all_ok,
        "problems": problems,
        "ok": all_ok,
    }
    p = Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"all_ok": all_ok, "cases": len(cases), "problems": problems},
                     ensure_ascii=False))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
