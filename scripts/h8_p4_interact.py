#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P4 / success 简历预览三类目标的真实交互取证（PLAN §R3-24 §24.4-4）。

为什么是共享模块：
  §24.4-4 同时要求 Design Fidelity 与主链/最终包浏览器验证「进入 P4 并验证可交互结果」，
  且明确 anchor 数量 / artifact_id 绑定 / PDF ready 不能替代交互结果。两处若各写一份断言，
  语义会分叉、且总有一份未经离线验证。故本模块是唯一实现，由
  `h8_design_fidelity.py`（设计保真）与 `h8_real_model_e2e.py`（主链/最终包）共同调用。

被验证的行为（fact / section / skills 三类目标 × mouse / Enter / Space）：
  * 激活后 `aria-pressed=true`、class 含 `selected`、右侧 `.wb-panel--aside` 详情**实际变化且
    与所选对象一致**（Fact 详情有真实理由/原文，段落详情有真实标题与成员事实/技能行）；
  * 同一方式再次激活 = 取消选择，右侧回到未选择摘要；
  * 两类目标互斥（任意时刻最多 1 个选中）；
  * 滚动后热区仍精确命中（热区与正文对齐，非固定样张坐标）；
  * 命中层身份与权威 `artifacts.pdf_anchors` **双向一一对应**：权威声明的每类锚点必须渲染出可点
    目标并完成上述全链路；权威未声明的类别必须 0 个热点（诚实退出，不产生可点但无响应的幽灵热区）。
    因此某类（如 skills）在该次任务数据下不存在时，按权威锚点判为「诚实退出」而非设计保真失败；
    「权威已声明却渲染不出」「权威未声明却出现可点目标」才是 FAIL。

