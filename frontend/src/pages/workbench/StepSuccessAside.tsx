import { useMemo } from 'react'
import { useWorkbenchTask } from './WorkbenchTaskContext'
import { artifactFileName, taskArtifactUrl } from '../../api/artifact'
import { anchorSelectionKey } from '../../components/PdfPreview'
import type { PdfAnchor } from '../../api/types'

/**
 * V2.2.0 T06：P4 成功后的右侧说明卡，对应冻结 DS-003 `successAside()`。
 * 未选择时：intro（「已为这个岗位整理好」）→ 完成摘要 → 底部固定下载区（↓ Word / ↓ PDF）。
 * 选择时：标题随所选对象变化（DS-003：Fact 详情 / 段落详情），正文展示与所选对象一致的内容：
 *   - fact  →  该条事实的表述 + 「与岗位的联系」(真实 reasons) + 「已确认的原始事实」(fact_refs 原文)；
 *   - 整段经历/项目  →  条目标题 + 角色·时段 + 该段全部事实（headline + 来源）；
 *   - 技能专长  →  由已采用事实整理的能力类别与条目。
 *
 * V2.2.0 DOC_RETURNED 返工：
 *  - 选择状态为**受控**，由 WorkbenchPage 持有并下发（唯一 P4 选择入口 = PDF 热点，
 *    本卡只消费、不另建第二套选择实现）；
 *  - 详情一律取自当前 Task 的权威数据：artifacts.pdf_anchors（锚点身份与 fact_id）、
 *    snapshotPayload.experiences（headline/body/fact_refs）、reasons（选择理由）、
 *    artifacts.preview_sections / preview_skills / fact_sources（同一最终 ResumeDocument 投影）；
 *  - 任何缺失（无 facts、无理由、无原文、无投影）都如实留白说明，绝不编造细节。
 */

interface ArtifactsView {
  pdf_path?: string
  pdf_artifact_id?: string
  pdf_sha256?: string
  pdf_anchors?: PdfAnchor[] | null
  docx_path?: string
  preview_sections?: PreviewSection[] | null
  preview_skills?: PreviewSkill[] | null
  fact_sources?: Record<string, string> | null
}

interface PreviewSection {
  experience_id?: string
  kind?: string
  heading?: string
  subhead?: string
}

interface PreviewSkill {
  category?: string
  items?: string[] | string | null
}

interface SnapshotFact {
  fact_id?: string
  headline?: string
  body?: string
  fact_refs?: string[]
}

interface SnapshotExperience {
  experience_id?: string
  sort_order?: number
  title?: string
  role?: string
  period?: string
  facts?: SnapshotFact[]
}

function skillItemsText(items: PreviewSkill['items']): string {
  if (Array.isArray(items)) return items.filter((x) => !!x).join('、')
  return typeof items === 'string' ? items : ''
}

export interface StepSuccessAsideProps {
  /** 受控选中锚点（null = 未选择，展示 intro + 摘要）。 */
  selection: PdfAnchor | null
}

