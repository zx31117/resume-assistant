import { useCallback, useState } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PdfPreview, { anchorSelectionKey } from '../src/components/PdfPreview'
import type { PdfAnchor } from '../src/api/types'

/**
 * V2.2.0 DOC_RETURNED 返工：P4 选择交互的**组件级正反向测试**（PLAN §R3-24 §24.4-4）。
 *
 * 覆盖：空 anchor / anchors 缺失 / artifact 身份错配 / artifactId 缺失 / 未提供受控回调 /
 * 缺身份键（不可选）/ 坐标越界 —— 一律诚实关闭（0 热点，PDF 仍 ready，无 console 错误）；
 * 以及单 fact / section / skills 三类目标的可选中、受控高亮、再次点击取消、事件单飞。
 *
 * 真实浏览器的 mouse / Enter / Space 激活与热区—正文几何对齐由 h8_r3_docreturned_ui（U2/U3/U6）
 * 与 h8_design_fidelity（P4 真实交互）在真实 PDF 上验证；此处断言的是组件契约本身。
 */

const ART = 'artifact_pdf_1'
const PDF_URL = `/api/task/t1/artifact/pdf`

function mkAnchor(over: Partial<PdfAnchor>): PdfAnchor {
  return {
    artifact_id: ART,
    page_index: 0,
    x0: 100,
    y0: 600,
    x1: 400,
    y1: 620,
    content_item_id: 'exp_1',
    bullet_index: 0,
    text: '负责交易链路设计与高并发优化',
    fact_refs: ['ref_1'],
    kind: 'fact',
    fact_id: 'F1',
    ...over,
  }
}

const FACT = mkAnchor({ kind: 'fact', fact_id: 'F1', y0: 700, y1: 720 })
const SECTION = mkAnchor({ kind: 'section', fact_id: null, content_item_id: 'exp_1', y0: 600, y1: 660, bullet_index: null })
const SKILLS = mkAnchor({ kind: 'skills', fact_id: null, content_item_id: 'skills', y0: 400, y1: 430, bullet_index: null })

function stubFetchOk() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d]), { status: 200 })),
  )
}

function consoleErrors(): string[] {
  const spy = vi.mocked(console.error)
  return spy.mock.calls.map((c) => c.map(String).join(' ')).filter((m) => !m.includes('not wrapped in act'))
}

async function waitReady(container: HTMLElement) {
  await waitFor(() => expect(container.querySelector('.pdf-preview')).toHaveAttribute('data-state', 'ready'))
}

/** 受控宿主：模拟 StepDownload/WorkbenchPage 的真实契约（父组件持有选中态并下发）。 */
function Controlled({
  anchors,
  artifactId = ART,
  withCallback = true,
  onCall,
}: {
  anchors?: PdfAnchor[] | null
  artifactId?: string | null
  withCallback?: boolean
  onCall?: (a: PdfAnchor | null) => void
}) {
  const [sel, setSel] = useState<PdfAnchor | null>(null)
  const handle = useCallback(
    (a: PdfAnchor | null) => {
      onCall?.(a)
      setSel(a)
    },
    [onCall],
  )
  return (
    <PdfPreview
      url={PDF_URL}
      artifactId={artifactId}
      anchors={anchors}
      selectedAnchor={sel}
      onSelectAnchor={withCallback ? handle : undefined}
    />
  )
}

function hits(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>('.pdf-hit'))
}

