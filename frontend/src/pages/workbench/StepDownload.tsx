import { useMemo } from 'react'
import PdfPreview from '../../components/PdfPreview'
import type { PdfAnchor } from '../../api/types'
import { useWorkbenchTask } from './WorkbenchTaskContext'

/**
 * V2.2.0 T06：步骤 4「修改与下载」的最终 P4 视图。
 * - 仅在任务 SUCCEEDED 且已发布 PDF artifact 时替换 P3 HTML 过程预览；
 *   running/其他终态仍由 WorkbenchPage 继续展示 StepCheckout 过程预览（诚实，不抢先）。
 * - PDF.js viewer 与「下载 PDF」读取同一 artifact（published_pdf_path），字节一致；
 * - anchor/依据：数据唯一真源 = P4 快照 artifacts.pdf_anchors（由后端从确切 PDF 文本层重建，
 *   绑定 pdf_artifact_id）。无 anchors / 与 artifact 身份错配 → PdfPreview 内建 fail closed，不渲染命中层；
 * - Word/PDF 下载独立可用；PDF 缺失（生成失败）时保留 Word 下载，绝不在 PDF 上伪造可用链接。
 */

/** 相对路径 output/<file> → 同源下载 URL（沿用 /api/template/download，支持 Range/MIME/Hash）。 */
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

export default function StepDownload() {
  const { status, snapshotPayload, publishedDocxPath, publishedPdfPath } = useWorkbenchTask()

  const artifacts = useMemo<ArtifactsView>(() => {
    const a = snapshotPayload?.artifacts
    if (a && typeof a === 'object') return a as ArtifactsView
    return {}
  }, [snapshotPayload])

  // 优先用终态发布路径；快照 artifacts 仅作为锚点/身份的补充（两者应指向同一文件）。
  const docxRel = publishedDocxPath || artifacts.docx_path || ''
  const pdfRel = publishedPdfPath || artifacts.pdf_path || ''
  const pdfAvailable = status === 'SUCCEEDED' && !!pdfRel
  const docxAvailable = !!docxRel

  const anchors = artifacts.pdf_anchors && Array.isArray(artifacts.pdf_anchors)
    ? artifacts.pdf_anchors
    : null
  const artifactId = artifacts.pdf_artifact_id || null

  const pdfUrl = pdfRel ? artifactUrl(pdfRel) : ''
  const pdfName = pdfRel ? basename(pdfRel) : ''
  const docxName = docxRel ? basename(docxRel) : ''

  // —— Word 不可用（未成功）→ 诚实占位，不出现下载动作 ——
  if (!docxAvailable) {
    return (
      <div className="wb-analyzing wb-analyzing--empty">
        <div className="wb-analyzing__title">生成仍在进行，暂无可下载的成品</div>
        <p className="wb-analyzing__sub">
          任务完成后会在此提供 Word / PDF 下载；仅当后端确认产物生成成功后才显示可下载内容。
        </p>
      </div>
    )
  }

  return (
    <div className="wb-download">
      <div className="wb-download__bar">
        <div className="wb-download__meta">
          <span className="wb-download__eyebrow">成品 PDF</span>
          <span className="wb-download__file">{pdfName || '（PDF 未生成）'}</span>
          {artifactId && artifacts.pdf_sha256 ? (
            <span className="wb-download__hash">sha256 {artifacts.pdf_sha256.slice(0, 16)}…</span>
          ) : null}
        </div>
        <div className="wb-download__actions">
          <a
            className="wb-btn wb-btn--primary wb-btn--sm"
            href={artifactUrl(docxRel)}
            download={docxName}
            data-role="download-word"
          >
            下载 Word
          </a>
          {pdfAvailable ? (
            <a
              className="wb-btn wb-btn--ghost wb-btn--sm"
              href={pdfUrl}
              download={pdfName}
              data-role="download-pdf"
            >
              下载 PDF
            </a>
          ) : (
            <span className="wb-download__missing" title="PDF 生成失败，Word 仍可用">
              PDF 不可用
            </span>
          )}
        </div>
      </div>

      <div className="wb-download__hint" role="note">
        PDF 预览与「下载 PDF」为同一文件；Word 是唯一排版真源，PDF 由同一 Word 经本机转换生成。
        {!pdfAvailable ? ' 本次 PDF 生成失败，Word 仍可正常下载使用。' : ''}
      </div>

      <div className="wb-download__preview">
        {pdfAvailable ? (
          <PdfPreview
            url={pdfUrl}
            artifactId={artifactId}
            anchors={anchors}
          />
        ) : (
          <div className="wb-download__nopdf" role="alert">
            <div className="wb-download__nopdf-title">PDF 成品不可用</div>
            <p className="wb-download__nopdf-sub">
              本次未生成 PDF（Word→PDF 转换失败或被跳过）。已保留可下载的 Word 文档。
            </p>
          </div>
        )}
      </div>
    </div>
  )
}