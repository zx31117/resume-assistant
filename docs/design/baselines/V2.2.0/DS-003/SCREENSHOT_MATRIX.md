# Screenshot Matrix

> 原型：D003-0.11；浏览器：Chromium 152.0.7977.84；Device Scale Factor：1。
> 字体：Windows系统字体栈Microsoft YaHei/Arial；其余平台按CSS fallback，无CDN。

## 命名规则

`theme__workbench__scenario__widthxheight__1x.png`。文件名为小写ASCII，scenario可含短横线，不包含个人信息。

## 最低证据矩阵

旧模板的全产品流程逐项保留适用性说明；本轮为D-003生成工作台，并未重新实现整个产品。

| 页面 | Scenario | 1440×900 A/B/C | 1280×800 A/B/C | 1024×768 | 390×844 | 320×568 | 备注 |
|---|---|---|---|---|---|---|---|
| 冷启动 | 双路 | N/A | N/A | N/A | N/A | N/A | 未新增上传/无简历对话 |
| 上传 | default/loading/error | N/A | N/A | N/A | N/A | N/A | 沿用旧设计，不在本轮 |
| 提取确认 | conflict/partial | N/A | N/A | N/A | N/A | N/A | 没有本轮提取/冲突检测 |
| 我的经历 | list/edit | A列表 | A/B/C列表 | A/B/C | A/B/C | A/B/C | 编辑/确认另有交互断言；delete N/A |
| 生成输入 | saved/empty/blocked | saved A/B/C，其余A | saved A/B/C | saved A/B/C | saved A/B/C | saved A/B/C | 校验、材料不足另有三桌面A及断言 |
| 生成中 | p1/p2/p3/p4 | p3 A/B/C，其余A | p3 A/B/C | p3 A/B/C | p3 A/B/C | p3 A/B/C | 六十张A指定桌面矩阵 |
| 结果 | success/source | success A/B/C | A/B/C | A/B/C | A/B/C | A/B/C | 原文可按需展开 |
| 修改 | fact-correction | A经历 | A/B/C经历 | A/B/C | A/B/C | A/B/C | intent/current修订N/A |
| 失败恢复 | failed/retry | failed A/B/C，failed-p4 A | failed A/B/C | A/B/C | A/B/C | A/B/C | Word保留/PDF禁用另有断言 |
| 个人与隐私 | default | A | A/B/C | A/B/C | A/B/C | A/B/C | 清除范围可操作 |
| 开发后台 | status/config | N/A | N/A | N/A | N/A | N/A | 本轮没有新增后台 |

原任务指定1280×720、1440×900、1920×1080：主题A均覆盖20个场景。720×450为200%等效回流，六个核心场景覆盖A/B/C。截图检查区分机器几何校验和视觉抽查，未把未看图项目写成已人工复核。

## 文件索引

