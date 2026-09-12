#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""H8-R2 监测器自检：无控制台父进程派生 CMD/tasklist 是否产生可见控制台窗口。

用 pythonw.exe（GUI 子系统、无控制台）模拟冻结 onedir 服务进程：无控制台父进程
以「不带任何隐藏窗口标志」的 subprocess 派生 cmd / tasklist → 分配新控制台 →
可见控制台窗口（本机窗口类 PseudoConsoleWindow）闪出。等价于旧包 P4 的行为。

配合 winmon 运行以验证监测器能捕获这些闪窗。

用法：
  python scripts/h8_r2_selftest.py
"""
from __future__ import annotations

import os
import subprocess
import sys

_INNER = r"""
import subprocess
import time
CMDS = [
    ["cmd", "/c", "ping -n 2 127.0.0.1 >nul"],
    ["tasklist", "/FI", "IMAGENAME eq WINWORD.EXE", "/FO", "CSV"],
    ["cmd", "/c", "rd /s /q C:\\nul"],
]
for _ in range(3):
    for c in CMDS:
        try:
            subprocess.run(c, capture_output=True, timeout=15)
        except Exception:
            pass
    time.sleep(0.2)
print("inner_done", flush=True)
"""


def main() -> int:
    exe_dir = os.path.dirname(sys.executable)
    pyw = os.path.join(exe_dir, "pythonw.exe")
    if not os.path.exists(pyw):
        print("pythonw.exe 不存在", flush=True)
        return 2
    p = subprocess.Popen([pyw, "-c", _INNER],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rc = p.wait(timeout=60)
    print(f"selftest_inner_done rc={rc}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
