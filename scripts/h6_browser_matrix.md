# H6 浏览器矩阵手册（PLAN §18.2(2)/(5)、§18.3）

对应可运行入口：`scripts/h6_browser_matrix.py`。本文件说明依赖、命令、预期与取证字段，
供固定 review / 独立验收从 **干净 checkout** 原样重建 §18.3 的 dev 与 production 四区域矩阵。

## 1. 前置与安装（仓库根执行，全部相对路径）

```bash
# Python 3.10 环境（backend/requirements.txt 已含 fastapi/uvicorn/reportlab/python-docx）
python backend/_v21_h6_matrix.py        # 确定性 62 项（exit 0, PASS=62 FAIL=0）

# 前端依赖
cd frontend && npm install && cd ..

# 浏览器 runner 依赖：agent-browser CLI（Playwright Chromium）在 PATH
python scripts/h6_browser_matrix.py --selfcheck   # 期望：agent-browser OK + 依赖可导入 + node OK
```

## 2. 运行

| 命令 | 覆盖 | 预期 |
|---|---|---|
| `python scripts/h6_browser_matrix.py --help` | 参数入口 | exit 0，仅显示帮助 |
| `python scripts/h6_browser_matrix.py --selfcheck` | 环境 | `[PASS] selfcheck`，缺失则列出并 exit 非零 |
| `python scripts/h6_browser_matrix.py --dev` | stub(8000)+vite dev(5173) 场景矩阵 | 汇总 `PASS=<N> FAIL=0`，exit 0 |
| `python scripts/h6_browser_matrix.py --prod-inject pdf`（或 overlay/basis/export） | 单个 VITE_H6_INJECT production test build + 浏览器 | `[PASS] prod-inject <t> ...`，exit 0 |
| `python scripts/h6_browser_matrix.py --prod-all` | 四 target 依次不可跳过 | `PASS=4 FAIL=0` |
| `python scripts/h6_browser_matrix.py --verify` | 正式无 env build | `[PASS] verify 正式 dist 无 H6 注入标记（纯 Python 扫描）` |
| `python scripts/h6_browser_matrix.py --all` | 总入口（62 矩阵+selfcheck+dev+prod-all+verify） | 分组汇总，任何失败 exit 非零 |

未知参数 / `--prod-inject` 缺 target 或非法 target / 同时指定多个入口 ⇒ **fail closed**，不启动任何
服务并 exit 2。任何 FAIL 都导致最终 exit 非零；runner 输出的 JSON 即取证字段。

## 3. dev 场景（--dev）机器断言

每个场景断言（不再只打印）：无 uncaught error 与无 React Hook warning（`console.error/warn` 采集 +
`errs/warns` 字段）；非白屏；每场景 generate POST 增量恰为 1（读 stub_posts.log）；成功场景额外断言
operation/artifact 身份非空且与 anchors artifact 一致、PDF canvas≥1、anchors full 有命中层 /
empty 为 0、Word/PDF 下载字节 SHA-256 与响应 pdf_sha256 / fixture 记录一致；失败场景断言失败态可见且
不产生成功 artifact；artifact-change 断言两次生成 POST 各 +1 且第二次 op/artifact 与第一次不同。

| 场景 | 关键断言 |
|---|---|
| dev-success | errs/warns 空、非白屏、POST+1、canvas≥1、anchors full 命中层≥1、op/art 绑定、下载 hash 一致 |
| dev-fail（fail_generate） | 失败/重试文本可见、非白屏、无成功 artifact、POST+1 |
| dev-nourl（pdf_gen=none） | canvas=0 且无「预览不可用」误报、非白屏、POST+1 |
| dev-broken（pdf_mode=broken） | avail=true（诚实不可用）、非白屏、POST+1 |
| dev-anchors-empty | canvas≥1、命中层=0、POST+1 |
| dev-artifact-change（两次生成） | 各自 POST+1；op/art 两次不同；第二次渲染/下载生效 |

POST/operation 计数：stub 每次 generate 追加到系统临时目录
`%TEMP%/v21h6_stub_runtime/stub_posts.log`；每场景恰 +1 行。真实后端幂等另由 onedir
非侵入门禁（RESULT §41.3/R30）覆盖。

## 4. production 四区域注入（--prod-all / --prod-inject）预期


`VITE_H6_INJECT=pdf|overlay|basis|export` 各自 `npm run build`（exit 0）→ stub 同源托管该
dist → 浏览器完整「初始→生成中→成功」→ 目标区域抛错 → 应用级 ErrorBoundary 出现
（文案含「应用异常 / 页面渲染时出了点问题 / 重试页面渲染 / 返回生成工作台」）且 body 非空。
runner 还会继续断言恢复路径：点「重试页面渲染」在持续注入下仍受边界保护不白屏；点「返回生成
工作台」可离开故障结果页回到生成页；且本 target 生成 POST 增量 ≤1（恢复不新增 operation）。

注入产物仅为测试 build，不进入最终 onedir。正式无 env build（--verify）后由**纯 Python 遍历
frontend/dist** 检查（不依赖 GNU grep）：H6 注入标记/测试入口命中数为 0，并输出扫描文件数与命中数。

## 5. 清理与安全边界

- runner 会自行停止其启动的 stub/dev 并 `agent-browser close --all`。
- fixture/stub/matrix 全部为虚构内容；无真实 Key/身份/本机绝对路径/在线依赖；运行态
  mode 文件与计数在系统临时目录（不写仓库）。
- H6 测试资产不进入正式 onedir（PyInstaller 收集范围已核对：包内无 `_v21_h6*`/`h6_fixtures`，
  正式 JS strip=0，见 RESULT §41.3）。
