# backend/h6_fixtures —— V2.1.0 H6 可移交确定性虚构测试资产（PLAN §18.2）

> 范围：T12-R28「固化虚构 fixture 与 runner」。本目录只被专项测试资产引用，**不进入正式
> 应用路由、普通构建入口或生产包**。

## 内容

| 文件 | 说明 |
|---|---|
| `resume_doc.json` | 虚构简历内容唯一来源（ResumeDocument 形状 + `bullet_fact_refs` + `evidence`）；`_meta.privacy_check` 登记虚构化检查 |
| `jd.txt` | 虚构岗位 JD（目标岗位语料） |
| `preview_anchors.json` | 冻结 PreviewAnchor 数据集：两页 PDF 实测坐标、多 section（education/work/project/skills）、空/非空 `fact_refs` 混排；`artifact_id` 为 token，运行态由 stub/矩阵替换 |
| `fixture_hashes.json` | 冻结时生成字节的 SHA-256 / size / pages（审计对照，矩阵断言再生成与之一致） |
| `identity_samples.json` | operation / artifact 身份与不变性/更换规则的字段样例 |
| `gen_fixtures.py` | 确定性生成器：`build_fixture_pdf()`（reportlab `invariant=1` 两页，注册仓库内 Noto 字体）与 `build_fixture_docx()`（python-docx + 固定时间戳/ZIP_STORED 确定性重打包） |

## 用法

```bash
# 直接预览生成结果（页数/哈希/锚点清单）
python backend/h6_fixtures/gen_fixtures.py

# 由矩阵入口统一驱动（推荐）：PDF/DOCX 生成与 hash 稳定、锚点一致性等全部断言
python backend/_v21_h6_matrix.py          # 要求末行 PASS=<N> FAIL=0、exit 0

# stub server（命令行起；详细参数见文件头 docstring）
python backend/_v21_h6_stub.py --port 8000
```

## 安全边界（must-read）

- 全部内容为虚构：姓名含占位字、电话用 `0000` 占位段、邮箱用 `.invalid` 保留域、
  公司/学校为合成名；无真实个人信息、无 API Key、无本机绝对路径、无在线依赖。
- 所有路径均由 `__file__` 仓库相对解析；运行不读写默认 runtime（需写运行态的模式/计数时
  由 stub 写到系统临时目录，见 `backend/_v21_h6_stub.py`）。
- 若把新真实信息放入任一 JSON/TXT，即违反 T12-R28 完成标准（评审将 grep 阻断）。
- 该包的确定性契约依赖 `backend/requirements.txt` 固定版本（reportlab==4.2.2、
  python-docx==1.2.0）与仓库内 `backend/templates/fonts/NotoSansSC-Regular.ttf`；
  升级任一依赖需重冻结本目录产物并记录于 RESULT。

## 浏览器半自动矩阵

需要 GUI/浏览器的部分（六组风险、四区域异常、Error Boundary 恢复、幂等）属半自动矩阵，
由 **T12-R29** 执行（见 `scripts/` 下的 H6 浏览器矩阵手册）；本目录只保证可被干净 checkout
的确定性入口复用的数据与生成器。