export default function StepSuccessAside({ selection }: StepSuccessAsideProps) {
  const { taskId, status, snapshotPayload, publishedDocxPath, publishedPdfPath, reasons } =
    useWorkbenchTask()

  const artifacts = useMemo<ArtifactsView>(() => {
    const a = snapshotPayload?.artifacts
    if (a && typeof a === 'object') return a as ArtifactsView
    return {}
  }, [snapshotPayload])

  const experiences = useMemo<SnapshotExperience[]>(() => {
    const e = snapshotPayload?.experiences
    return Array.isArray(e) ? (e as SnapshotExperience[]) : []
  }, [snapshotPayload])

  const docxRel = publishedDocxPath || artifacts.docx_path || ''
  const pdfRel = publishedPdfPath || artifacts.pdf_path || ''
  const pdfAvailable = status === 'SUCCEEDED' && !!pdfRel
  const docxAvailable = status === 'SUCCEEDED' && !!docxRel
  const docxHref = docxAvailable ? taskArtifactUrl(taskId, 'docx') : ''
  const pdfHref = pdfAvailable ? taskArtifactUrl(taskId, 'pdf') : ''

  // V220-R3-G07：下载区不保留空占位；真实可验证 hash（PDF SHA-256）有值才展示，无值不渲染。
  const pdfSha256 = (artifacts.pdf_sha256 || '').trim()

  const selectedKey = selection ? anchorSelectionKey(selection) : null

  /** 选择身份 → 详情视图（数据全部来自当前 Task 权威快照/投影）。 */
  const detail = useMemo<React.ReactNode>(() => {
    if (!selection || !selectedKey) return null

    if (selectedKey === 'skills') {
      const rows = (artifacts.preview_skills ?? []).filter((s) => !!s && !!s.category)
      return (
        <div className="section-detail">
          <h3>技能专长</h3>
          <p className="field-help">由已采用事实整理</p>
          {rows.length === 0 ? (
            <p className="section-detail__empty">本次未产出可展示的技能类别。</p>
          ) : (
            rows.map((s, i) => (
              <div className="section-detail-row" key={`${s.category}-${i}`}>
                <strong>{s.category}</strong>
                <p>{skillItemsText(s.items)}</p>
              </div>
            ))
          )}
        </div>
      )
    }

    if (selectedKey.startsWith('fact:')) {
      const factId = selectedKey.slice('fact:'.length)
      let host: SnapshotExperience | null = null
      let fact: SnapshotFact | null = null
      for (const exp of experiences) {
        const hit = (exp.facts ?? []).find((f) => f.fact_id === factId)
        if (hit) {
          host = exp
          fact = hit
          break
        }
      }
      const refs = (fact?.fact_refs ?? selection.fact_refs ?? []).filter((r) => !!r)
      const sources = refs
        .map((r) => (artifacts.fact_sources ?? {})[r])
        .filter((t): t is string => typeof t === 'string' && t.length > 0)
      const reason = reasons[factId] ?? ''
      return (
        <div className="detail-stream">
          <h3>{fact?.headline ? `${fact.headline} · 选择理由` : '事实 · 选择理由'}</h3>
          <p>{host?.title || '该事实所属经历未记录'}</p>
          <div className="reason-box">
            <strong>与岗位的联系</strong>
            <span>{reason || '本次未记录该条事实的选择理由。'}</span>
          </div>
          <details className="source-box">
            <summary>查看已确认的原始事实 ⌄</summary>
            {sources.length > 0 ? (
              <blockquote>{sources.join('\n')}</blockquote>
            ) : (
              <blockquote>该条事实未记录可展示的原文依据。</blockquote>
            )}
          </details>
        </div>
      )
    }

    if (selectedKey.startsWith('section:')) {
      const sectionId = selectedKey.slice('section:'.length)
      const meta = (artifacts.preview_sections ?? []).find((s) => s.experience_id === sectionId)
      const host = experiences.find((e) => e.experience_id === sectionId)
      const facts = (host?.facts ?? []).filter((f) => !!f.fact_id && !!f.headline)
      const heading = meta?.heading || host?.title || '该段落'
      const subhead = meta?.subhead || [host?.role, host?.period].filter(Boolean).join(' · ')
      return (
        <div className="section-detail">
          <h3>{heading}</h3>
          <p className="field-help">{subhead || '未记录角色与时段'}</p>
          {facts.length === 0 ? (
            <p className="section-detail__empty">该段落未记录可展示的已确认事实。</p>
          ) : (
            facts.map((f) => (
              <div className="section-fact section-fact--static" key={f.fact_id}>
                <strong>{f.headline}</strong>
                <span>
                  {(f.fact_refs ?? [])
                    .map((r) => (artifacts.fact_sources ?? {})[r])
                    .filter((t): t is string => typeof t === 'string' && t.length > 0)
                    .join('；') || '未记录原文依据'}
                </span>
              </div>
            ))
          )}
        </div>
      )
    }

    return (
      <div className="section-detail">
        <p className="section-detail__empty">该选中对象无法对应到已确认内容。</p>
      </div>
    )
  }, [selection, selectedKey, artifacts, experiences, reasons])

  const title = selectedKey?.startsWith('fact:')
    ? 'Fact 详情'
    : selectedKey
      ? '段落详情'
      : '已为这个岗位整理好'

  return (
    <>
      <div className="wb-panel__head">
        <div>
          <div className="wb-panel__head-title">{title}</div>
          <div className="wb-panel__head-sub">
            {selectedKey ? (
              <span className="wb-badge wb-badge--neutral">已选择 · 再次点击可取消</span>
            ) : (
              <span className="wb-badge wb-badge--ok">✓ 已完成</span>
            )}
          </div>
        </div>
      </div>
      <div className="wb-panel__scroll">
        {detail ?? (
          <>
            <div className="wb-aside-intro">
              <div className="wb-aside-eyebrow">READY FOR YOUR NEXT STEP</div>
              <h3 className="wb-aside-title">
                把你的经历，
                <br />
                清楚地呈现出来。
              </h3>
              <p className="wb-aside-desc">
                基于你已确认的经历与目标岗位，整理为一份可投递的岗位简历，并已导出 Word 与 PDF
                文件。点击左侧 PDF 中的事实、整段经历或技能专长可查看详情；再次点击即可取消。
              </p>
            </div>
            <ul className="wb-aside-summary">
              <li>
                <span className="wb-aside-summary__check" aria-hidden="true">
                  ✓
                </span>
                联系方式来自本次身份输入
              </li>
              <li>
                <span className="wb-aside-summary__check" aria-hidden="true">
                  ✓
                </span>
                每段经历均有已确认事实支撑
              </li>
              <li>
                <span className="wb-aside-summary__check" aria-hidden="true">
                  ✓
                </span>
                Word 是唯一排版真源，PDF 由同一 Word 生成
              </li>
            </ul>
          </>
        )}
      </div>
      <footer className="wb-panel__foot wb-success-downloads" aria-label="简历下载">
        {docxHref ? (
          <a
            className="wb-btn wb-btn--ghost wb-btn--sm"
            href={docxHref}
            download={artifactFileName(taskId, 'docx')}
            data-role="download-word"
          >
            ↓ Word
          </a>
        ) : null}
        {pdfHref ? (
          <a
            className="wb-btn wb-btn--primary wb-btn--sm"
            href={pdfHref}
            download={artifactFileName(taskId, 'pdf')}
            data-role="download-pdf"
          >
            ↓ PDF
          </a>
        ) : null}
        {pdfAvailable && pdfSha256 ? (
          <span className="wb-success-downloads__hash" title="PDF 文件 SHA-256">
            校验 {pdfSha256.slice(0, 12)}
          </span>
        ) : null}
      </footer>
    </>
  )
}