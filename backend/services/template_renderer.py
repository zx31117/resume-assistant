"""V1.2 标准化模板渲染器。

核心职责：
  1. 加载 pm_template.docx + pm_template.json（通过 docx_writer.load_template_assets）
  2. 按 section_spec.type 分派到不同渲染函数（profile / education / work / project / skills / awards）
  3. 按 title_style（命名样式名）定位章节锚点，靠 item_block[].style 找原型段，**不依赖文本匹配**
  4. 克隆原型段 → fill_placeholders 替换占位符 → 插入到锚点之后 → 删除原型段
  5. 收集 warnings（用于 generate-report 展示）

不做：
  - 经历裁剪（在 ResumeBuilder.build() 里已裁完）
  - 改字体 / 改事实内容
  - 文本框 / 坐标处理（V1.2 标准模板里没有文本框）

V1.3 T8：
  - 渲染完后扫描所有 paragraphs + tables cells，检出未替换占位符（{{xxx}} / [[xxx]]）加入 warnings；
  - 绝不"内容级 truncate"（不删 bullet 文本、不删条目），只按 section.max_items 保险兜底（裁剪前移至 Builder）。
"""
from __future__ import annotations

import os
import re
from typing import Optional

from docx import Document
from docx.text.paragraph import Paragraph

from models.template_schema import TemplateSpec, SectionSpec, RowSpec
from models.resume_document import ResumeDocument
from services import docx_writer
from services.docx_writer import TemplateError

# V1.3 T8：未替换占位符扫描（两种风格都要检，避免遗留模板字符串）
_PH_PATTERNS = [
    re.compile(r"\{\{([^{}]+)\}\}"),       # {{placeholder}}
    re.compile(r"\[\[([^\[\]]+)\]\]"),     # [[placeholder]]
]


