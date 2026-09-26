import { useMemo } from 'react'
import { useWorkbenchTask } from './WorkbenchTaskContext'
import { artifactFileName, taskArtifactUrl } from '../../api/artifact'
import type { PdfAnchor } from '../../api/types'

/**
 * V2.2.0 T06：P4 成功后的右侧说明卡，对应冻结 DS-003 `successAside()`。
 * 信息层级：intro（「已为这个岗位整理好」）→ 完成摘要 → 底部固定下载区（↓ Word / ↓ PDF）。
 * - 下载与主面板 PDF.js viewer 读取同一 artifact（同一 task-scoped 权威路由），字节一致；
 * - PDF 缺失（生成失败）时保留 Word 下载，绝不伪造 PDF 链接。
 * - V2.2.0 R3：URL 由 `taskArtifactUrl(taskId, kind)` 唯一构造，不再使用 filename 路由。
 */

interface ArtifactsView {
  pdf_path?: string
  pdf_artifact_id?: string
  pdf_sha256?: string
  pdf_anchors?: PdfAnchor[] | null
  docx_path?: string
}

export default function StepSuccessAside() {
  const { taskId, status, snapshotPayload, publishedDocxPath, publishedPdfPath } = useWorkbenchTask()

  const artifacts = useMemo<ArtifactsView>(() => {
    const a = snapshotPayload?.artifacts
    if (a && typeof a === 'object') return a as ArtifactsView
    return {}
  }, [snapshotPayload])

  const docxRel = publishedDocxPath || artifacts.docx_path || ''
  const pdfRel = publishedPdfPath || artifacts.pdf_path || ''
  const pdfAvailable = status === 'SUCCEEDED' && !!pdfRel
  const docxAvailable = status === 'SUCCEEDED' && !!docxRel
  const docxHref = docxAvailable ? taskArtifactUrl(taskId, 'docx') : ''
  const pdfHref = pdfAvailable ? taskArtifactUrl(taskId, 'pdf') : ''

  // V220-R3-G07：下载区不保留空占位；真实可验证 hash（PDF SHA-256）有值才展示，无值不渲染。
  const pdfSha256 = (artifacts.pdf_sha256 || '').trim()

  return (
    <>
      <div className="wb-panel__head">
        <div>
          <div className="wb-panel__head-title">已为这个岗位整理好</div>
          <div className="wb-panel__head-sub">
            <span className="wb-badge wb-badge--ok">✓ 已完成</span>
          </div>
        </div>
      </div>
      <div className="wb-panel__scroll">
        <div className="wb-aside-intro">
          <div className="wb-aside-eyebrow">READY FOR YOUR NEXT STEP</div>
          <h3 className="wb-aside-title">
            把你的经历，
            <br />
            清楚地呈现出来。
          </h3>
          <p className="wb-aside-desc">
            基于你已确认的经历与目标岗位，整理为一份可投递的岗位简历，并已导出 Word 与 PDF 文件。
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