beforeEach(() => {
  stubFetchOk()
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('PdfPreview 反向：诚实关闭（禁止幽灵热区）', () => {
  const cases: Array<[string, Parameters<typeof Controlled>[0]]> = [
    ['anchors 为空数组', { anchors: [] }],
    ['anchors 为 null', { anchors: null }],
    ['artifact 身份错配', { anchors: [mkAnchor({ artifact_id: 'artifact_OTHER' })] }],
    ['artifactId 缺失（旧后端）', { anchors: [mkAnchor({})], artifactId: null }],
    ['未提供受控回调', { anchors: [mkAnchor({})], withCallback: false }],
    ['fact 锚点缺 fact_id', { anchors: [mkAnchor({ fact_id: null })] }],
    ['section 锚点缺 content_item_id', { anchors: [mkAnchor({ kind: 'section', fact_id: null, content_item_id: null })] }],
    ['skills 锚点缺 content_item_id', { anchors: [mkAnchor({ kind: 'skills', fact_id: null, content_item_id: null })] }],
    ['坐标越界（超出页面 MediaBox）', { anchors: [mkAnchor({ x1: 5000 })] }],
  ]

  for (const [name, props] of cases) {
    it(`${name} → 0 热点，PDF 仍 ready，无 console 错误`, async () => {
      const { container } = render(<Controlled {...props} />)
      await waitReady(container)
      await waitFor(() => expect(container.querySelector('.pdf-page')).not.toBeNull())
      expect(hits(container)).toHaveLength(0)
      expect(container.querySelectorAll('[data-fact],[data-section]')).toHaveLength(0)
      expect(consoleErrors()).toEqual([])
    })
  }
})

describe('PdfPreview 正向：三类目标受控选择', () => {
  it('单 fact：命中身份/类别正确，点击选中 → 再次点击取消，事件单飞', async () => {
    const calls: Array<PdfAnchor | null> = []
    const { container } = render(<Controlled anchors={[FACT]} onCall={(a) => calls.push(a)} />)
    await waitReady(container)
    await waitFor(() => expect(hits(container)).toHaveLength(1))

    const btn = container.querySelector<HTMLButtonElement>("[data-fact='F1']")!
    expect(btn).not.toBeNull()
    expect(btn.getAttribute('data-anchor-kind')).toBe('fact')
    expect(btn.getAttribute('aria-pressed')).toBe('false')
    expect(btn.getAttribute('aria-label')).toContain('查看事实')
    expect(anchorSelectionKey(FACT)).toBe('fact:F1')

    const user = userEvent.setup()
    await user.click(btn)
    await waitFor(() => expect(btn.getAttribute('aria-pressed')).toBe('true'))
    expect(btn.className).toContain('selected')
    expect(calls).toHaveLength(1)
    expect(calls[0]).toBe(FACT)

    // 重复点击同一热点 = 取消选择（受控回写 null），且不发生额外选择
    await user.click(btn)
    await waitFor(() => expect(btn.getAttribute('aria-pressed')).toBe('false'))
    expect(btn.className).not.toContain('selected')
    expect(calls).toHaveLength(2)
    expect(calls[1]).toBeNull()
    expect(consoleErrors()).toEqual([])
  })

  it('section：整段经历锚点可选中，受控高亮跟随', async () => {
    const calls: Array<PdfAnchor | null> = []
    const { container } = render(<Controlled anchors={[SECTION]} onCall={(a) => calls.push(a)} />)
    await waitReady(container)
    await waitFor(() => expect(hits(container)).toHaveLength(1))
    const btn = container.querySelector<HTMLButtonElement>("[data-section='exp_1']")!
    expect(btn.getAttribute('data-anchor-kind')).toBe('section')
    expect(anchorSelectionKey(SECTION)).toBe('section:exp_1')
    await userEvent.setup().click(btn)
    await waitFor(() => expect(btn.getAttribute('aria-pressed')).toBe('true'))
    expect(calls).toHaveLength(1)
    expect(calls[0]).toBe(SECTION)
  })

  it('skills：技能专长整段可选中，身份键为 skills', async () => {
    const calls: Array<PdfAnchor | null> = []
    const { container } = render(<Controlled anchors={[SKILLS]} onCall={(a) => calls.push(a)} />)
    await waitReady(container)
    await waitFor(() => expect(hits(container)).toHaveLength(1))
    const btn = container.querySelector<HTMLButtonElement>("[data-section='skills']")!
    expect(btn.getAttribute('data-anchor-kind')).toBe('skills')
    expect(anchorSelectionKey(SKILLS)).toBe('skills')
    await userEvent.setup().click(btn)
    await waitFor(() => expect(btn.getAttribute('aria-pressed')).toBe('true'))
    expect(calls[0]).toBe(SKILLS)
  })

  it('三类共存：fact 在 DOM 顺序上位于 section/skills 之后（行内点击命中 fact，其余命中整段）', async () => {
    const { container } = render(<Controlled anchors={[SECTION, SKILLS, FACT]} />)
    await waitReady(container)
    await waitFor(() => expect(hits(container)).toHaveLength(3))
    const kinds = hits(container).map((b) => b.getAttribute('data-anchor-kind'))
    expect(kinds[kinds.length - 1]).toBe('fact')
    expect(kinds.slice(0, -1).sort()).toEqual(['section', 'skills'])
  })

  it('热点是真实 <button type=button> 且可聚焦（Enter/Space 原生激活与 focus-visible 的前提）', async () => {
    const { container } = render(<Controlled anchors={[FACT, SECTION, SKILLS]} />)
    await waitReady(container)
    await waitFor(() => expect(hits(container)).toHaveLength(3))
    for (const b of hits(container)) {
      expect(b.tagName).toBe('BUTTON')
      expect(b.getAttribute('type')).toBe('button')
      b.focus()
      expect(document.activeElement).toBe(b)
    }
    expect(consoleErrors()).toEqual([])
  })

  it('互斥：选中 section 后点击 fact，仅 fact 为 aria-pressed=true', async () => {
    const { container } = render(<Controlled anchors={[SECTION, FACT]} />)
    await waitReady(container)
    await waitFor(() => expect(hits(container)).toHaveLength(2))
    const sec = container.querySelector<HTMLButtonElement>("[data-section='exp_1']")!
    const fact = container.querySelector<HTMLButtonElement>("[data-fact='F1']")!
    const user = userEvent.setup()
    await user.click(sec)
    await waitFor(() => expect(sec.getAttribute('aria-pressed')).toBe('true'))
    await user.click(fact)
    await waitFor(() => expect(fact.getAttribute('aria-pressed')).toBe('true'))
    expect(sec.getAttribute('aria-pressed')).toBe('false')
    expect(sec.className).not.toContain('selected')
  })

  it('artifactId 匹配且身份键齐全 → 正常渲染（与错配用例形成正反对照）', async () => {
    const { container } = render(<Controlled anchors={[mkAnchor({ artifact_id: ART })]} />)
    await waitReady(container)
    await waitFor(() => expect(hits(container)).toHaveLength(1))
    expect(screen.queryByRole('alert')).toBeNull()
  })
})