class TemplateRenderer:
    """按 TemplateSpec 把 ResumeDocument 渲染进 DOCX。"""

    def __init__(self, template_id: str, backend_root: Optional[str] = None):
        """加载模板资产。

        backend_root: backend/ 目录的绝对路径。未提供时默认取本文件上两级。
        """
        if backend_root is None:
            backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        self.backend_root = backend_root
        self.template_id = template_id
        self.doc, self.spec = docx_writer.load_template_assets(template_id, backend_root)
        self.warnings: list[str] = []

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    def render(self, resume_doc: ResumeDocument) -> tuple[Document, list[str], dict]:
        """渲染并返回 (填充后的 doc, warnings 列表, render_stats dict)。

        调用方负责 Document.save(path) 存盘。

        V1.3 T8 新增：
          - 渲染完扫描是否有 {{...}} / [[...]] 未替换占位符；
          - 返回 render_stats，内含 education/work/projects 渲染前后条目数对照
            （用于 PLAN §8.2 验证 Renderer 输入输出条目集合一致、不截断）。
        """
        input_counts: dict[str, int] = {
            "education": len(resume_doc.education),
            "work": len(resume_doc.work),
            "projects": len(resume_doc.projects),
            "awards": len(resume_doc.awards),
            "skills": len(resume_doc.skills),
        }
        for section in self.spec.sections:
            try:
                if section.type == "profile":
                    self._render_profile(section, resume_doc)
                elif section.type == "summary":
                    self._render_summary(section, resume_doc)
                elif section.type == "education":
                    self._render_item_section(
                        section, resume_doc.education,
                        ctx_prefix="edu", resume_doc=resume_doc,
                    )
                elif section.type == "work":
                    self._render_item_section(
                        section, resume_doc.work,
                        ctx_prefix="work", resume_doc=resume_doc,
                    )
                elif section.type == "project":
                    self._render_item_section(
                        section, resume_doc.projects,
                        ctx_prefix="project", resume_doc=resume_doc,
                    )
                elif section.type == "skills":
                    self._render_skills(section, resume_doc)
                elif section.type == "awards":
                    self._render_awards(section, resume_doc)
                else:  # other
                    self.warnings.append(f"章节[{section.id}]类型={section.type!r}无渲染处理，已跳过")
            except TemplateError as e:
                # 把模板错误累积成 warning（但 required=true 的章节还是要抛）
                if section.required:
                    raise
                self.warnings.append(str(e))
        # 注：V1.2 PDF 布局复刻版起参照 PDF 布局，bullet 行全部常规字体，不再做关键词加粗后处理

        # V1.3 T8：未替换占位符扫描（不抛异常，只加 warnings，严重时人工复核）
        unreplaced_found = self._scan_unreplaced_placeholders()

        # T8 渲染层条目数对照（和 Builder max_items 裁剪不同；若此处 rendered < input 属于 Renderer 越权截断）
        section_counts: list[dict] = []
        # 用模板 spec.section.id 做 section_id：education/work/project/awards/skills
        mapping: dict[str, int] = {
            "education": input_counts["education"],
            "work": input_counts["work"],
            "project": input_counts["projects"],
            "awards": input_counts["awards"],
            "skills": input_counts["skills"],
        }
        rendered_counts: dict[str, int] = self._count_rendered_items()
        # capacity_warnings：
        #   - section.max_items 保险裁剪（_render_item_section 已写入 self.warnings）
        #   - 事实保护标题行占位符全空（同上）
        capacity_warnings: list[str] = [w for w in self.warnings if any(
            k in w for k in [
                "超过模板上限", "占位符全为空",
            ]
        )]
        for sec in self.spec.sections:
            if sec.type in {"profile", "summary"}:
                continue
            input_n = mapping.get(sec.type, 0)
            rendered_n = rendered_counts.get(sec.id, rendered_counts.get(sec.type, 0))
            section_counts.append({
                "section_id": sec.id,
                "input_items": input_n,
                "rendered_items": rendered_n,
            })
        render_stats = {
            "sections": section_counts,
            "unreplaced_placeholders": sorted(unreplaced_found),
            "capacity_warnings": capacity_warnings,
        }
        return self.doc, self.warnings, render_stats

    def _count_rendered_items(self) -> dict[str, int]:
        """粗略但可重复的条目数计数方式：按 item_block 的第一个 style 在最终 doc 中出现的次数。

        对 V1 内置 pm_template 足够稳定（item_block 首段一定是 {ctx}_Section_Role 等独有的 section 风格）。
        """
        from services import docx_writer  # lazy
        counts: dict[str, int] = {}
        for sec in self.spec.sections:
            if sec.type in {"profile", "summary"}:
                continue
            ib = sec.item_block or []
            if not ib:
                counts[sec.id] = 0
                continue
            first_style = ib[0].style
            counts[sec.id] = len(docx_writer.find_paragraphs_by_style(self.doc, first_style))
        return counts

    def _scan_unreplaced_placeholders(self) -> set[str]:
        """扫描全文，检出未替换占位符，去重后加入 warnings。

        返回命中的占位符集合（供 render_stats 记录）。
        """
        found: set[str] = set()
        # paragraphs
        for p in self.doc.paragraphs:
            for pattern in _PH_PATTERNS:
                for m in pattern.finditer(p.text):
                    found.add(m.group(0))
        # tables
        for table in self.doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for pattern in _PH_PATTERNS:
                        for m in pattern.finditer(cell.text):
                            found.add(m.group(0))
        if found:
            examples = sorted(found)[:8]
            self.warnings.append(
                f"渲染后仍检测到 {len(found)} 处未替换占位符（可能是模板 bug 或数据缺失），样例: {examples}"
            )
        return found


    # ------------------------------------------------------------------
    # profile 区（无标题段，rows 模式，每行单独样式 + 单独占位符 Run）
    # ------------------------------------------------------------------
    def _render_profile(self, section: SectionSpec, doc: ResumeDocument) -> None:
        rows = section.rows or []
        ctx = {"profile": doc.profile}
        # rows 顺序和模板 docx 中 Profile_* 段的出现顺序天然一致
        for row_spec in rows:
            # 按 style 找到第一个匹配段（就是模板里 Profile_Name / Profile_Line ...的原型段）
            found = docx_writer.find_paragraphs_by_style(self.doc, row_spec.style)
            if not found:
                raise TemplateError(f"profile 缺少 {row_spec.style} 样式的段落")
            proto = found[0]
            # 替换：profile 区只有一份，直接在原型段上替换，不需要克隆
            was_empty = docx_writer.fill_placeholders(proto, ctx)
            if was_empty:
                # 可选字段（如 location 导致整段空）→ 删段
                docx_writer.remove_paragraph(proto)

    def _render_summary(self, section: SectionSpec, resume_doc: ResumeDocument) -> None:
        """自我评价（Summary）章节：从 profile.summary 按换行拆成多行，每行一条 Summary_Bullet。

        对应 input/模板.docx 里「自我评价」章节：
            陌生领域速学：零基础情况下，2周内自学LangChain框架并搭建RAG原型demo；
            跨职能粘合剂：在团队中常担任PM与开发的「翻译官」...
        每行含「：」→ 关键词与正文同为常规字体（V1.2 PDF 复刻版起不做加粗后处理）。
        """
        text = (resume_doc.profile.summary or "").strip()
        if not text:
            if section.required:
                raise TemplateError(f"必填章节[{section.id}]自我评价无内容（profile.summary 为空）")
            # 非必填：删标题段 + 原型块
            title_paras = docx_writer.find_paragraphs_by_style(self.doc, section.title_style or "")
            if title_paras:
                self._remove_section(title_paras[0], preserve_title=False)
            self.warnings.append(f"章节[{section.id}]自我评价为空（非必填，已移除）")
            return
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        # 构造 dummy items：每个 item = {"bullet": 一行文本}
        dummy_items: list[dict] = [{"bullet": ln} for ln in lines]
        # 复用 _render_item_section：ctx_prefix="summary" → 占位符 {{summary.bullet}} 正确解析
        self._render_item_section(
            section, dummy_items,
            ctx_prefix="summary", resume_doc=resume_doc,
        )

    # ------------------------------------------------------------------
    # 通用 item 列表章节（education / work / project）—— §7.3 算法实现
    # ------------------------------------------------------------------
    def _render_item_section(
        self,
        section: SectionSpec,
        items: list,
        *,
        ctx_prefix: str,
        resume_doc: ResumeDocument,
    ) -> None:
        # 1. 定位标题段（靠 style，不靠文本）
        title_paras = docx_writer.find_paragraphs_by_style(self.doc, section.title_style or "")
        if not title_paras:
            msg = f"章节[{section.id}]缺少 title_style={section.title_style!r} 的段落"
            if section.required:
                raise TemplateError(msg)
            self.warnings.append(msg + "（非必填，已跳过）")
            return
        P_title = title_paras[0]

        # 2. max_items 渲染兜底（裁剪前移后一般不会超，这里只是保险）
        if section.max_items and len(items) > section.max_items:
            self.warnings.append(
                f"章节[{section.id}]条目数 {len(items)} 超过模板上限 {section.max_items}，渲染截断到前 {section.max_items} 条"
            )
            items = items[: section.max_items]

        # 3. 空列表 + required=true → 报错；空列表 + required=false → 删标题段和原型块，跳过
        if not items:
            if section.required:
                raise TemplateError(f"必填章节[{section.id}]无条目")
            # 删标题段 + 下方所有原型块段落（直到下一个已知的 SectionTitle_* 段为止）
            self._remove_section(P_title, preserve_title=False)
            self.warnings.append(f"章节[{section.id}]为空（非必填，已移除标题+原型）")
            return

        # 4. 收集 item_block 原型段（按 row_spec.style 顺序定位）
        block = self._collect_item_block(P_title, section.item_block or [])
        if block is None:
            msg = f"章节[{section.id}]item_block 原型段缺失"
            if section.required:
                raise TemplateError(msg)
            self.warnings.append(msg + "（非必填，已跳过）")
            return

        # V1.3 T4/T8：item_block[0] 是"事实保护标题行"（Education_ItemTitle / Work_ItemTitle / Project_ItemTitle）。
        # 旧逻辑在 fill_placeholders 返回 any_empty 时会"整段不插入"，会把事实字段（start_time/end_time/school/company/name...）
        # 全部丢弃，导致 Renderer 看起来"越权截断事实"，验收 T4 失败。
        # 修复：对 item_block 的第 0 行（row index=0）——即使占位符全空也保留已克隆行（否则整段的事实字段
        # 语义会被隐式删除），同时追加 warning 并写入 render_stats.capacity_warnings，
        # 由下游人工检查（属于 Builder 字段填充问题，不是 Renderer 的内容截断）。
        non_repeat_row_indexes: set[int] = {
            idx for idx, (row_spec, _) in enumerate(block) if not row_spec.repeat
        }
        fact_title_row_idx = 0 if block and not block[0][0].repeat else None

        # 5. 实际插入（在 P_title 之后逐条克隆）
        ref = P_title  # 当前插入点（每次 insert_after 后 ref 前进）
        for item in items:
            item_ctx_base: dict = {ctx_prefix: item}
            # 同时把 resume_doc 顶层字段放 ctx（方便 repeat 指向顶层时也能解析——虽然 education/work/project 不常用）
            item_ctx_base.setdefault("profile", resume_doc.profile)

            for row_idx, (row_spec, proto_p) in enumerate(block):
                if row_spec.repeat:
                    # repeat 行：指向 item 下的子列表（如 work.bullets）
                    sub_values = self._resolve_list(item, row_spec.repeat, ctx_prefix)
                    for single_val in sub_values:
                        # 构造 {work.bullet: v} 这样的 ctx（去掉末尾的 s）
                        repeat_ctx_key = row_spec.repeat.replace(f"{ctx_prefix}.", f"{ctx_prefix}.")
                        # repeat="work.bullets" → 单条占位符是 work.bullet（去 s）
                        single_key = repeat_ctx_key[:-1] if repeat_ctx_key.endswith("s") else repeat_ctx_key
                        clone_p = docx_writer.clone_paragraph(proto_p)
                        single_ctx = dict(item_ctx_base)
                        self._ctx_put(single_ctx, single_key, single_val)
                        was_empty = docx_writer.fill_placeholders(clone_p, single_ctx)
                        if was_empty:
                            # 空 bullet 也跳过不插
                            continue
                        docx_writer.insert_after(ref, clone_p)
                        ref = clone_p
                else:
                    # 普通行：item 级字段替换（如 edu.school / work.company）
                    clone_p = docx_writer.clone_paragraph(proto_p)
                    was_empty = docx_writer.fill_placeholders(clone_p, item_ctx_base)
                    if was_empty and row_idx != fact_title_row_idx:
                        # V1.2 空值规则（§7.3 step 6）：任意占位符为空 → 整段删除，不占空白行
                        # —— 但 事实保护标题行（row_idx == 0）例外，绝不删除，避免事实字段丢失。
                        continue
                    if was_empty and row_idx == fact_title_row_idx:
                        # 记录为 warning + capacity_warning（提醒 Builder/上游填充问题）
                        item_label = (
                            getattr(item, "experience_id", None)
                            or getattr(item, "name", None)
                            or getattr(item, "company", None)
                            or ""
                        )
                        msg = (
                            f"章节[{section.id}]条目[{item_label}]的标题行 style={row_spec.style!r} "
                            f"占位符全为空，Renderer 不删除该行（避免事实保护字段丢失），请检查 Builder 字段填充"
                        )
                        self.warnings.append(msg)
                    docx_writer.insert_after(ref, clone_p)
                    ref = clone_p

        # 6. 删除原型块所有原型段（不留模板样板行）
        for _, proto_p in block:
            docx_writer.remove_paragraph(proto_p)

    # ------------------------------------------------------------------
    # skills / awards 列表型章节（顶层 list，不是 item 下的 bullets）
    # ------------------------------------------------------------------
    def _render_skills(self, section: SectionSpec, doc: ResumeDocument) -> None:
        items = doc.skills
        title_paras = docx_writer.find_paragraphs_by_style(self.doc, section.title_style or "")
        if not title_paras:
            if section.required:
                raise TemplateError(f"skills 缺少 title_style={section.title_style!r}")
            self.warnings.append("skills 标题段缺失（非必填，已跳过）")
            return

        P_title = title_paras[0]

        if not items:
            if section.required:
                raise TemplateError("必填章节 skills 无内容")
            self._remove_section(P_title, preserve_title=False)
            self.warnings.append("章节[skills]为空（非必填，已移除）")
            return

        block = self._collect_item_block(P_title, section.item_block or [])
        if block is None:
            if section.required:
                raise TemplateError("skills item_block 原型段缺失")
            self.warnings.append("skills item_block 原型段缺失（非必填，已跳过）")
            return

        row_spec, proto_p = block[0]  # skills 只有一行 Skill_Line 原型（repeat=skills）
        # 注：repeat="skills"，每个 SkillGroup → 一行；占位符用 skill.category / skill.items
        ref = P_title
        for skill in items:
            clone_p = docx_writer.clone_paragraph(proto_p)
            # SkillGroup.items 是 list[str] → 顿号分隔的字符串，符合简历技能展示格式
            joined_items = "、".join(skill.items) if isinstance(skill.items, list) else str(skill.items or "")
            ctx = {
                "skill": {
                    "category": skill.category,
                    "items": joined_items,
                },
                "profile": doc.profile,
            }
            was_empty = docx_writer.fill_placeholders(clone_p, ctx)
            if was_empty:
                continue
            docx_writer.insert_after(ref, clone_p)
            ref = clone_p
        for _, p in block:
            docx_writer.remove_paragraph(p)

    def _render_awards(self, section: SectionSpec, doc: ResumeDocument) -> None:
        items = doc.awards
        title_paras = docx_writer.find_paragraphs_by_style(self.doc, section.title_style or "")
        if not title_paras:
            if section.required:
                raise TemplateError(f"awards 缺少 title_style={section.title_style!r}")
            self.warnings.append("awards 标题段缺失（非必填，已跳过）")
            return

        P_title = title_paras[0]

        if not items:
            if section.required:
                raise TemplateError("必填章节 awards 无内容")
            self._remove_section(P_title, preserve_title=False)
            self.warnings.append("章节[awards]为空（非必填，已移除）")
            return

        block = self._collect_item_block(P_title, section.item_block or [])
        if block is None:
            if section.required:
                raise TemplateError("awards item_block 原型段缺失")
            self.warnings.append("awards item_block 原型段缺失（非必填，已跳过）")
            return

        row_spec, proto_p = block[0]
        ref = P_title
        for award in items:
            clone_p = docx_writer.clone_paragraph(proto_p)
            ctx = {"award": award, "profile": doc.profile}
            was_empty = docx_writer.fill_placeholders(clone_p, ctx)
            if was_empty:
                continue
            docx_writer.insert_after(ref, clone_p)
            ref = clone_p
        for _, p in block:
            docx_writer.remove_paragraph(p)

    # ==================================================================
    # 辅助：item_block 原型段定位、section 删除、ctx 点路径等
    # ==================================================================

    def _collect_item_block(
        self,
        P_title: Paragraph,
        row_specs: list[RowSpec],
    ) -> Optional[list[tuple[RowSpec, Paragraph]]]:
        """在 P_title 之后按 row_spec[].style 的顺序找到对应原型段落。

        找不到任何一个时返回 None（调用方决定报错还是跳过）。
        """
        block: list[tuple[RowSpec, Paragraph]] = []
        cursor = docx_writer.find_next_paragraph(P_title)
        section_title_style_prefixes = {
            f"SectionTitle_{s}" for s in ("Education", "Work", "Project", "Skills", "Awards")
        }
        for row_spec in row_specs:
            while cursor is not None and cursor.style.name != row_spec.style:
                # 遇到下一个章节的标题段 → 说明模板缺原型
                if cursor.style.name in section_title_style_prefixes:
                    self.warnings.append(
                        f"定位 item_block[{row_spec.style}]时遇到下一章节标题 {cursor.style.name!r}，模板原型缺失"
                    )
                    return None
                cursor = docx_writer.find_next_paragraph(cursor)
            if cursor is None:
                self.warnings.append(f"item_block 缺少 style={row_spec.style!r} 的原型段")
                return None
            block.append((row_spec, cursor))
            cursor = docx_writer.find_next_paragraph(cursor)
        return block

    def _remove_section(self, P_title: Paragraph, *, preserve_title: bool) -> None:
        """删除 P_title 之后直到下一章节标题的所有段落（用于空章节移除）。"""
        section_title_style_prefixes = {
            "SectionTitle_Education", "SectionTitle_Work", "SectionTitle_Project",
            "SectionTitle_Skills", "SectionTitle_Awards",
        }
        cur = docx_writer.find_next_paragraph(P_title)
        while cur is not None and cur.style.name not in section_title_style_prefixes:
            nxt = docx_writer.find_next_paragraph(cur)
            docx_writer.remove_paragraph(cur)
            cur = nxt
        if not preserve_title:
            docx_writer.remove_paragraph(P_title)

    @staticmethod
    def _resolve_list(item, dotpath: str, ctx_prefix: str) -> list:
        """解析 repeat 指定的列表字段（如 work.bullets）。"""
        parts = dotpath.split(".")
        if parts[0] != ctx_prefix:
            # repeat 指向 resume_doc 顶层列表（如 skills / awards）
            return []
        cur = item
        for p in parts[1:]:
            if isinstance(cur, dict):
                cur = cur.get(p) if p in cur else []
            else:
                cur = getattr(cur, p, None)
            if cur is None:
                return []
        return list(cur or [])

    @staticmethod
    def _ctx_put(ctx: dict, dotpath: str, value) -> None:
        """把单值放进 ctx 对应点路径（如 work.bullet → {work: {bullet: v}}）。"""
        parts = dotpath.split(".")
        cur = ctx
        for p in parts[:-1]:
            if p not in cur or not isinstance(cur[p], dict):
                cur[p] = {}
            cur = cur[p]
        cur[parts[-1]] = value
