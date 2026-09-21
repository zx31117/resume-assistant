import { useMemo } from 'react'
import PdfPreview from '../../components/PdfPreview'
import type { PdfAnchor } from '../../api/types'
import { useWorkbenchTask } from './WorkbenchTaskContext'

/**
 * V2.2.0 T06：步骤 4「修改与下载」的最终 P4 视图（主面板，仅成品预览）。
 * 冻结 DS-003 resumeMain() success 态：主面板以真实 PDF.js viewer 为主视觉，
 * 只保留 `/api/template/download` 文件说明与预览；下载入口在右侧 successAside 固位，不在此重复。
 *
 * - 仅在任务 SUCCEEDED 且已发布 PDF artifact 时替换 P3 HTML 过程预览；
 *   running/其他终态仍由 WorkbenchPage 继续展示 StepCheckout 过程预览（诚实，不抢先）。
 * - PDF.js viewer 与「下载 PDF」读取同一 artifact（published_pdf_path），字节一致；
 * - anchor/依据：数据唯一真源 = P4 快照 artifacts.pdf_anchors（由后端从确切 PDF 文本层重建，
 *   绑定 pdf_artifact_id）。无 anchors / 与 artifact 身份错配 → PdfPreview 内建 fail closed，不渲染命中层；
 * - PDF 缺失（生成失败）时如实展示占位，Word 下载仍由 successAside 提供，绝不在 PDF 上伪造可用链接。
 */

/** 相对路径 output/<file> → 同源下载 URL（沿用 /api/template/download）。 */
function artifactUrl(relPath: string): string {
  return `/api/template/download?path=${encodeURIComponent(relPath)}`
}

interface ArtifactsView {
  pdf_path?: string
  pdf_artifact_id?: string
  pdf_sha256?: string
  pdf_anchors?: PdfAnchor[] | null
  docx_path?: string
}

export default function StepDownload() {
  const { status, snapshotPayload, publishedPdfPath } = useWorkbenchTask()

  const artifacts = useMemo<ArtifactsView>(() => {
    const a = snapshotPayload?.artifacts
    if (a && typeof a === 'object') return a as ArtifactsView
    return {}
  }, [snapshotPayload])

  const pdfRel = publishedPdfPath || artifacts.pdf_path || ''
  const pdfAvailable = status === 'SUCCEEDED' && !!pdfRel

  const anchors = artifacts.pdf_anchors && Array.isArray(artifacts.pdf_anchors)
    ? artifacts.pdf_anchors
    : null
  const artifactId = artifacts.pdf_artifact_id || null

  const pdfUrl = pdfRel ? artifactUrl(pdfRel) : ''

  if (!pdfAvailable) {
    return (
      <div className="wb-analyzing wb-analyzing--empty">
        <div className="wb-analyzing__title">PDF 成品不可用</div>
        <p className="wb-analyzing__sub">
          本次未生成 PDF（Word→PDF 转换失败或被跳过）。右侧说明卡仍可下载已保留的 Word 文档。
        </p>
      </div>
    )
  }

  return (
    <div className="wb-download">
      <div className="wb-download__caption">
        PDF 内容与「下载 PDF」文件一致；Word 是唯一排版真源。
      </div>
      <div className="wb-download__preview">
        <PdfPreview url={pdfUrl} artifactId={artifactId} anchors={anchors} />
      </div>
    </div>
  )
}