接入方约定：`bx(args, timeout=30) -> str` 为 agent-browser 调用（两脚本签名一致）。
"""
from __future__ import annotations

import json
import time

# ── 页面探针 ──────────────────────────────────────────────────────
LAYOUT_JS = (
    "JSON.stringify([].map.call(document.querySelectorAll('.pdf-page'),function(pg){"
    "var pr=pg.getBoundingClientRect();var cv=pg.querySelector('canvas');"
    "var cr=cv?cv.getBoundingClientRect():null;"
    "var hits=[].map.call(pg.querySelectorAll('.pdf-hit'),function(b){"
    "var r=b.getBoundingClientRect();"
    "return {kind:b.getAttribute('data-anchor-kind'),"
    "id:b.getAttribute('data-fact')||b.getAttribute('data-section')||'',"
    "cls:String(b.className),pressed:b.getAttribute('aria-pressed'),"
    "label:b.getAttribute('aria-label')||'',"
    "l:r.left,t:r.top,w:r.width,h:r.height};});"
    "return {page:{l:pr.left,t:pr.top,w:pr.width,h:pr.height},"
    "canvas:cr?{l:cr.left,t:cr.top,w:cr.width,h:cr.height}:null,hits:hits};}))")

ASIDE_JS = (
    "JSON.stringify({"
    "title:(document.querySelector('.wb-panel--aside .wb-panel__head-title')||{}).textContent||'',"
    "badge:(document.querySelector('.wb-panel--aside .wb-panel__head-sub')||{}).textContent||'',"
    "reason:(document.querySelector('.wb-panel--aside .reason-box span')||{}).textContent||'',"
    "source:(document.querySelector('.wb-panel--aside .source-box blockquote')||{}).textContent||'',"
    "factH:(document.querySelector('.wb-panel--aside .detail-stream h3')||{}).textContent||'',"
    "factHost:(document.querySelector('.wb-panel--aside .detail-stream p')||{}).textContent||'',"
    "secH:(document.querySelector('.wb-panel--aside .section-detail h3')||{}).textContent||'',"
    "secHelp:(document.querySelector('.wb-panel--aside .section-detail .field-help')||{}).textContent||'',"
    "skillRows:document.querySelectorAll('.wb-panel--aside .section-detail-row').length,"
    "secFacts:document.querySelectorAll('.wb-panel--aside .section-fact').length,"
    "empty:document.querySelectorAll('.wb-panel--aside .section-detail__empty').length})")

# 权威 task 快照探针：P4 三类目标是否**应**可点，由后端 artifacts.pdf_anchors 决定（唯一真源）。
# 页面内同步读同源 `GET /api/task/{lastTaskId}`，只把锚点身份计数/明细带回（不传整段 JSON）。
# 仅统计**已渲染页**（page_index < `.pdf-page` 数量）的锚点，兼容 viewer 懒渲染：未渲染页的锚点
# 本就不在命中层，不应被误判为「权威已声明却渲染不出」。
AUTHORITY_JS = (
    "(function(){var o={ok:false,tid:'',why:'',total:0,rendered_pages:0,"
    "kinds:{fact:0,section:0,skills:0},keys:{fact:[],section:[],skills:[]},"
    "preview:{sections:0,skills:0}};"
    "try{"
    "var tid=sessionStorage.getItem('resume_assistant.lastTaskId')||'';o.tid=tid;"
    "o.rendered_pages=document.querySelectorAll('.pdf-page').length;"
    "if(!tid){o.why='no lastTaskId';return JSON.stringify(o);}"
    "var x=new XMLHttpRequest();x.open('GET','/api/task/'+tid,false);x.send();"
    "o.ok=(x.status===200);"
    "if(!o.ok){o.why='http '+x.status;return JSON.stringify(o);}"
    "var j=JSON.parse(x.responseText);"
    "var p=(j.snapshot&&j.snapshot.payload)||{};var arts=p.artifacts||{};"
    "var a=arts.pdf_anchors||[];o.total=a.length;var rp=o.rendered_pages;"
    "for(var i=0;i<a.length;i++){var k=a[i].kind||'fact';"
    "if(rp>0&&(a[i].page_index||0)>=rp)continue;"
    "if(k==='fact'){if(a[i].fact_id){o.kinds.fact++;o.keys.fact.push(String(a[i].fact_id));}}"
    "else if(k==='section'){if(a[i].content_item_id){o.kinds.section++;"
    "o.keys.section.push(String(a[i].content_item_id));}}"
    "else if(k==='skills'){if(a[i].content_item_id){o.kinds.skills++;o.keys.skills.push('skills');}}}"
    "var ps=arts.preview_sections;o.preview.sections=(ps&&typeof ps.length==='number')?ps.length:0;"
    "var pk=arts.preview_skills;o.preview.skills=(pk&&typeof pk.length==='number')?pk.length:0;"
    "}catch(e){o.why=String(e);}"
    "return JSON.stringify(o);})()")

# StepSuccessAside 诚实留白文案：命中这些值 = 没有真实数据可展示（不得据此判 PASS）。
REASON_FALLBACK = "本次未记录该条事实的选择理由。"
SOURCE_FALLBACK = "该条事实未记录可展示的原文依据。"
# 未选择时的右侧摘要标题（StepSuccessAside）。
IDLE_TITLE = "已为这个岗位整理好"


def ev(bx, js_expr: str):
    """执行返回 `JSON.stringify(...)` 的 JS 并解析（标量/字符串安全，跳过 CLI 的 ✓/✗ 行）。"""
    raw = bx(["eval", js_expr], timeout=30)
    if not raw:
        return None
    lines = [l.strip() for l in raw.splitlines()
             if l.strip() and not l.strip().startswith(("✓", "✗"))]
    cand = lines[-1] if lines else ""
    if not cand:
        return None
    try:
        v = json.loads(cand)
    except Exception:
        return {"_raw": cand[:200]}
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return v
    return v


def layout(bx) -> list:
    v = ev(bx, LAYOUT_JS)
    return v if isinstance(v, list) else []


def aside(bx) -> dict:
    v = ev(bx, ASIDE_JS)
    return v if isinstance(v, dict) else {}


def authority(bx) -> dict:
    """读当前 Task 的权威锚点集（`artifacts.pdf_anchors`）—— 「该类**应**可点」的唯一真源。"""
    v = ev(bx, AUTHORITY_JS)
    return v if isinstance(v, dict) else {"ok": False, "why": "probe failed"}


def hit_identity(h: dict) -> str | None:
    """命中层热点的身份键，语义与前端 `pdfAnchorKey` 一致（缺身份 → None，前端同样不渲染）。"""
    kind = h.get("kind")
    ident = h.get("id") or ""
    if kind == "fact":
        return f"fact:{ident}" if ident else None
    if kind == "section":
        return f"section:{ident}" if ident else None
    if kind == "skills":
        return "skills"
    return None


def authority_keys(auth: dict) -> set:
    """权威锚点身份集合（与 `hit_identity` 同构，供双向比对）。"""
    keys = auth.get("keys") or {}
    out = set()
    for f in keys.get("fact") or []:
        if f:
            out.add(f"fact:{f}")
    for s in keys.get("section") or []:
        if s:
            out.add(f"section:{s}")
    if int((auth.get("kinds") or {}).get("skills") or 0) > 0:
        out.add("skills")
    return out


def hit_of(lay: list, kind: str, ident: str = "") -> dict | None:
    for pg in lay or []:
        for h in pg.get("hits") or []:
            if h.get("kind") == kind and (not ident or h.get("id") == ident):
                return h
    return None


def sel_for(kind: str, ident: str) -> str:
    """agent-browser 的 click/focus 会剥掉属性选择器里的双引号 → 统一用单引号。"""
    if kind == "fact":
        return f"[data-fact='{ident}']"
    if kind == "skills":
        return "[data-section='skills']"
    return f"[data-section='{ident}']"


def hit_probe(bx, sel: str) -> dict:
    """热点「可视点击点」：须在热点矩形内、预览滚动可视区内、且该点最上层元素正是该热点。

    候选点一律先 `Math.trunc` 成整数再探测，并直接以该整数点为 `pt` —— 必须与
    `click_hit` 真正发送的整数像素一致。若用浮点矩心探测、点击侧再 `int()` 截断，
    两者可能相差 1px；section 整段热点被 fact 行覆盖后可能只剩几像素可点带，
    1px 偏移就会点到上层 fact 上（§R3-24 实测根因）。
    探测与点击之间还隔着 agent-browser 往返，版面可能抖动 1–2px，故优先选「与其它热点
    边界保持 ≥4px 净空」的点，取不到才退回第一个合法点（保证单像素级错位也不会点错对象）。
    """
    js = ("(function(){var el=document.querySelector(" + json.dumps(sel) + ");"
          "if(!el)return JSON.stringify({found:false});"
          "el.scrollIntoView({block:'center'});"
          "var r=el.getBoundingClientRect();"
          "var sc=document.querySelector('.pdf-preview__pages');"
          "var sr=sc?sc.getBoundingClientRect():null;"
          "var x0=Math.max(r.left,sr?sr.left:0,0),y0=Math.max(r.top,sr?sr.top:0,0);"
          "var x1=Math.min(r.right,sr?sr.right:window.innerWidth,window.innerWidth),"
          "y1=Math.min(r.bottom,sr?sr.bottom:window.innerHeight,window.innerHeight);"
          "var c=[[(x0+x1)/2,(y0+y1)/2],[x0+3,(y0+y1)/2],[x1-3,(y0+y1)/2],"
          "[(x0+x1)/2,y0+3],[(x0+x1)/2,y1-3]];"
          "var others=[].filter.call(document.querySelectorAll('.pdf-hit'),function(o){return o!==el;});"
          "function clr(x,y){var m=1e9;for(var j=0;j<others.length;j++){"
          "var b=others[j].getBoundingClientRect();"
          "if(x>=b.left&&x<=b.right&&y>=b.top&&y<=b.bottom)return -1;"
          "var dx=Math.max(b.left-x,0,x-b.right),dy=Math.max(b.top-y,0,y-b.bottom);"
          "var d=dx>dy?dx:dy;if(d<m)m=d;}return m;}"
          "var pt=null,fb=null;"
          "for(var i=0;i<c.length;i++){"
          "var cx=Math.trunc(c[i][0]),cy=Math.trunc(c[i][1]);"
          "var e=document.elementFromPoint(cx,cy);"
          "if(e&&e===el){if(fb===null)fb=[cx,cy];if(clr(cx,cy)>=4&&pt===null)pt=[cx,cy];}}"
          "if(pt===null)pt=fb;"
          "return JSON.stringify({found:true,pt:pt,"
          "rect:[Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)],"
          "scroll:sr?[Math.round(sr.left),Math.round(sr.top),Math.round(sr.width),Math.round(sr.height)]:null});})()")
    v = ev(bx, js)
    return v if isinstance(v, dict) else {"found": False}


def click_hit(bx, sel: str) -> dict:
    """对 PDF 热点执行**真实鼠标**点击（视口坐标 mouse move/down/up）。

    本产品透明 PDF 命中层上 agent-browser 的 `click <selector>` 会静默空转（无输出、无状态变化），
    因此必须用原子鼠标事件；点击点由 `hit_probe` 证明「最上层元素就是该热点」。
    """
    pr = hit_probe(bx, sel)
    pt = pr.get("pt")
    if not pt:
        return {"ok": False, "probe": pr}
    bx(["mouse", "move", str(int(pt[0])), str(int(pt[1]))], timeout=20)
    down = bx(["mouse", "down"], timeout=20)
    up = bx(["mouse", "up"], timeout=20)
    return {"ok": True, "pt": (pt[0], pt[1]), "probe": pr, "out": f"{down}|{up}"}


def focus_press(bx, sel: str, key: str) -> dict:
    """键盘激活：真实 focus 到热点（真实 <button>）后发射 Enter/Space。"""
    bx(["focus", sel], timeout=25)
    time.sleep(0.25)
    out = bx(["press", key], timeout=25)
    return {"ok": True, "out": out}


def detail_ok(kind: str, st: dict) -> tuple[bool, str]:
    """右侧 .wb-panel--aside 是否展示了**与所选对象一致的真实详情**（非留白/非伪造）。"""
    if kind == "fact":
        reason = st.get("reason") or ""
        source = st.get("source") or ""
        real = (reason not in ("", REASON_FALLBACK)) or (source not in ("", SOURCE_FALLBACK))
        good = st.get("title") == "Fact 详情" and bool(st.get("factH")) and real
        return good, (f"title={st.get('title')!r} factH={st.get('factH')!r} "
                      f"reasonLen={len(reason)} sourceLen={len(source)} real={real}")
    if kind == "section":
        good = (st.get("title") == "段落详情" and bool(st.get("secH"))
                and int(st.get("secFacts") or 0) >= 1)
        return good, (f"title={st.get('title')!r} secH={st.get('secH')!r} "
                      f"secFacts={st.get('secFacts')} empty={st.get('empty')}")
    good = (st.get("title") == "段落详情" and bool(st.get("secH"))
            and int(st.get("skillRows") or 0) >= 1)
    return good, (f"title={st.get('title')!r} secH={st.get('secH')!r} "
                  f"skillRows={st.get('skillRows')} empty={st.get('empty')}")


def run(bx, *, ok, bad, log, evidence: dict, tag: str = "P4.interact",
        kinds: tuple[str, ...] = ("fact", "section", "skills")) -> None:
    """执行 P4 三类目标的真实交互断言，并写入 `evidence["_p4_hits"]` / `["_p4_authority"]` /
    `["_p4_interactions_done"]`。

    每类是否**应**可点由当前 Task 的权威 `artifacts.pdf_anchors` 决定（见模块说明），
    不使用任何固定坐标或第二份 HTML 真源。
    `ok(label, extra)` / `bad(label, why)` 为接入方的判定回调；`tag` 为断言名前缀，
    使 Design Fidelity（P4.interact.*）与主链（ui.P4.interact.*）在证据中可区分。
    """
    log("\n=== P4 真实交互：fact / section / skills × mouse / Enter / Space ===")
    lay = layout(bx)
    hits = [h for pg in lay for h in (pg.get("hits") or [])]
    fact = next((h for h in hits if h.get("kind") == "fact" and h.get("id")), None)
    sect = next((h for h in hits if h.get("kind") == "section" and h.get("id")), None)
    skills = next((h for h in hits if h.get("kind") == "skills"), None)
    evidence["_p4_hits"] = {
        "total": len(hits), "fact": fact and fact.get("id"),
        "section": sect and sect.get("id"), "skills": bool(skills),
        "aside_unselected": aside(bx).get("title")}
    auth = authority(bx)
    evidence["_p4_authority"] = auth

    # ① 「该类是否应可点」的判据必须来自**权威锚点集**（§R3-24 §24.4-1：anchor 缺失 / 不可定位 →
    #    诚实退出对应交互）。因此「无 skill 组可点」本身不是设计保真失败（技能区本就只在有 Fact
    #    依据时出现）；反之「权威已声明却渲染不出」或「权威未声明却出现可点目标」都必须 FAIL。
    #    双向比对命中层身份 ↔ artifacts.pdf_anchors，只覆盖**已渲染页**。
    if not auth.get("ok"):
        bad(f"{tag}.authority", f"无法读取权威 task 快照（{auth.get('why')}）→ 锚点身份不可判定")
    auth_keys = authority_keys(auth) if auth.get("ok") else set()
    dom_keys = {k for k in (hit_identity(h) for h in hits) if k}
    if auth.get("ok"):
        missing = sorted(auth_keys - dom_keys)
        ghost = sorted(dom_keys - auth_keys)
        if not missing and not ghost:
            ok(f"{tag}.anchor-identity",
               f"权威锚点 {len(auth_keys)} 项 ↔ 命中层 {len(dom_keys)} 项一一对应（无缺失、无幽灵）")
        else:
            bad(f"{tag}.anchor-identity", f"权威声明却无热区={missing} 幽灵热区={ghost}")
    if not hits:
        bad(f"{tag}.at-least-one-class", "命中层无任何可点目标，无从验证真实交互")

    for kind, h in (("fact", fact), ("section", sect), ("skills", skills)):
        if kind not in kinds:
            continue
        declared = int((auth.get("kinds") or {}).get(kind) or 0)
        if not h:
            if declared:
                bad(f"{tag}.{kind}.present",
                    f"权威快照声明 {declared} 个 {kind} 锚点，命中层却无可点目标（渲染与锚点不一致）")
            else:
                ok(f"{tag}.{kind}.absent",
                   f"权威快照未声明 {kind} 锚点 → 诚实退出（命中层 0 个，无幽灵热区）")
            continue
        if auth.get("ok") and not declared:
            bad(f"{tag}.{kind}.ghost", f"权威快照未声明 {kind} 锚点，命中层却出现可点目标（幽灵热区）")
            continue
        ident = h.get("id") or ""
        ok(f"{tag}.{kind}.present",
           f"id={ident} rect=({round(h.get('w') or 0)}x{round(h.get('h') or 0)})")
        sel = sel_for(kind, ident)
        for how in ("mouse", "Enter", "Space"):
            base_st = aside(bx)
            act = click_hit(bx, sel) if how == "mouse" else focus_press(bx, sel, how)
            time.sleep(0.7)
            now = hit_of(layout(bx), kind, ident)
            st = aside(bx)
            pressed = bool(now and str(now.get("pressed")).lower() == "true")
            selected = bool(now and "selected" in (now.get("cls") or ""))
            good, why = detail_ok(kind, st)
            if act.get("ok") and pressed and selected and good and st != base_st:
                ok(f"{tag}.{kind}.{how}",
                   f"pt={act.get('pt')} aria-pressed=true .selected 详情实际变化（{why}）")
            else:
                bad(f"{tag}.{kind}.{how}",
                    f"act={act.get('ok')} pressed={pressed} selected={selected} "
                    f"changed={st != base_st} {why}")
            # 同一激活方式再次触发 = 取消选择（重复点击/按键取消，DS-003）
            if how == "mouse":
                click_hit(bx, sel)
            else:
                focus_press(bx, sel, how)
            time.sleep(0.7)
            now2 = hit_of(layout(bx), kind, ident)
            st2 = aside(bx)
            off = bool(now2 and str(now2.get("pressed")).lower() != "true"
                       and "selected" not in (now2.get("cls") or ""))
            if off and st2.get("title") == IDLE_TITLE:
                ok(f"{tag}.{kind}.{how}.toggle-off", f"再次{how}取消选择，右侧回到未选择摘要")
            else:
                bad(f"{tag}.{kind}.{how}.toggle-off",
                    f"pressed={now2 and now2.get('pressed')} cls={now2 and now2.get('cls')} "
                    f"asideTitle={st2.get('title')!r}")

    # 互斥：先选 fact 再选 section，任意时刻最多 1 个选中且右侧跟随最后选择
    if fact and sect and "fact" in kinds and "section" in kinds:
        click_hit(bx, sel_for("fact", fact.get("id") or ""))
        time.sleep(0.6)
        click_hit(bx, sel_for("section", sect.get("id") or ""))
        time.sleep(0.7)
        lay3 = layout(bx)
        n_sel = sum(1 for pg in lay3 for hh in (pg.get("hits") or [])
                    if str(hh.get("pressed")).lower() == "true")
        st3 = aside(bx)
        if n_sel == 1 and st3.get("title") == "段落详情":
            ok(f"{tag}.exclusive", "fact→section 后仅 1 个选中，右侧=段落详情")
        else:
            bad(f"{tag}.exclusive", f"pressed_n={n_sel} aside={st3}")
        click_hit(bx, sel_for("section", sect.get("id") or ""))
        time.sleep(0.5)

    # 滚动后热区仍与正文对齐（命中点最上层元素就是该热点）
    if fact:
        bx(["eval", "(function(){var s=document.querySelector('.pdf-preview__pages');"
                    "if(s)s.scrollTop=Math.min(120,s.scrollHeight);return 'ok';})()"], timeout=20)
        time.sleep(0.6)
        pr = hit_probe(bx, sel_for("fact", fact.get("id") or ""))
        if pr.get("found") and pr.get("pt"):
            ok(f"{tag}.align-after-scroll",
               f"滚动后热区仍精确命中 pt={tuple(round(v, 1) for v in pr['pt'])} rect={pr.get('rect')}")
        else:
            bad(f"{tag}.align-after-scroll", f"滚动后热点不可命中 probe={pr}")
        bx(["eval", "(function(){var s=document.querySelector('.pdf-preview__pages');"
                    "if(s)s.scrollTop=0;return 'ok';})()"], timeout=20)
        time.sleep(0.4)
    evidence["_p4_interactions_done"] = True