import { useEffect, useRef, useState } from 'react'
import type { DocPreviewSection } from '../api/types'

/**
 * V2.1.0 T12-R5：结果页左侧真实简历纸张预览（fitPaper）。
 * - 自然尺寸固定 A4-ish（720×1018），通过 transform: scale 等比适配 .preview-scroll 可用空间；
 * - 默认尽量不滚轮；MIN_SCALE 兜底避免缩到不可读，溢出部分由 .preview-scroll 受控滚动承接（仅左侧预览区）；
 * - 完全基于真实 result.doc_preview 渲染；bullet 可点击 → 上抛 onSelect 给 evidence 面板联动。
 */

const NATURAL_W = 720 // A4 @ 96dpi (210mm) 减 74px 边距的近似内文宽度
const NATURAL_H = 1018 // 720 × 297/210 ≈ 1018（自然纸张高度）
const MIN_SCALE = 0.55 // 文字不可读兜底：再小就让 .preview-scroll 滚动
const MAX_SCALE = 1.2 // 不再放大，避免纸张过大

export interface SelectedBullet {
  sectionIdx: number
  entryIdx: number
  bulletIdx: number
}

interface Props {
  sections: DocPreviewSection[] | null
  selected: SelectedBullet | null
  onSelect: (s: SelectedBullet) => void
}

export default function ResultPaperPreview({ sections, selected, onSelect }: Props) {
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const [scale, setScale] = useState(1)

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const compute = () => {
      const cw = el.clientWidth
      const ch = el.clientHeight
      if (cw === 0 || ch === 0) return
      const sFit = Math.min(cw / NATURAL_W, ch / NATURAL_H)
      const s = Math.min(MAX_SCALE, Math.max(MIN_SCALE, sFit))
      setScale(s)
    }
    const ro = new ResizeObserver(compute)
    ro.observe(el)
    compute()
    return () => ro.disconnect()
  }, [])

  return (
    <div className="preview-scroll" ref={scrollRef} aria-label="简历内容预览">
      <div
        style={{
          width: NATURAL_W * scale,
          height: NATURAL_H * scale,
          position: 'relative',
          margin: '0 auto',
        }}
      >
        <article
          className="paper-preview"
          aria-label="简历预览"
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: NATURAL_W,
            minHeight: NATURAL_H,
            transform: `scale(${scale})`,
            transformOrigin: 'top left',
          }}
        >
          {sections && sections.length > 0 ? (
            sections.map((sec, sIdx) => (
              <section key={`${sec.section}-${sIdx}`} className="paper-preview__section">
                <h2 className="paper-preview__heading">{sec.title}</h2>
                {sec.entries.map((ent, eIdx) => (
                  <div key={`${sIdx}-${eIdx}`} className="paper-preview__entry">
                    <div className="paper-preview__entry-head">
                      {ent.heading && (
                        <span className="paper-preview__entry-title">{ent.heading}</span>
                      )}
                      {ent.subhead && (
                        <span className="paper-preview__entry-sub">{ent.subhead}</span>
                      )}
                    </div>
                    {sec.section === 'skills' ? (
                      <div className="paper-preview__skill-line">
                        <strong>{ent.heading}</strong>
                        {ent.bullets.join('、')}
                      </div>
                    ) : ent.bullets.length > 0 ? (
                      <ul className="paper-preview__bullets">
                        {ent.bullets.map((b, bIdx) => {
                          const isSelected =
                            selected?.sectionIdx === sIdx &&
                            selected?.entryIdx === eIdx &&
                            selected?.bulletIdx === bIdx
                          return (
                            <li
                              key={`${sIdx}-${eIdx}-${bIdx}`}
                              className={
                                'paper-preview__bullet' +
                                (isSelected ? ' paper-preview__bullet--selected' : '')
                              }
                              onClick={() =>
                                onSelect({ sectionIdx: sIdx, entryIdx: eIdx, bulletIdx: bIdx })
                              }
                              onKeyDown={(e) => {
                                if (e.key === 'Enter' || e.key === ' ') {
                                  e.preventDefault()
                                  onSelect({
                                    sectionIdx: sIdx,
                                    entryIdx: eIdx,
                                    bulletIdx: bIdx,
                                  })
                                }
                              }}
                              role="button"
                              tabIndex={0}
                              aria-pressed={isSelected}
                            >
                              {b}
                            </li>
                          )
                        })}
                      </ul>
                    ) : null}
                  </div>
                ))}
              </section>
            ))
          ) : (
            <div className="empty" style={{ padding: 'var(--s6) var(--s4)' }}>
              <div className="empty__title">本次响应未携带内容预览</div>
              <div className="empty__desc">
                可直接下载下方 DOCX；预览能力依赖后端 V2.1.0 T6 字段。
              </div>
            </div>
          )}
        </article>
      </div>
    </div>
  )
}
