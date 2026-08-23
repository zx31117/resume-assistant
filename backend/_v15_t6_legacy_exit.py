"""V1.5.0 T6 验证：旧向量实现退出（PLAN §7 T6 / §8.2）。

验证项：
1. 旧模块文件已删除（chroma_store / vector_index_sync / rag_service）
2. 生产代码无导入旧模块
3. requirements.txt 无 chromadb
4. config.py 无 CHROMA_PATH
5. schemas.ExperienceOut 无 vector_id
6. 应用可正常 import（无 ImportError）
7. 旧测试文件已加 guard
8. 新 V1.5.0 模块可正常 import

退出码 0 = 全部通过；非 0 = 有失败。
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

BACKEND = _THIS_DIR

_pass = 0
_fail = 0


def check(cond: bool, name: str):
    global _pass, _fail
    if cond:
        _pass += 1
        print(f"  [PASS] {name}")
    else:
        _fail += 1
        print(f"  [FAIL] {name}")


def _file_deleted(rel_path: str) -> bool:
    return not (BACKEND / rel_path).exists()


def _grep_in_file(rel_path: str, pattern: str) -> bool:
    """Return True if pattern found in file."""
    fp = BACKEND / rel_path
    if not fp.exists():
        return False
    text = fp.read_text(encoding="utf-8", errors="ignore")
    return pattern in text


def _grep_in_py_files(pattern: str, exclude: set[str] = None) -> list[str]:
    """Search all .py files under backend/ for pattern. Returns list of matching file names."""
    exclude = exclude or set()
    matches = []
    for py in BACKEND.glob("*.py"):
        if py.name in exclude:
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        if pattern in text:
            matches.append(py.name)
    return matches


def main():
    # Stub env for import
    os.environ.setdefault("ARK_API_KEY", "t6-legacy-stub-key")
    os.environ.setdefault("OPENAI_API_KEY", "t6-legacy-stub-key")

    print("=" * 60)
    print("V1.5.0 T6: 旧向量实现退出验证")
    print("=" * 60)

    # ── 1. 旧模块文件已删除 ──────────────────────────────────
    print("\n[1] 旧模块文件已删除")
    check(_file_deleted("vectorstore/chroma_store.py"), "chroma_store.py deleted")
    # Check if vectorstore dir is empty or doesn't have chroma_store
    vs_dir = BACKEND / "vectorstore"
    if vs_dir.exists():
        remaining = list(vs_dir.glob("*.py"))
        check(not any(f.name == "chroma_store.py" for f in remaining),
              f"vectorstore/ has no chroma_store.py (remaining: {[f.name for f in remaining]})")
    else:
        check(True, "vectorstore/ dir does not exist")
    check(_file_deleted("services/vector_index_sync.py"), "vector_index_sync.py deleted")
    check(_file_deleted("services/rag_service.py"), "rag_service.py deleted")

    # ── 2. 生产代码无导入旧模块 ──────────────────────────────
    print("\n[2] 生产代码无导入旧模块")
    # Exclude test files and this file from the scan
    test_excludes = {
        "_v15_t6_legacy_exit.py", "_t6_patches.py", "_t6_test_patches.py",
        "_v13_stub_e2e_new.py", "_v13_validation.py", "_e2e_v13_full.py",
        "_v14_t3_migrate.py",  # guarded
    }
    # Check for import statements of deleted modules in production .py files
    prod_files = []
    for py in BACKEND.glob("*.py"):
        if py.name in test_excludes or py.name.startswith("_v15_t") or py.name.startswith("_v14_t"):
            continue
        if py.name.startswith("_"):
            continue
        prod_files.append(py.name)

    for py in BACKEND.glob("api/**/*.py"):
        prod_files.append(str(py.relative_to(BACKEND)).replace("\\", "/"))
    for py in BACKEND.glob("services/**/*.py"):
        prod_files.append(str(py.relative_to(BACKEND)).replace("\\", "/"))
    for py in BACKEND.glob("core/**/*.py"):
        prod_files.append(str(py.relative_to(BACKEND)).replace("\\", "/"))
    for py in BACKEND.glob("database/**/*.py"):
        prod_files.append(str(py.relative_to(BACKEND)).replace("\\", "/"))
    for py in BACKEND.glob("models/**/*.py"):
        prod_files.append(str(py.relative_to(BACKEND)).replace("\\", "/"))
    for py in BACKEND.glob("vectorstore/**/*.py"):
        prod_files.append(str(py.relative_to(BACKEND)).replace("\\", "/"))

    import re as _re
    bad_imports = []
    # Match actual import statements only (not comments/docstrings)
    import_patterns = [
        _re.compile(r'^\s*from\s+services\s+import\s+.*\b(rag_service|vector_index_sync)\b'),
        _re.compile(r'^\s*from\s+services\.(rag_service|vector_index_sync)\s+import'),
        _re.compile(r'^\s*import\s+services\.(rag_service|vector_index_sync)'),
        _re.compile(r'^\s*from\s+vectorstore\s+import\s+.*\bchroma_store\b'),
        _re.compile(r'^\s*from\s+vectorstore\.chroma_store\s+import'),
        _re.compile(r'^\s*import\s+vectorstore\.chroma_store'),
    ]
    for rel in prod_files:
        fp = BACKEND / rel
        if not fp.exists():
            continue
        text = fp.read_text(encoding="utf-8", errors="ignore")
        for line in text.split("\n"):
            ls = line.strip()
            if ls.startswith("#"):
                continue
            for pat in import_patterns:
                if pat.match(line):
                    bad_imports.append(f"{rel}: {ls}")
    check(not bad_imports, f"no production imports of deleted modules (found: {bad_imports[:3]})")

    # Check for chroma_store imports
    chroma_imports = []
    for rel in prod_files:
        fp = BACKEND / rel
        if not fp.exists():
            continue
        text = fp.read_text(encoding="utf-8", errors="ignore")
        for line in text.split("\n"):
            ls = line.strip()
            if ls.startswith("#"):
                continue
            if "chroma_store" in ls and "import" in ls:
                chroma_imports.append(f"{rel}: {ls}")
    check(not chroma_imports, f"no chroma_store imports in production (found: {chroma_imports[:3]})")

    # ── 3. requirements.txt 无 chromadb ──────────────────────
    print("\n[3] requirements.txt 无 chromadb")
    req = (BACKEND / "requirements.txt").read_text(encoding="utf-8")
    check("chromadb" not in req, "chromadb removed from requirements.txt")
    check("numpy" in req, "numpy still present (computation library)")

    # ── 4. config.py 无 CHROMA_PATH ──────────────────────────
    print("\n[4] config.py 无 CHROMA_PATH")
    cfg = (BACKEND / "core/config.py").read_text(encoding="utf-8")
    # Check that CHROMA_PATH is not an active Settings class attribute
    # (docstring/comments mentioning it as removed are OK)
    active_chroma = []
    in_class = False
    for line in cfg.split("\n"):
        if "class Settings" in line:
            in_class = True
            continue
        if in_class and "CHROMA_PATH" in line and not line.strip().startswith("#"):
            # This is a class attribute assignment like "CHROMA_PATH: str = ..."
            stripped = line.strip()
            if ":" in stripped or "=" in stripped:
                active_chroma.append(line.strip())
    check(not active_chroma, f"no active CHROMA_PATH setting in config.py (found: {active_chroma})")

    # ── 5. schemas.ExperienceOut 无 vector_id ────────────────
    print("\n[5] schemas.ExperienceOut 无 vector_id")
    # Import and check
    try:
        from api.schemas import ExperienceOut
        fields = list(ExperienceOut.model_fields.keys())
        check("vector_id" not in fields, f"ExperienceOut has no vector_id (fields: {fields})")
    except Exception as e:
        check(False, f"Failed to import ExperienceOut: {e}")

    # ── 6. 应用可正常 import ────────────────────────────────
    print("\n[6] 应用可正常 import（无 ImportError）")
    try:
        import main
        check(True, "main.py imports successfully")
    except Exception as e:
        check(False, f"main.py import failed: {e}")

    try:
        from api.routes import generate
        check(True, "api.routes.generate imports successfully")
    except Exception as e:
        check(False, f"api.routes.generate import failed: {e}")

    # ── 7. 旧测试文件已加 guard ───────────────────────────────
    print("\n[7] 旧测试文件已加 V1.5.0 guard")
    for old_file in ["_v13_validation.py", "_e2e_v13_full.py", "_v14_t3_migrate.py"]:
        fp = BACKEND / old_file
        if fp.exists():
            text = fp.read_text(encoding="utf-8", errors="ignore")
            check("V1.5.0 GUARD" in text, f"{old_file} has V1.5.0 guard")
        else:
            check(False, f"{old_file} not found")

    # ── 8. 新 V1.5.0 模块可正常 import ───────────────────────
    print("\n[8] 新 V1.5.0 模块可正常 import")
    new_mods = [
        "services.embedding_service",
        "services.fact_service",
        "services.selection_service",
        "services.constrained_rewrite",
        "database.migrations",
    ]
    for mod in new_mods:
        try:
            importlib.import_module(mod)
            check(True, f"{mod} imports OK")
        except Exception as e:
            check(False, f"{mod} import failed: {e}")

    # ── 9. 模型层无 VectorIndexJob ───────────────────────────
    print("\n[9] 模型层无 VectorIndexJob 类定义")
    models_text = (BACKEND / "database/models.py").read_text(encoding="utf-8")
    # Check that VectorIndexJob is not defined as a class (comments are OK)
    has_class = any("class VectorIndexJob" in l for l in models_text.split("\n") if not l.strip().startswith("#"))
    check(not has_class, "no 'class VectorIndexJob' definition in models.py")

    # ── 10. 模型层有 V1.5.0 新表 ─────────────────────────────
    print("\n[10] 模型层有 V1.5.0 新表（Fact / SchemaVersion / FactEmbedding）")
    check("class Fact(" in models_text or "class Fact(Base)" in models_text, "Fact model defined")
    check("class SchemaVersion" in models_text, "SchemaVersion model defined")
    check("class FactEmbedding" in models_text, "FactEmbedding model defined")

    # ── Summary ──────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"T6 Legacy Exit: {_pass} passed, {_fail} failed")
    print("=" * 60)
    if _fail > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