| ID | Theme | Page | Scenario | Viewport | Scale | 文件 | 复核 |
|---|---|---|---|---|---|---|---|
| SS-001 | A | workbench | cancel | 1280×720 | 1 | [a__workbench__cancel__1280x720__1x.png](previews/d003/a__workbench__cancel__1280x720__1x.png) | 机器校验 |
| SS-002 | A | workbench | cancel | 1440×900 | 1 | [a__workbench__cancel__1440x900__1x.png](previews/d003/a__workbench__cancel__1440x900__1x.png) | 机器校验 |
| SS-003 | A | workbench | cancel | 1920×1080 | 1 | [a__workbench__cancel__1920x1080__1x.png](previews/d003/a__workbench__cancel__1920x1080__1x.png) | 机器校验 |
| SS-004 | A | workbench | cancelled | 1280×720 | 1 | [a__workbench__cancelled__1280x720__1x.png](previews/d003/a__workbench__cancelled__1280x720__1x.png) | 机器校验 |
| SS-005 | A | workbench | cancelled | 1440×900 | 1 | [a__workbench__cancelled__1440x900__1x.png](previews/d003/a__workbench__cancelled__1440x900__1x.png) | 机器校验 |
| SS-006 | A | workbench | cancelled | 1920×1080 | 1 | [a__workbench__cancelled__1920x1080__1x.png](previews/d003/a__workbench__cancelled__1920x1080__1x.png) | 机器校验 |
| SS-007 | A | workbench | empty | 1280×720 | 1 | [a__workbench__empty__1280x720__1x.png](previews/d003/a__workbench__empty__1280x720__1x.png) | 机器校验 |
| SS-008 | A | workbench | empty | 1440×900 | 1 | [a__workbench__empty__1440x900__1x.png](previews/d003/a__workbench__empty__1440x900__1x.png) | 机器校验 |
| SS-009 | A | workbench | empty | 1920×1080 | 1 | [a__workbench__empty__1920x1080__1x.png](previews/d003/a__workbench__empty__1920x1080__1x.png) | 机器校验 |
| SS-010 | A | experiences | experiences | 1024×768 | 1 | [a__workbench__experiences__1024x768__1x.png](previews/d003/a__workbench__experiences__1024x768__1x.png) | 机器校验 |
| SS-011 | A | experiences | experiences | 1280×720 | 1 | [a__workbench__experiences__1280x720__1x.png](previews/d003/a__workbench__experiences__1280x720__1x.png) | 机器校验 |
| SS-012 | A | experiences | experiences | 1280×800 | 1 | [a__workbench__experiences__1280x800__1x.png](previews/d003/a__workbench__experiences__1280x800__1x.png) | 机器校验 |
| SS-013 | A | experiences | experiences | 1440×900 | 1 | [a__workbench__experiences__1440x900__1x.png](previews/d003/a__workbench__experiences__1440x900__1x.png) | 机器校验 |
| SS-014 | A | experiences | experiences | 1920×1080 | 1 | [a__workbench__experiences__1920x1080__1x.png](previews/d003/a__workbench__experiences__1920x1080__1x.png) | 机器校验 |
| SS-015 | A | experiences | experiences | 320×568 | 1 | [a__workbench__experiences__320x568__1x.png](previews/d003/a__workbench__experiences__320x568__1x.png) | 机器校验 + 视觉抽查 |
| SS-016 | A | experiences | experiences | 390×844 | 1 | [a__workbench__experiences__390x844__1x.png](previews/d003/a__workbench__experiences__390x844__1x.png) | 机器校验 |
| SS-017 | A | experiences | experiences | 720×450 | 1 | [a__workbench__experiences__720x450__1x.png](previews/d003/a__workbench__experiences__720x450__1x.png) | 机器校验 |
| SS-018 | A | workbench | failed-p4 | 1280×720 | 1 | [a__workbench__failed-p4__1280x720__1x.png](previews/d003/a__workbench__failed-p4__1280x720__1x.png) | 机器校验 |
| SS-019 | A | workbench | failed-p4 | 1440×900 | 1 | [a__workbench__failed-p4__1440x900__1x.png](previews/d003/a__workbench__failed-p4__1440x900__1x.png) | 机器校验 |
| SS-020 | A | workbench | failed-p4 | 1920×1080 | 1 | [a__workbench__failed-p4__1920x1080__1x.png](previews/d003/a__workbench__failed-p4__1920x1080__1x.png) | 机器校验 |
| SS-021 | A | workbench | failed | 1024×768 | 1 | [a__workbench__failed__1024x768__1x.png](previews/d003/a__workbench__failed__1024x768__1x.png) | 机器校验 |
| SS-022 | A | workbench | failed | 1280×720 | 1 | [a__workbench__failed__1280x720__1x.png](previews/d003/a__workbench__failed__1280x720__1x.png) | 机器校验 |
| SS-023 | A | workbench | failed | 1280×800 | 1 | [a__workbench__failed__1280x800__1x.png](previews/d003/a__workbench__failed__1280x800__1x.png) | 机器校验 |
| SS-024 | A | workbench | failed | 1440×900 | 1 | [a__workbench__failed__1440x900__1x.png](previews/d003/a__workbench__failed__1440x900__1x.png) | 机器校验 |
| SS-025 | A | workbench | failed | 1920×1080 | 1 | [a__workbench__failed__1920x1080__1x.png](previews/d003/a__workbench__failed__1920x1080__1x.png) | 机器校验 |
| SS-026 | A | workbench | failed | 320×568 | 1 | [a__workbench__failed__320x568__1x.png](previews/d003/a__workbench__failed__320x568__1x.png) | 机器校验 |
| SS-027 | A | workbench | failed | 390×844 | 1 | [a__workbench__failed__390x844__1x.png](previews/d003/a__workbench__failed__390x844__1x.png) | 机器校验 |
| SS-028 | A | workbench | failed | 720×450 | 1 | [a__workbench__failed__720x450__1x.png](previews/d003/a__workbench__failed__720x450__1x.png) | 机器校验 + 视觉抽查 |
| SS-029 | A | workbench | history-p1 | 1280×720 | 1 | [a__workbench__history-p1__1280x720__1x.png](previews/d003/a__workbench__history-p1__1280x720__1x.png) | 机器校验 |
| SS-030 | A | workbench | history-p1 | 1440×900 | 1 | [a__workbench__history-p1__1440x900__1x.png](previews/d003/a__workbench__history-p1__1440x900__1x.png) | 机器校验 |
| SS-031 | A | workbench | history-p1 | 1920×1080 | 1 | [a__workbench__history-p1__1920x1080__1x.png](previews/d003/a__workbench__history-p1__1920x1080__1x.png) | 机器校验 |
| SS-032 | A | workbench | history-p2 | 1280×720 | 1 | [a__workbench__history-p2__1280x720__1x.png](previews/d003/a__workbench__history-p2__1280x720__1x.png) | 机器校验 |
| SS-033 | A | workbench | history-p2 | 1440×900 | 1 | [a__workbench__history-p2__1440x900__1x.png](previews/d003/a__workbench__history-p2__1440x900__1x.png) | 机器校验 |
| SS-034 | A | workbench | history-p2 | 1920×1080 | 1 | [a__workbench__history-p2__1920x1080__1x.png](previews/d003/a__workbench__history-p2__1920x1080__1x.png) | 机器校验 |
| SS-035 | A | workbench | insufficient | 1280×720 | 1 | [a__workbench__insufficient__1280x720__1x.png](previews/d003/a__workbench__insufficient__1280x720__1x.png) | 机器校验 |
| SS-036 | A | workbench | insufficient | 1440×900 | 1 | [a__workbench__insufficient__1440x900__1x.png](previews/d003/a__workbench__insufficient__1440x900__1x.png) | 机器校验 |
| SS-037 | A | workbench | insufficient | 1920×1080 | 1 | [a__workbench__insufficient__1920x1080__1x.png](previews/d003/a__workbench__insufficient__1920x1080__1x.png) | 机器校验 |
| SS-038 | A | workbench | menu | 1280×720 | 1 | [a__workbench__menu__1280x720__1x.png](previews/d003/a__workbench__menu__1280x720__1x.png) | 机器校验 |
| SS-039 | A | workbench | menu | 1440×900 | 1 | [a__workbench__menu__1440x900__1x.png](previews/d003/a__workbench__menu__1440x900__1x.png) | 机器校验 |
| SS-040 | A | workbench | menu | 1920×1080 | 1 | [a__workbench__menu__1920x1080__1x.png](previews/d003/a__workbench__menu__1920x1080__1x.png) | 机器校验 |
| SS-041 | A | workbench | p1 | 1280×720 | 1 | [a__workbench__p1__1280x720__1x.png](previews/d003/a__workbench__p1__1280x720__1x.png) | 机器校验 |
| SS-042 | A | workbench | p1 | 1440×900 | 1 | [a__workbench__p1__1440x900__1x.png](previews/d003/a__workbench__p1__1440x900__1x.png) | 机器校验 |
| SS-043 | A | workbench | p1 | 1920×1080 | 1 | [a__workbench__p1__1920x1080__1x.png](previews/d003/a__workbench__p1__1920x1080__1x.png) | 机器校验 |
| SS-044 | A | workbench | p2 | 1280×720 | 1 | [a__workbench__p2__1280x720__1x.png](previews/d003/a__workbench__p2__1280x720__1x.png) | 机器校验 |
| SS-045 | A | workbench | p2 | 1440×900 | 1 | [a__workbench__p2__1440x900__1x.png](previews/d003/a__workbench__p2__1440x900__1x.png) | 机器校验 |
| SS-046 | A | workbench | p2 | 1920×1080 | 1 | [a__workbench__p2__1920x1080__1x.png](previews/d003/a__workbench__p2__1920x1080__1x.png) | 机器校验 |
| SS-047 | A | workbench | p3 | 1024×768 | 1 | [a__workbench__p3__1024x768__1x.png](previews/d003/a__workbench__p3__1024x768__1x.png) | 机器校验 |
| SS-048 | A | workbench | p3 | 1280×720 | 1 | [a__workbench__p3__1280x720__1x.png](previews/d003/a__workbench__p3__1280x720__1x.png) | 机器校验 |
| SS-049 | A | workbench | p3 | 1280×800 | 1 | [a__workbench__p3__1280x800__1x.png](previews/d003/a__workbench__p3__1280x800__1x.png) | 机器校验 |
| SS-050 | A | workbench | p3 | 1440×900 | 1 | [a__workbench__p3__1440x900__1x.png](previews/d003/a__workbench__p3__1440x900__1x.png) | 机器校验 + 视觉抽查 |
| SS-051 | A | workbench | p3 | 1920×1080 | 1 | [a__workbench__p3__1920x1080__1x.png](previews/d003/a__workbench__p3__1920x1080__1x.png) | 机器校验 |
| SS-052 | A | workbench | p3 | 320×568 | 1 | [a__workbench__p3__320x568__1x.png](previews/d003/a__workbench__p3__320x568__1x.png) | 机器校验 |
| SS-053 | A | workbench | p3 | 390×844 | 1 | [a__workbench__p3__390x844__1x.png](previews/d003/a__workbench__p3__390x844__1x.png) | 机器校验 |
| SS-054 | A | workbench | p3 | 720×450 | 1 | [a__workbench__p3__720x450__1x.png](previews/d003/a__workbench__p3__720x450__1x.png) | 机器校验 |
| SS-055 | A | workbench | p4 | 1280×720 | 1 | [a__workbench__p4__1280x720__1x.png](previews/d003/a__workbench__p4__1280x720__1x.png) | 机器校验 |
| SS-056 | A | workbench | p4 | 1440×900 | 1 | [a__workbench__p4__1440x900__1x.png](previews/d003/a__workbench__p4__1440x900__1x.png) | 机器校验 |
| SS-057 | A | workbench | p4 | 1920×1080 | 1 | [a__workbench__p4__1920x1080__1x.png](previews/d003/a__workbench__p4__1920x1080__1x.png) | 机器校验 |
| SS-058 | A | privacy | privacy | 1024×768 | 1 | [a__workbench__privacy__1024x768__1x.png](previews/d003/a__workbench__privacy__1024x768__1x.png) | 机器校验 |
| SS-059 | A | privacy | privacy | 1280×720 | 1 | [a__workbench__privacy__1280x720__1x.png](previews/d003/a__workbench__privacy__1280x720__1x.png) | 机器校验 |
| SS-060 | A | privacy | privacy | 1280×800 | 1 | [a__workbench__privacy__1280x800__1x.png](previews/d003/a__workbench__privacy__1280x800__1x.png) | 机器校验 |
| SS-061 | A | privacy | privacy | 1440×900 | 1 | [a__workbench__privacy__1440x900__1x.png](previews/d003/a__workbench__privacy__1440x900__1x.png) | 机器校验 |
| SS-062 | A | privacy | privacy | 1920×1080 | 1 | [a__workbench__privacy__1920x1080__1x.png](previews/d003/a__workbench__privacy__1920x1080__1x.png) | 机器校验 |
| SS-063 | A | privacy | privacy | 320×568 | 1 | [a__workbench__privacy__320x568__1x.png](previews/d003/a__workbench__privacy__320x568__1x.png) | 机器校验 |
| SS-064 | A | privacy | privacy | 390×844 | 1 | [a__workbench__privacy__390x844__1x.png](previews/d003/a__workbench__privacy__390x844__1x.png) | 机器校验 |
| SS-065 | A | privacy | privacy | 720×450 | 1 | [a__workbench__privacy__720x450__1x.png](previews/d003/a__workbench__privacy__720x450__1x.png) | 机器校验 |
| SS-066 | A | records | records | 1280×720 | 1 | [a__workbench__records__1280x720__1x.png](previews/d003/a__workbench__records__1280x720__1x.png) | 机器校验 |
| SS-067 | A | records | records | 1440×900 | 1 | [a__workbench__records__1440x900__1x.png](previews/d003/a__workbench__records__1440x900__1x.png) | 机器校验 |
| SS-068 | A | records | records | 1920×1080 | 1 | [a__workbench__records__1920x1080__1x.png](previews/d003/a__workbench__records__1920x1080__1x.png) | 机器校验 |
| SS-069 | A | workbench | restored | 1280×720 | 1 | [a__workbench__restored__1280x720__1x.png](previews/d003/a__workbench__restored__1280x720__1x.png) | 机器校验 |
| SS-070 | A | workbench | restored | 1440×900 | 1 | [a__workbench__restored__1440x900__1x.png](previews/d003/a__workbench__restored__1440x900__1x.png) | 机器校验 |
| SS-071 | A | workbench | restored | 1920×1080 | 1 | [a__workbench__restored__1920x1080__1x.png](previews/d003/a__workbench__restored__1920x1080__1x.png) | 机器校验 |
| SS-072 | A | workbench | saved | 1024×768 | 1 | [a__workbench__saved__1024x768__1x.png](previews/d003/a__workbench__saved__1024x768__1x.png) | 机器校验 |
| SS-073 | A | workbench | saved | 1280×720 | 1 | [a__workbench__saved__1280x720__1x.png](previews/d003/a__workbench__saved__1280x720__1x.png) | 机器校验 |
| SS-074 | A | workbench | saved | 1280×800 | 1 | [a__workbench__saved__1280x800__1x.png](previews/d003/a__workbench__saved__1280x800__1x.png) | 机器校验 |
| SS-075 | A | workbench | saved | 1440×900 | 1 | [a__workbench__saved__1440x900__1x.png](previews/d003/a__workbench__saved__1440x900__1x.png) | 机器校验 |
| SS-076 | A | workbench | saved | 1920×1080 | 1 | [a__workbench__saved__1920x1080__1x.png](previews/d003/a__workbench__saved__1920x1080__1x.png) | 机器校验 |
| SS-077 | A | workbench | saved | 320×568 | 1 | [a__workbench__saved__320x568__1x.png](previews/d003/a__workbench__saved__320x568__1x.png) | 机器校验 + 视觉抽查 |
| SS-078 | A | workbench | saved | 390×844 | 1 | [a__workbench__saved__390x844__1x.png](previews/d003/a__workbench__saved__390x844__1x.png) | 机器校验 |
| SS-079 | A | workbench | saved | 720×450 | 1 | [a__workbench__saved__720x450__1x.png](previews/d003/a__workbench__saved__720x450__1x.png) | 机器校验 |
| SS-080 | A | workbench | saving | 1280×720 | 1 | [a__workbench__saving__1280x720__1x.png](previews/d003/a__workbench__saving__1280x720__1x.png) | 机器校验 |
| SS-081 | A | workbench | saving | 1440×900 | 1 | [a__workbench__saving__1440x900__1x.png](previews/d003/a__workbench__saving__1440x900__1x.png) | 机器校验 |
| SS-082 | A | workbench | saving | 1920×1080 | 1 | [a__workbench__saving__1920x1080__1x.png](previews/d003/a__workbench__saving__1920x1080__1x.png) | 机器校验 |
| SS-083 | A | workbench | success | 1024×768 | 1 | [a__workbench__success__1024x768__1x.png](previews/d003/a__workbench__success__1024x768__1x.png) | 机器校验 |
| SS-084 | A | workbench | success | 1280×720 | 1 | [a__workbench__success__1280x720__1x.png](previews/d003/a__workbench__success__1280x720__1x.png) | 机器校验 |
| SS-085 | A | workbench | success | 1280×800 | 1 | [a__workbench__success__1280x800__1x.png](previews/d003/a__workbench__success__1280x800__1x.png) | 机器校验 |
| SS-086 | A | workbench | success | 1440×900 | 1 | [a__workbench__success__1440x900__1x.png](previews/d003/a__workbench__success__1440x900__1x.png) | 机器校验 + 视觉抽查 |
| SS-087 | A | workbench | success | 1920×1080 | 1 | [a__workbench__success__1920x1080__1x.png](previews/d003/a__workbench__success__1920x1080__1x.png) | 机器校验 |
| SS-088 | A | workbench | success | 320×568 | 1 | [a__workbench__success__320x568__1x.png](previews/d003/a__workbench__success__320x568__1x.png) | 机器校验 |
| SS-089 | A | workbench | success | 390×844 | 1 | [a__workbench__success__390x844__1x.png](previews/d003/a__workbench__success__390x844__1x.png) | 机器校验 |
| SS-090 | A | workbench | success | 720×450 | 1 | [a__workbench__success__720x450__1x.png](previews/d003/a__workbench__success__720x450__1x.png) | 机器校验 |
| SS-091 | B | experiences | experiences | 1024×768 | 1 | [b__workbench__experiences__1024x768__1x.png](previews/d003/b__workbench__experiences__1024x768__1x.png) | 机器校验 |
| SS-092 | B | experiences | experiences | 1280×800 | 1 | [b__workbench__experiences__1280x800__1x.png](previews/d003/b__workbench__experiences__1280x800__1x.png) | 机器校验 |
| SS-093 | B | experiences | experiences | 320×568 | 1 | [b__workbench__experiences__320x568__1x.png](previews/d003/b__workbench__experiences__320x568__1x.png) | 机器校验 |
| SS-094 | B | experiences | experiences | 390×844 | 1 | [b__workbench__experiences__390x844__1x.png](previews/d003/b__workbench__experiences__390x844__1x.png) | 机器校验 |
| SS-095 | B | experiences | experiences | 720×450 | 1 | [b__workbench__experiences__720x450__1x.png](previews/d003/b__workbench__experiences__720x450__1x.png) | 机器校验 |
| SS-096 | B | workbench | failed | 1024×768 | 1 | [b__workbench__failed__1024x768__1x.png](previews/d003/b__workbench__failed__1024x768__1x.png) | 机器校验 |
| SS-097 | B | workbench | failed | 1280×800 | 1 | [b__workbench__failed__1280x800__1x.png](previews/d003/b__workbench__failed__1280x800__1x.png) | 机器校验 |
| SS-098 | B | workbench | failed | 1440×900 | 1 | [b__workbench__failed__1440x900__1x.png](previews/d003/b__workbench__failed__1440x900__1x.png) | 机器校验 |
| SS-099 | B | workbench | failed | 320×568 | 1 | [b__workbench__failed__320x568__1x.png](previews/d003/b__workbench__failed__320x568__1x.png) | 机器校验 |
| SS-100 | B | workbench | failed | 390×844 | 1 | [b__workbench__failed__390x844__1x.png](previews/d003/b__workbench__failed__390x844__1x.png) | 机器校验 |
| SS-101 | B | workbench | failed | 720×450 | 1 | [b__workbench__failed__720x450__1x.png](previews/d003/b__workbench__failed__720x450__1x.png) | 机器校验 |
| SS-102 | B | workbench | p3 | 1024×768 | 1 | [b__workbench__p3__1024x768__1x.png](previews/d003/b__workbench__p3__1024x768__1x.png) | 机器校验 |
| SS-103 | B | workbench | p3 | 1280×800 | 1 | [b__workbench__p3__1280x800__1x.png](previews/d003/b__workbench__p3__1280x800__1x.png) | 机器校验 |
| SS-104 | B | workbench | p3 | 1440×900 | 1 | [b__workbench__p3__1440x900__1x.png](previews/d003/b__workbench__p3__1440x900__1x.png) | 机器校验 |
| SS-105 | B | workbench | p3 | 320×568 | 1 | [b__workbench__p3__320x568__1x.png](previews/d003/b__workbench__p3__320x568__1x.png) | 机器校验 |
| SS-106 | B | workbench | p3 | 390×844 | 1 | [b__workbench__p3__390x844__1x.png](previews/d003/b__workbench__p3__390x844__1x.png) | 机器校验 + 视觉抽查 |
| SS-107 | B | workbench | p3 | 720×450 | 1 | [b__workbench__p3__720x450__1x.png](previews/d003/b__workbench__p3__720x450__1x.png) | 机器校验 |
| SS-108 | B | privacy | privacy | 1024×768 | 1 | [b__workbench__privacy__1024x768__1x.png](previews/d003/b__workbench__privacy__1024x768__1x.png) | 机器校验 |
| SS-109 | B | privacy | privacy | 1280×800 | 1 | [b__workbench__privacy__1280x800__1x.png](previews/d003/b__workbench__privacy__1280x800__1x.png) | 机器校验 |
| SS-110 | B | privacy | privacy | 320×568 | 1 | [b__workbench__privacy__320x568__1x.png](previews/d003/b__workbench__privacy__320x568__1x.png) | 机器校验 |
| SS-111 | B | privacy | privacy | 390×844 | 1 | [b__workbench__privacy__390x844__1x.png](previews/d003/b__workbench__privacy__390x844__1x.png) | 机器校验 |
| SS-112 | B | privacy | privacy | 720×450 | 1 | [b__workbench__privacy__720x450__1x.png](previews/d003/b__workbench__privacy__720x450__1x.png) | 机器校验 |
| SS-113 | B | workbench | saved | 1024×768 | 1 | [b__workbench__saved__1024x768__1x.png](previews/d003/b__workbench__saved__1024x768__1x.png) | 机器校验 |
| SS-114 | B | workbench | saved | 1280×800 | 1 | [b__workbench__saved__1280x800__1x.png](previews/d003/b__workbench__saved__1280x800__1x.png) | 机器校验 |
| SS-115 | B | workbench | saved | 1440×900 | 1 | [b__workbench__saved__1440x900__1x.png](previews/d003/b__workbench__saved__1440x900__1x.png) | 机器校验 |
| SS-116 | B | workbench | saved | 320×568 | 1 | [b__workbench__saved__320x568__1x.png](previews/d003/b__workbench__saved__320x568__1x.png) | 机器校验 |
| SS-117 | B | workbench | saved | 390×844 | 1 | [b__workbench__saved__390x844__1x.png](previews/d003/b__workbench__saved__390x844__1x.png) | 机器校验 |
| SS-118 | B | workbench | saved | 720×450 | 1 | [b__workbench__saved__720x450__1x.png](previews/d003/b__workbench__saved__720x450__1x.png) | 机器校验 |
| SS-119 | B | workbench | success | 1024×768 | 1 | [b__workbench__success__1024x768__1x.png](previews/d003/b__workbench__success__1024x768__1x.png) | 机器校验 |
| SS-120 | B | workbench | success | 1280×800 | 1 | [b__workbench__success__1280x800__1x.png](previews/d003/b__workbench__success__1280x800__1x.png) | 机器校验 + 视觉抽查 |
| SS-121 | B | workbench | success | 1440×900 | 1 | [b__workbench__success__1440x900__1x.png](previews/d003/b__workbench__success__1440x900__1x.png) | 机器校验 |
| SS-122 | B | workbench | success | 320×568 | 1 | [b__workbench__success__320x568__1x.png](previews/d003/b__workbench__success__320x568__1x.png) | 机器校验 |
| SS-123 | B | workbench | success | 390×844 | 1 | [b__workbench__success__390x844__1x.png](previews/d003/b__workbench__success__390x844__1x.png) | 机器校验 |
| SS-124 | B | workbench | success | 720×450 | 1 | [b__workbench__success__720x450__1x.png](previews/d003/b__workbench__success__720x450__1x.png) | 机器校验 |
| SS-125 | C | experiences | experiences | 1024×768 | 1 | [c__workbench__experiences__1024x768__1x.png](previews/d003/c__workbench__experiences__1024x768__1x.png) | 机器校验 |
| SS-126 | C | experiences | experiences | 1280×800 | 1 | [c__workbench__experiences__1280x800__1x.png](previews/d003/c__workbench__experiences__1280x800__1x.png) | 机器校验 |
| SS-127 | C | experiences | experiences | 320×568 | 1 | [c__workbench__experiences__320x568__1x.png](previews/d003/c__workbench__experiences__320x568__1x.png) | 机器校验 |
| SS-128 | C | experiences | experiences | 390×844 | 1 | [c__workbench__experiences__390x844__1x.png](previews/d003/c__workbench__experiences__390x844__1x.png) | 机器校验 |
| SS-129 | C | experiences | experiences | 720×450 | 1 | [c__workbench__experiences__720x450__1x.png](previews/d003/c__workbench__experiences__720x450__1x.png) | 机器校验 |
| SS-130 | C | workbench | failed | 1024×768 | 1 | [c__workbench__failed__1024x768__1x.png](previews/d003/c__workbench__failed__1024x768__1x.png) | 机器校验 |
| SS-131 | C | workbench | failed | 1280×800 | 1 | [c__workbench__failed__1280x800__1x.png](previews/d003/c__workbench__failed__1280x800__1x.png) | 机器校验 |
| SS-132 | C | workbench | failed | 1440×900 | 1 | [c__workbench__failed__1440x900__1x.png](previews/d003/c__workbench__failed__1440x900__1x.png) | 机器校验 |
| SS-133 | C | workbench | failed | 320×568 | 1 | [c__workbench__failed__320x568__1x.png](previews/d003/c__workbench__failed__320x568__1x.png) | 机器校验 |
| SS-134 | C | workbench | failed | 390×844 | 1 | [c__workbench__failed__390x844__1x.png](previews/d003/c__workbench__failed__390x844__1x.png) | 机器校验 |
| SS-135 | C | workbench | failed | 720×450 | 1 | [c__workbench__failed__720x450__1x.png](previews/d003/c__workbench__failed__720x450__1x.png) | 机器校验 |
| SS-136 | C | workbench | p3 | 1024×768 | 1 | [c__workbench__p3__1024x768__1x.png](previews/d003/c__workbench__p3__1024x768__1x.png) | 机器校验 |
| SS-137 | C | workbench | p3 | 1280×800 | 1 | [c__workbench__p3__1280x800__1x.png](previews/d003/c__workbench__p3__1280x800__1x.png) | 机器校验 |
| SS-138 | C | workbench | p3 | 1440×900 | 1 | [c__workbench__p3__1440x900__1x.png](previews/d003/c__workbench__p3__1440x900__1x.png) | 机器校验 |
| SS-139 | C | workbench | p3 | 320×568 | 1 | [c__workbench__p3__320x568__1x.png](previews/d003/c__workbench__p3__320x568__1x.png) | 机器校验 |
| SS-140 | C | workbench | p3 | 390×844 | 1 | [c__workbench__p3__390x844__1x.png](previews/d003/c__workbench__p3__390x844__1x.png) | 机器校验 |
| SS-141 | C | workbench | p3 | 720×450 | 1 | [c__workbench__p3__720x450__1x.png](previews/d003/c__workbench__p3__720x450__1x.png) | 机器校验 |
| SS-142 | C | privacy | privacy | 1024×768 | 1 | [c__workbench__privacy__1024x768__1x.png](previews/d003/c__workbench__privacy__1024x768__1x.png) | 机器校验 |
| SS-143 | C | privacy | privacy | 1280×800 | 1 | [c__workbench__privacy__1280x800__1x.png](previews/d003/c__workbench__privacy__1280x800__1x.png) | 机器校验 |
| SS-144 | C | privacy | privacy | 320×568 | 1 | [c__workbench__privacy__320x568__1x.png](previews/d003/c__workbench__privacy__320x568__1x.png) | 机器校验 + 视觉抽查 |
| SS-145 | C | privacy | privacy | 390×844 | 1 | [c__workbench__privacy__390x844__1x.png](previews/d003/c__workbench__privacy__390x844__1x.png) | 机器校验 |
| SS-146 | C | privacy | privacy | 720×450 | 1 | [c__workbench__privacy__720x450__1x.png](previews/d003/c__workbench__privacy__720x450__1x.png) | 机器校验 |
| SS-147 | C | workbench | saved | 1024×768 | 1 | [c__workbench__saved__1024x768__1x.png](previews/d003/c__workbench__saved__1024x768__1x.png) | 机器校验 |
| SS-148 | C | workbench | saved | 1280×800 | 1 | [c__workbench__saved__1280x800__1x.png](previews/d003/c__workbench__saved__1280x800__1x.png) | 机器校验 |
| SS-149 | C | workbench | saved | 1440×900 | 1 | [c__workbench__saved__1440x900__1x.png](previews/d003/c__workbench__saved__1440x900__1x.png) | 机器校验 |
| SS-150 | C | workbench | saved | 320×568 | 1 | [c__workbench__saved__320x568__1x.png](previews/d003/c__workbench__saved__320x568__1x.png) | 机器校验 |
| SS-151 | C | workbench | saved | 390×844 | 1 | [c__workbench__saved__390x844__1x.png](previews/d003/c__workbench__saved__390x844__1x.png) | 机器校验 |
| SS-152 | C | workbench | saved | 720×450 | 1 | [c__workbench__saved__720x450__1x.png](previews/d003/c__workbench__saved__720x450__1x.png) | 机器校验 |
| SS-153 | C | workbench | success | 1024×768 | 1 | [c__workbench__success__1024x768__1x.png](previews/d003/c__workbench__success__1024x768__1x.png) | 机器校验 |
| SS-154 | C | workbench | success | 1280×800 | 1 | [c__workbench__success__1280x800__1x.png](previews/d003/c__workbench__success__1280x800__1x.png) | 机器校验 |
| SS-155 | C | workbench | success | 1440×900 | 1 | [c__workbench__success__1440x900__1x.png](previews/d003/c__workbench__success__1440x900__1x.png) | 机器校验 |
| SS-156 | C | workbench | success | 320×568 | 1 | [c__workbench__success__320x568__1x.png](previews/d003/c__workbench__success__320x568__1x.png) | 机器校验 |
| SS-157 | C | workbench | success | 390×844 | 1 | [c__workbench__success__390x844__1x.png](previews/d003/c__workbench__success__390x844__1x.png) | 机器校验 + 视觉抽查 |
| SS-158 | C | workbench | success | 720×450 | 1 | [c__workbench__success__720x450__1x.png](previews/d003/c__workbench__success__720x450__1x.png) | 机器校验 |
