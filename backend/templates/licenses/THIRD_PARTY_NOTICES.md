# Third-Party Notices（V2.1.0 R17a）

ResumeAssistant 可再分发资源中包含以下第三方项目。本目录随源码入库，并随 onedir
打包进入 `_internal/licenses`（稳定可见；不依赖开发机 node_modules 或在线链接）。
完整许可证原文见同目录 `*.txt`（未经改写、完整文本）。

--------------------------------------------------------------------------------

## 1. Noto Sans SC（字体，随 PDF 渲染器子集内嵌）

- 上游项目：Google Noto CJK（[notofonts/noto-cjk](https://github.com/notofonts/noto-cjk)），
  字体主程序（Noto Sans SC）版权归 Adobe/Google 等贡献者，详见字体 name table 版权声明。
- 分发包/版本：npm 包 `@expo-google-fonts/noto-sans-sc@0.4.3`（内容为 Google Fonts 发布物）。
- 获取来源（下载 URL）：
  `https://cdn.jsdelivr.net/npm/@expo-google-fonts/noto-sans-sc@0.4.3/NotoSansSC-Regular.ttf`
- 原始文件名：`NotoSansSC-Regular.ttf`
- SHA-256：
  `d45f67f0a7c0ca3f256950777ce6a61cc7ce5f9696d02900cbbaac25f8aa7d16`
- 大小：10,559,284 字节
- 许可证：SIL Open Font License 1.1（OFL-1.1）。
  - 完整许可证全文（未经改写）：同目录 `NOTO-OFL.txt`。
  - 授权文本来源（不可变原始上游）：
    `https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/LICENSE`
    （raw 文件 SHA-256 `6a73f9541c2de74158c0e7cf6b0a58ef774f5a780bf191f2d7ec9cc53efe2bf2`）
  - OFL 官方参考：<http://scripts.sil.org/OFL> / <https://openfontlicense.org>
- 使用方式：reportlab `TTFont` 注册后子集化内嵌（/FontFile2）进生成的 PDF；
  仅内嵌 Regular 字重，不修改字体文件本身。

## 2. pdfjs-dist（前端 PDF 渲染运行时，内置 viewer）

- 上游项目：Mozilla pdf.js（<https://github.com/mozilla/pdf.js>）的 npm 构建产物。
- 分发包/版本：npm 包 `pdfjs-dist@4.10.38`（`frontend/package.json` dependencies 固定）。
- 获取来源：`npm ci`（lockfile `frontend/package-lock.json` 固定 4.10.38）。
- 许可证：Apache License 2.0。
  - 完整许可证全文（未经改写）：同目录 `PDFJS-APACHE2.txt`，与
    `frontend/node_modules/pdfjs-dist/LICENSE` 字节一致（SHA-256
    `0d542e0c8804e39aa7f37eb00da5a762149dc682d7829451287e11b938e94594`）。
- 使用方式：PDF 成品预览 viewer（`pdf.worker.min-*.mjs` 以独立 asset 随 frontend/dist 打包，
  无运行时 CDN 加载）。

--------------------------------------------------------------------------------

文件清单（本目录）：
- `NOTO-OFL.txt`      —— OFL 1.1 全文（Noto Sans SC 许可证）
- `PDFJS-APACHE2.txt` —— Apache License 2.0 全文（pdfjs-dist 许可证）
