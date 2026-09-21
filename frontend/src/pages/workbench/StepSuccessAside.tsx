import { useMemo } from 'react'
import { useWorkbenchTask } from './WorkbenchTaskContext'
import type { PdfAnchor } from '../../api/types'

/**
 * V2.2.0 T06：P4 成功后的右侧说明卡，对应冻结 DS-003 `successAside()`。
 * 信息层级：intro（「已为这个岗位整理好」）→ 完成摘要 → 底部固定下载区（↓ Word / ↓ PDF）。
 * - 下载与主面板 PDF.js viewer 读取同一 artifact（published_pdf_path / published_docx_path），字节一致；
 * - PDF 缺失（生成失败）时保留 Word 下载，绝不伪造 PDF 链接。
 */

/** 相对路径 output/<file> → 同源下载 URL（沿用 /api/template/download）。 */
function artifactUrl(relPath: string): string {
  return `/api/template/download?path=${encodeURIComponent(relPath)}`
}

/** output/<file> → <file>（用于 <a download> 文件名）。 */
function basename(relPath: string): string {
  const parts = relPath.split('/')
  return parts[parts.length - 1] || relPath
}

interface ArtifactsView {
  pdf_path?: string
  pdf_artifact_id?: string
  pdf_sha256?: string
  pdf_anchors?: PdfAnchor[] | null
  docx_path?: string
}

export default function StepSuccessAside() {
  const { status, snapshotPayload, publishedDocxPath, publishedPdfPath } = useWorkbenchTask()

  const artifacts = useMemo<ArtifactsView>(() => {
    const a = snapshotPayload?.artifacts
    if (a && typeof a === 'object') return a as ArtifactsView
    return {}
  }, [snapshotPayload])

  const docxRel = publishedDocxPath || artifacts.docx_path || ''
  const pdfRel = publishedPdfPath || artifacts.pdf_path || ''
  const pdfAvailable = status === 'SUCCEEDED' && !!pdfRel
  const docxAvailable = !!docxRel

  // 读取 word/pdf 相对路径，仅用于 <a download> 的文件名与 URL。
  const pdfName = useMemo(() => (pdfRel ? basename(pdfRel) : ''), [pdfRel])
  const docxName = useMemo(() => (docxRel ? basename(docxRel) : ''), [docxRel])

  // 锚点仅存在于快照 artifacts（与主面板 viewer 共用同一真源），此卡不渲染命中层。
  void artifacts

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
        {docxAvailable ? (
          <a
            className="wb-btn wb-btn--ghost wb-btn--sm"
            href={artifactUrl(docxRel)}
            download={docxName}
            data-role="download-word"
          >
            ↓ Word
          </a>
        ) : (
          <span className="wb-success-downloads__missing">Word 不可用</span>
        )}
        {pdfAvailable ? (
          <a
            className="wb-btn wb-btn--primary wb-btn--sm"
            href={artifactUrl(pdfRel)}
            download={pdfName}
            data-role="download-pdf"
          >
            ↓ PDF
          </a>
        ) : (
          <span className="wb-success-downloads__missing" title="PDF 生成失败，Word 仍可用">
            PDF 不可用
          </span>
        )}
      </footer>
    </>
  )
}