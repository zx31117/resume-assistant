import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import WbTaskHeading from '../components/layout/WbTaskHeading'
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
    <div className="wb-subpage">
      <WbTaskHeading
        title="我的简历"
        desc="每一份简历，都是面向一个具体岗位的表达。列表只展示真实发布的产物，不做伪造。"
      />
      <div className="wb-panel wb-panel--main">
        <div className="wb-panel__head">
          <div>
            <div className="wb-panel__head-title">已生成的简历</div>
            <div className="wb-panel__head-sub">已成功发布 Word / PDF 的真实生成记录</div>
          </div>
        </div>
        <div className="wb-panel__scroll">
          {error ? (
            <div className="wb-empty">
              <div className="wb-empty__icon" aria-hidden="true">
                !
              </div>
              <h3 className="wb-empty__title">记录加载失败</h3>
              <p className="wb-empty__desc">{error}</p>
              <button
                className="wb-btn wb-btn--primary wb-btn--sm"
                onClick={() => {
                  setError(null)
                  setRecords(null)
                  taskApi
                    .records()
                    .then(setRecords)
                    .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
                }}
              >
                重新加载
              </button>
            </div>
          ) : loading ? (
            <div className="wb-empty">
              <div className="wb-empty__icon wb-empty__icon--spin" aria-hidden="true" />
              <p className="wb-empty__desc">正在加载记录…</p>
            </div>
          ) : records!.length === 0 ? (
            <div className="wb-empty">
              <div className="wb-empty__icon" aria-hidden="true">
                ▧
              </div>
              <h3 className="wb-empty__title">还没有已生成的记录</h3>
              <p className="wb-empty__desc">
                前往工作台填写身份与岗位描述并开始生成，完成后这里会列出发布的可下载 Word / PDF。
              </p>
              <Link className="wb-btn wb-btn--primary wb-btn--sm" to="/">
                返回生成工作台
              </Link>
            </div>
          ) : (
            <ul className="wb-record-list">
              {records!.map((rec) => {
                const name = rec.latest_input?.name?.trim()
                const jdLen = rec.latest_input?.jd_len ?? 0
                const docxRel = rec.published_docx_path
                const pdfRel = rec.published_pdf_path
                const pdfAvailable = !!pdfRel
                return (
                  <li className="wb-record" key={rec.task_id}>
                    <div className="wb-record__top">
                      <div className="wb-record__info">
                        <span className="wb-record__title">{name || '未命名'}</span>
                        <span className="wb-badge wb-badge--ok">已发布</span>
                      </div>
                      <span className="wb-record__meta">
                        {jdLen > 0 && `JD ${jdLen} 字`}
                        {jdLen > 0 && ' · '}更新于 {fmtDate(rec.updated_at)}
                      </span>
                    </div>
                    <div className="wb-record__actions">
                      {docxRel ? (
                        <a
                          className="wb-btn wb-btn--ghost wb-btn--sm"
                          href={artifactUrl(docxRel)}
                          download={basename(docxRel)}
                          data-role="download-word-record"
                        >
                          下载 Word
                        </a>
                      ) : (
                        <span className="wb-success-downloads__missing">无 Word 产物</span>
                      )}
                      {pdfAvailable ? (
                        <a
                          className="wb-btn wb-btn--primary wb-btn--sm"
                          href={artifactUrl(pdfRel!)}
                          download={basename(pdfRel!)}
                          data-role="download-pdf-record"
                        >
                          下载 PDF
                        </a>
                      ) : (
                        <span className="wb-success-downloads__missing">（本次未生成 PDF，Word 仍可用）</span>
                      )}
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}