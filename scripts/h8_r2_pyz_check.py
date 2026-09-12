#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""H8-R2 冻结包内嵌 PYZ 字节码核验。

以 PyInstaller CArchiveReader/ZlibArchiveReader 解包最终 onedir 的 EXE 内嵌 PYZ，
递归读取 `services.docx_to_pdf` / `services.docx_to_pdf_worker` / `api.routes.template`
三个生产模块的 code.co_names，断言：

- 三者均含 `CREATE_NO_WINDOW`（即 `_NO_WINDOW = subprocess.CREATE_NO_WINDOW if ...` 已进包）；
- `services.docx_to_pdf` 不再含 `rd` / `cmd` 常量（`cmd /c rd` 二次包装已移除）。

用法：
  python scripts/h8_r2_pyz_check.py --exe <release-h8-r2>/ResumeAssistant/ResumeAssistant.exe
退出码：0 = 断言全部通过；1 = 任一断言失败；2 = 无法读取。
"""
from __future__ import annotations

import argparse
import json
import marshal
import sys
from pathlib import Path

try:
    from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader
except Exception as e:  # noqa: BLE001
    print(f"PYZ_CHECK_FATAL pyinstaller_unavailable: {e!r}")
    sys.exit(2)

MODULES = (
    "services.docx_to_pdf",
    "services.docx_to_pdf_worker",
    "api.routes.template",
)
MUST_HAVE = ("CREATE_NO_WINDOW",)
MUST_NOT_HAVE = {  # module -> 不应出现的 co_names/co_consts 常量
    "services.docx_to_pdf": ("cmd", "rd"),
}


def _module_code(pyz: ZlibArchiveReader, mod: str):
    # PyInstaller 6 的 extract 已解 marshal，直接返回 code 对象
    if mod in pyz.toc:
        return pyz.extract(mod)
    return None


def _iter_codes(obj, seen=None):
    """递归遍历 code 对象及其嵌套 code（模块→函数→闭包）。"""
    if seen is None:
        seen = set()
    if id(obj) in seen:
        return
    seen.add(id(obj))
    yield obj
    if hasattr(obj, "co_consts"):
        for c in obj.co_consts:
            if hasattr(c, "co_names"):
                yield from _iter_codes(c, seen)


def _iter_consts(obj, seen=None):
    if seen is None:
        seen = set()
    if id(obj) in seen:
        return
    seen.add(id(obj))
    yield obj
    if isinstance(obj, (list, tuple)):
        for item in obj:
            yield from _iter_consts(item)
    elif hasattr(obj, "co_consts"):
        for c in obj.co_consts:
            yield from _iter_consts(c)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    exe = Path(args.exe)
    if not exe.exists():
        print("PYZ_CHECK_FATAL exe_missing")
        return 2

    car = CArchiveReader(str(exe))
    if "PYZ.pyz" not in car.toc:
        print("PYZ_CHECK_FATAL no_pyz_entry")
        return 2

    pyz = car.open_embedded_archive("PYZ.pyz")

    result: dict = {"exe": str(exe), "modules": {}}
    all_ok = True
    for mod in MODULES:
        code = _module_code(pyz, mod)
        rec: dict = {"found": code is not None}
        if code is not None:
            all_names = {n for c in _iter_codes(code) for n in c.co_names}
            consts = {c for c in _iter_consts(code) if isinstance(c, str)}
            rec["co_names_has_create_no_window"] = "CREATE_NO_WINDOW" in all_names
            rec["co_consts_no_cmd"] = not ({"cmd"} & consts)
            rec["co_consts_no_rd"] = not ({"rd"} & consts)
            rec["bad_consts_present"] = sorted(
                ({"cmd", "rd"} & consts) if mod in MUST_NOT_HAVE else set()
            )
            ok = (
                rec["found"]
                and rec["co_names_has_create_no_window"]
                and (mod not in MUST_NOT_HAVE or not rec["bad_consts_present"])
            )
            rec["ok"] = ok
            if not ok:
                all_ok = False
        else:
            rec["ok"] = False
            all_ok = False
        result["modules"][mod] = rec

    result["all_ok"] = all_ok
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
