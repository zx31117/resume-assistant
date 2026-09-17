import { Link } from 'react-router-dom'
import PageHeader from '../components/PageHeader'
import Badge from '../components/ui/Badge'
import Card from '../components/ui/Card'
import { useWorkbenchTask } from './workbench/WorkbenchTaskContext'

/**
 * V2.2.0 T07：我的简历——查看真实可用的生成记录与 artifact。
 *
 * 真实能力映射（无 fixture、无伪造列表）：
 * - 后端没有「已生成文件/任务列表」查询端点，故本页不伪造 N 条历史列表；
 * - 唯一真实可展示对象为「当前任务」：其终态发布路径由 `WorkbenchTaskContext` 提供
 *   （`published_docx_path / published_pdf_path`，仅 SUCCEEDED 后非空），与工作台 P4 同源；
 * - 下载走 `publishedXxxPath` → 同一 `/api/template/download` artifact，与生成流程逐字一致；
 * - 任务未生成/运行中/失败/取消 → 如实显示空与下一步，绝不伪造可用链接。
 */

/** 相对路径 output/<file> → 同源下载 URL（沿用 /api/template/download，支持 Range/MIME/Hash）。 */
function artifactUrl(relPath: string): string {
  return `/api/template/download?path=${encodeURIComponent(relPath)}`
}

function basename(relPath: string): string {
  const parts = relPath.split('/')
  return parts[parts.length - 1] || relPath
}

export default function RecordsPage() {
  const { taskId, status, input, publishedDocxPath, publishedPdfPath } = useWorkbenchTask()

  const hasTask = !!taskId
  const docxRel = publishedDocxPath
  const pdfRel = publishedPdfPath
  const docxAvailable = !!docxRel
  const pdfAvailable = status === 'SUCCEEDED' && !!pdfRel
  const name = input?.name?.trim()

  return (
    <div className="page">
      <PageHeader
        title="我的简历"
        description="已生成的简历与导出文件。本页连接当前生成任务的真实产物，不做伪造列表。"
      />

      <div className="page-scroll">
        <Card title="当前任务的生成记录" subtitle={hasTask ? '来自工作台正在 / 已经进行的任务' : '尚无进行中的任务'}>
          {!hasTask ? (
            <div className="empty" style={{ margin: 'var(--s4) 0' }}>
              <p className="empty__title">还没有进行中的任务</p>
              <p className="empty__desc">
                前往工作台填写身份与岗位描述并开始生成后，这里会显示该任务生成的真实 Word / PDF。
                后端当前不提供已生成文件列表查询，因此不伪造历史列表。
              </p>
              <div style={{ marginTop: 'var(--s3)' }}>
                <Link className="btn btn--primary btn--md" to="/">
                  返回生成工作台
                </Link>
              </div>
            </div>
          ) : (
            <div className="stack" style={{ marginTop: 'var(--s4)' }}>
              <div className="hstack" style={{ flexWrap: 'wrap', gap: 'var(--s3)' }}>
                <Badge tone={status === 'SUCCEEDED' ? 'ok' : 'neutral'}>{status ?? '—'}</Badge>
                {name && <span className="exp-item__title">{name}</span>}
                {input?.jd?.trim()?.length ? (
                  <span className="muted">JD {input.jd.trim().length} 字</span>
                ) : null}
              </div>

              {status === 'SUCCEEDED' ? (
                docxAvailable ? (
                  <div className="privacy-list">
                    <div className="privacy-row">
                      <span className="privacy-row__title">Word 文档</span>
                      <span className="privacy-row__desc">
                        本次生成的唯一排版真源（ResumeDocument → DOCX）。
                        <a
                          className="btn btn--primary btn--sm"
                          style={{ marginTop: 'var(--s2)', display: 'inline-block' }}
                          href={artifactUrl(docxRel!)}
                          download={basename(docxRel!)}
                          data-role="download-word-record"
                        >
                          下载 Word
                        </a>
                      </span>
                    </div>
                    <div className="privacy-row">
                      <span className="privacy-row__title">PDF 文档</span>
                      <span className="privacy-row__desc">
                        由同一 Word 经本机转换生成；与工作台预览为同一文件。
                        {pdfAvailable ? (
                          <a
                            className="btn btn--ghost btn--sm"
                            style={{ marginTop: 'var(--s2)', display: 'inline-block' }}
                            href={artifactUrl(pdfRel!)}
                            download={basename(pdfRel!)}
                            data-role="download-pdf-record"
                          >
                            下载 PDF
                          </a>
                        ) : (
                          <span className="muted">
                            {' '}
                            （本次未生成 PDF，Word 仍可用）
                          </span>
                        )}
                      </span>
                    </div>
                    <div style={{ marginTop: 'var(--s3)' }}>
                      <Link className="btn btn--ghost btn--sm" to="/">
                        返回查看 / 继续下载
                      </Link>
                    </div>
                  </div>
                ) : (
                  <p className="muted">当前任务尚未发布 artifact，请返回工作台在 P4 完成后下载。</p>
                )
              ) : (
                <p className="muted">
                  {status === 'RUNNING'
                    ? '生成进行中，完成后这里会出现可下载的 Word / PDF。'
                    : status === 'FAILED'
                    ? '本次生成失败：返回工作台查看失败范围并重试。'
                    : status === 'CANCELLED'
                    ? '本次生成已取消，输入已保留；可在工作台重新生成。'
                    : '任务尚未生成：返回工作台填写身份与 JD 后可生成。'}
                </p>
              )}
              <p className="muted" style={{ fontSize: 'var(--text-sm)' }}>
                {docxAvailable
                  ? `Word：${basename(docxRel!)}`
                  : '当前无可下载的 Word artifact'}
                {pdfAvailable ? ` · PDF：${basename(pdfRel!)}` : ''}
              </p>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}