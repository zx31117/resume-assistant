import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import PageHeader from '../components/PageHeader'
import Badge from '../components/ui/Badge'
import Card from '../components/ui/Card'
import { taskApi } from '../api/endpoints'
import type { TaskRecordOut } from '../api/types'

/**
 * V2.2.0 T07/R2-T08：我的简历——查看真实可用的生成记录与 artifact。
 *
 * 真实能力映射（无 fixture、无伪造列表）：
 * - 后端 GET /api/task/records 只返回 SUCCEEDED 且已发布 DOCX/PDF 产物的任务，
 *   为空返回 []，绝不伪造历史列表；
 * - 每条记录渲染真实 `/api/template/download` 下载链接（与工作台 P4 同源逐字一致）；
 * - 文档未生成/运行中/失败/取消 → 不出现在列表，如实显示空与下一步。
 */

/** 相对路径 output/<file> → 同源下载 URL（沿用 /api/template/download）。 */
function artifactUrl(relPath: string): string {
  return `/api/template/download?path=${encodeURIComponent(relPath)}`
}

function basename(relPath: string): string {
  const parts = relPath.split('/')
  return parts[parts.length - 1] || relPath
}

function fmtDate(iso: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('zh-CN', { hour12: false })
}

export default function RecordsPage() {
  const [records, setRecords] = useState<TaskRecordOut[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    taskApi
      .records()
      .then((rows) => {
        if (alive) setRecords(rows)
      })
      .catch((e: unknown) => {
        if (alive) setError(e instanceof Error ? e.message : String(e))
      })
    return () => {
      alive = false
    }
  }, [])

  const loading = records === null && error === null

  return (
    <div className="page">
      <PageHeader
        title="我的简历"
        description="已生成的简历与导出文件。列表来自后端记录查询，只展示真实发布产物，不做伪造。"
      />

      <div className="page-scroll">
        <Card title="已生成记录" subtitle="来自后端 GET /api/task/records 的真实发布记录">
          {error ? (
            <div className="empty" style={{ margin: 'var(--s4) 0' }}>
              <p className="empty__title">记录加载失败</p>
              <p className="empty__desc">{error}</p>
              <div style={{ marginTop: 'var(--s3)' }}>
                <button
                  className="btn btn--primary btn--sm"
                  onClick={() => {
                    setError(null)
                    setRecords(null)
                    taskApi.records().then(setRecords).catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
                  }}
                >
                  重新加载
                </button>
              </div>
            </div>
          ) : loading ? (
            <p className="muted" style={{ margin: 'var(--s4) 0' }}>正在加载记录…</p>
          ) : records!.length === 0 ? (
            <div className="empty" style={{ margin: 'var(--s4) 0' }}>
              <p className="empty__title">还没有已生成的记录</p>
              <p className="empty__desc">
                当前没有已发布 Word / PDF 的生成记录。前往工作台填写身份与岗位描述并开始生成，
                完成后这里会列出该任务发布的可下载 Word / PDF。
              </p>
              <div style={{ marginTop: 'var(--s3)' }}>
                <Link className="btn btn--primary btn--md" to="/">
                  返回生成工作台
                </Link>
              </div>
            </div>
          ) : (
            <div className="stack" style={{ marginTop: 'var(--s3)' }}>
              {records!.map((rec) => {
                const name = rec.latest_input?.name?.trim()
                const jdLen = rec.latest_input?.jd_len ?? 0
                const docxRel = rec.published_docx_path
                const pdfRel = rec.published_pdf_path
                const pdfAvailable = !!pdfRel
                return (
                  <div className="privacy-list" key={rec.task_id} style={{ marginBottom: 'var(--s3)' }}>
                    <div className="privacy-row">
                      <span className="privacy-row__title">
                        {name || '未命名'}
                      </span>
                      <span className="privacy-row__desc">
                        <span className="muted" style={{ marginRight: 'var(--s2)' }}>
                          更新于 {fmtDate(rec.updated_at)}
                        </span>
                        <Badge tone="ok">已发布</Badge>
                        {jdLen > 0 && <span className="muted">JD {jdLen} 字</span>}
                      </span>
                    </div>
                    <div className="privacy-row">
                      <span className="privacy-row__title">Word 文档</span>
                      <span className="privacy-row__desc">
                        {docxRel ? (
                          <a
                            className="btn btn--primary btn--sm"
                            style={{ marginTop: 'var(--s2)', display: 'inline-block' }}
                            href={artifactUrl(docxRel)}
                            download={basename(docxRel)}
                            data-role="download-word-record"
                          >
                            下载 {basename(docxRel)}
                          </a>
                        ) : (
                          <span className="muted">无 Word 产物</span>
                        )}
                      </span>
                    </div>
                    <div className="privacy-row">
                      <span className="privacy-row__title">PDF 文档</span>
                      <span className="privacy-row__desc">
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
                          <span className="muted">（本次未生成 PDF，Word 仍可用）</span>
                        )}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}