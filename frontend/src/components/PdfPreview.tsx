import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react'
import * as pdfjsLib from 'pdfjs-dist'
// V2.1.0 R15b：worker 随包打包（vite 资源方式），不从 CDN 拉取；
// 产物中 worker 以独立 asset（pdf.worker.min-*.mjs）出现，由 workerSrc 定位。
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import type { PdfAnchor } from '../api/types'
import Button from './ui/Button'
import { maybeInjectH6 } from '../h6' // V2.1.0 H6 test-only（正式构建剥离）

// pdf.js v4：页面在独立的 worker 线程解析/栅格化。必须设置本地 worker 路径。
pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl

/**
 * V2.1.0 R15b/R16：结果页「真实 PDF 成品预览」。
 * - 读取与「下载 PDF」完全相同的 pdf_download_url（同一 artifact），内置 pdf.js 渲染；
 * - 每页等比铺满预览卡可用宽度（scale = 内容宽 / 页宽），多页纵向排列；
 *   外层预览卡（.result-shell__preview）是唯一容器，超出高度仅在该卡内容区纵向滚动；
 * - 每页 canvas 之上叠加透明命中层：把后端 PreviewAnchor（PDF 原生坐标 pt、y 自底向上、
 *   page_index 0 起）经与渲染同一 viewport 的 page.getViewport().convertToViewportPoint
 *   换算到屏幕 CSS px（y 翻转为自顶向下），放透明可点元素；纯绝对定位不改 canvas 几何；
 * - 任何失败都不得回退 HTML 近似预览：loading / 失败 / 非 PDF 都停在固定尺寸状态，
 *   提供「重试 / 返回修改输入」入口。
 * - 键盘可达：命中元素为真实 <button>（role 语义天然满足 + aria-label=bullet 文本）。
 */

export interface PdfPreviewProps {
  /** 与「下载 PDF」同一 URL（pdf_download_url）。 */
  url: string
  /** pdf_artifact_id；与 anchor.artifact_id 不一致的锚点整体丢弃（fail closed）。 */
  artifactId?: string | null
  anchors?: PdfAnchor[] | null
  /** 当前选中锚点（父组件持有，用于命中层高亮 / aria-pressed）。 */
  selectedAnchor?: PdfAnchor | null
  onSelectAnchor?: (anchor: PdfAnchor | null) => void
  onRetry?: () => void
  onBackToEdit?: () => void
}

interface PageMeta {
  pageNo: number
  baseW: number
  baseH: number
}

interface HitRect {
  key: string
  left: number
  top: number
  width: number
  height: number
  anchor: PdfAnchor
}

interface PageView {
  pageNo: number
  cssW: number
  cssH: number
  hits: HitRect[]
}

type Status = 'loading' | 'ready' | 'error'

export function pdfAnchorKey(a: PdfAnchor): string {
  return `${a.artifact_id}::${a.page_index}::${a.content_item_id ?? ''}::${a.bullet_index ?? -1}::${a.x0}::${a.y0}`
}

const PDF_MAGIC = [0x25, 0x50, 0x44, 0x46] // %PDF

function looksLikePdf(bytes: Uint8Array): boolean {
  if (bytes.length < PDF_MAGIC.length) return false
  return PDF_MAGIC.every((b, i) => bytes[i] === b)
}

export default function PdfPreview({
  url,
  artifactId,
  anchors,
  selectedAnchor,
  onSelectAnchor,
  onRetry,
  onBackToEdit,
}: PdfPreviewProps) {
  maybeInjectH6('pdf') // V2.1.0 H6 test-only：viewer 区注入（正式构建剥离）
  const [status, setStatus] = useState<Status>('loading')
  const [errorText, setErrorText] = useState<string | null>(null)
  const [docMeta, setDocMeta] = useState<PageMeta[] | null>(null)
  const [availW, setAvailW] = useState(0)
  const [pages, setPages] = useState<PageView[] | null>(null)
  const [reload, setReload] = useState(0)

  const docRef = useRef<pdfjsLib.PDFDocumentProxy | null>(null)
  const pageObjsRef = useRef(new Map<number, pdfjsLib.PDFPageProxy>())
  const canvasRefs = useRef(new Map<number, HTMLCanvasElement>())
  const renderTasksRef = useRef(new Map<number, pdfjsLib.RenderTask>())
  const scrollAreaRef = useRef<HTMLDivElement | null>(null)
  const drawSeqRef = useRef(0)

  /**
   * 同步取消所有尚未结束的渲染任务。
   * pdf.js 在 render() 期间通过内部 WeakSet 记录占用中的 canvas
   * （pdf.mjs initializeGraphics：`Cannot use the same canvas during
   * multiple render() operations.`），只有任务正常完成或 cancel() 才会释放。
   * 因此在任何「用同一 canvas 再画一次」之前必须先 cancel 旧任务；
   * 若需彻底等待其收尾（promise settle），调用方再对任务 promise 取反即可。
   * clear=false 保留 map：留给紧接着的新一轮绘制在开画前 await settle。
   */
  const cancelRenderTasks = useCallback((clear: boolean) => {
    const inflight = [...renderTasksRef.current.values()]
    if (clear) renderTasksRef.current.clear()
    for (const t of inflight) {
      try {
        t.cancel()
      } catch {
        // 已完成/已取消任务再次 cancel 属预期，忽略。
      }
    }
    return inflight
  }, [])

  const selectedKey = selectedAnchor ? pdfAnchorKey(selectedAnchor) : null

  /* ── 只保留与当前 artifact 匹配的锚点（不匹配 → fail closed，不渲染命中层） ── */
  const usableAnchors = useMemo(() => {
    const list = anchors ?? []
    if (!artifactId) {
      // 响应未给 artifact_id（旧后端）：无法核对身份，宁可不叠加命中层也不猜测。
      return []
    }
    return list.filter((a) => a.artifact_id === artifactId)
  }, [anchors, artifactId])

  const resetDoc = useCallback(() => {
    const doc = docRef.current
    docRef.current = null
    pageObjsRef.current.clear()
    canvasRefs.current.clear()
    // 先取消未完成渲染并释放其 canvas 占用，再销毁 doc，避免 destroy 撞上活跃渲染。
    cancelRenderTasks(true)
    if (doc) {
      // 只对仍属于本组件的 doc 调用 destroy（先置 null，避免重复销毁）。
      void doc.destroy().catch(() => undefined)
    }
  }, [cancelRenderTasks])

  /* ── 加载与解析（同源 GET pdf_download_url → getDocument({data})） ── */
  useEffect(() => {
    let alive = true
    setStatus('loading')
    setErrorText(null)
    setPages(null)
    setDocMeta(null)
    setAvailW(0)
    resetDoc()
    async function load() {
      try {
        const resp = await fetch(url, { headers: { Accept: 'application/pdf' } })
        if (!resp.ok) {
          throw new Error(`下载 PDF 失败（HTTP ${resp.status}）。`)
        }
        const buf = await resp.arrayBuffer()
        const bytes = new Uint8Array(buf)
        if (!looksLikePdf(bytes)) {
          throw new Error('服务器返回的不是 PDF 文件。')
        }
        const doc = await pdfjsLib.getDocument({ data: bytes }).promise
        if (!alive) {
          // 卸载已发生：销毁本次本地 doc（尚未挂到 ref，由本分支负责）。
          void doc.destroy().catch(() => undefined)
          return
        }
        docRef.current = doc
        const metas: PageMeta[] = []
        for (let n = 1; n <= doc.numPages; n++) {
          const page = await doc.getPage(n)
          pageObjsRef.current.set(n, page)
          const vp = page.getViewport({ scale: 1 })
          metas.push({ pageNo: n, baseW: vp.width, baseH: vp.height })
        }
        if (!alive) return
        setDocMeta(metas)
        setStatus('ready')
      } catch (e) {
        if (!alive) return
        setErrorText(e instanceof Error ? e.message : String(e))
        setStatus('error')
      }
    }
    void load()
    return () => {
      alive = false
      resetDoc()
    }
  }, [url, reload, resetDoc])

  /* ── 预览卡可用宽度：只影响画布尺寸/命中层换算，不改变外框 ── */
  useEffect(() => {
    if (status !== 'ready') return
    const el = scrollAreaRef.current
    if (!el) return
    const measure = () => setAvailW((prev) => {
      const w = el.clientWidth
      return Math.abs(w - prev) > 0.5 ? w : prev
    })
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [status])

  /* ── 用 docMeta + availW 计算每页 CSS 几何与命中层矩形（同一 viewport 换算） ── */
  useEffect(() => {
    if (status !== 'ready' || !docMeta || !availW) {
      setPages(null)
      return
    }
    maybeInjectH6('overlay') // V2.1.0 H6 test-only：命中层区注入（正式构建剥离）
    const byPage = new Map<number, PdfAnchor[]>()
    for (const a of usableAnchors) {
      const list = byPage.get(a.page_index) ?? []
      list.push(a)
      byPage.set(a.page_index, list)
    }
    const views: PageView[] = []
    for (const meta of docMeta) {
      const page = pageObjsRef.current.get(meta.pageNo)
      // 渲染与命中换算共用同一 viewport 基准（scale = 可用宽 / 页宽）。
      const cssScale = availW / meta.baseW
      const vpCss = page ? page.getViewport({ scale: cssScale }) : null
      const cssH = vpCss ? vpCss.height : meta.baseH * cssScale
      const hits: HitRect[] = []
      const anchorsForPage = byPage.get(meta.pageNo - 1) ?? [] // page_index 0 起
      for (const a of anchorsForPage) {
        // 坐标越界（超出本页 MediaBox 容忍）→ fail closed：丢弃，不渲染可点区。
        if (
          !(
            a.x0 >= 0 &&
            a.y0 >= 0 &&
            a.x1 <= meta.baseW + 0.5 &&
            a.y1 <= meta.baseH + 0.5 &&
            a.x0 <= a.x1 &&
            a.y0 <= a.y1
          )
        ) {
          continue
        }
        if (!vpCss || !page) continue
        // y 自底部向上 → 页面视觉左上角由 (x0, y1) 给出；右下角由 (x1, y0) 给出。
        const tl = vpCss.convertToViewportPoint(a.x0, a.y1)
        const br = vpCss.convertToViewportPoint(a.x1, a.y0)
        const left = tl[0]
        const top = tl[1]
        const width = br[0] - tl[0]
        const height = br[1] - tl[1]
        if (![left, top, width, height].every((v) => Number.isFinite(v) && v >= 0)) continue
        hits.push({ key: pdfAnchorKey(a), left, top, width, height, anchor: a })
      }
      views.push({ pageNo: meta.pageNo, cssW: availW, cssH, hits })
    }
    setPages(views)
  }, [status, docMeta, availW, usableAnchors])

  /* ── 渲染（含 devicePixelRatio 高清）；失败也走「PDF 预览不可用」失败态 ── */
  useEffect(() => {
    if (status !== 'ready' || !pages) return
    const pageViews = pages
    let cancelled = false
    const job = ++drawSeqRef.current
    async function draw() {
      try {
        // 新一轮绘制开始前，先取消上一轮仍在进行的渲染任务并等其 promise settle：
        // cancel() 是同步的（pdf.js 会立即释放该 canvas 的“占用中”标记并停掉 rAF），
        // 但这里仍 await 其 promise 收尾，确保旧任务彻底结束后再复用同一 canvas 重绘。
        // 覆盖路径：可用宽度变化 / 依赖数组变化 / reload / 命中层重算触发的重绘。
        const inflight = [...renderTasksRef.current.values()]
        renderTasksRef.current.clear()
        if (inflight.length > 0) {
          await Promise.all(
            inflight.map(async (task) => {
              try {
                task.cancel()
              } catch {
                // 已完成/已取消，忽略
              }
              try {
                await task.promise
              } catch {
                // RenderingCancelledException —— 主动取消的预期结果
              }
            }),
          )
        }
        if (cancelled || job !== drawSeqRef.current) return
        for (const pv of pageViews) {
          if (cancelled || job !== drawSeqRef.current) return
          const meta = docMeta?.find((m) => m.pageNo === pv.pageNo)
          const page = pageObjsRef.current.get(pv.pageNo)
          const canvas = canvasRefs.current.get(pv.pageNo)
          if (!meta || !page || !canvas) continue
          const dpr = window.devicePixelRatio || 1
          const vp = page.getViewport({ scale: (pv.cssW / meta.baseW) * dpr })
          canvas.width = Math.max(1, Math.floor(vp.width))
          canvas.height = Math.max(1, Math.floor(vp.height))
          canvas.style.width = `${pv.cssW}px`
          canvas.style.height = `${pv.cssH}px`
          const ctx = canvas.getContext('2d')
          if (!ctx) continue
          const renderTask = page.render({ canvasContext: ctx, viewport: vp })
          renderTasksRef.current.set(pv.pageNo, renderTask)
          // 任务结束（成功/被取消）即从登记表移除；用同一引用守卫，
          // 避免把后续新一轮注册的同页任务误删。
          const settle = () => {
            if (renderTasksRef.current.get(pv.pageNo) === renderTask) {
              renderTasksRef.current.delete(pv.pageNo)
            }
          }
          renderTask.promise.then(settle, settle)
          await renderTask.promise
        }
      } catch (e) {
        if (cancelled || job !== drawSeqRef.current) return
        setErrorText(e instanceof Error ? e.message : String(e))
        setStatus('error')
      }
    }
    void draw()
    return () => {
      cancelled = true
      // 依赖变化/卸载：取消仍占用 canvas 的渲染任务，让下一轮可安全复用同一 canvas。
      cancelRenderTasks(false)
    }
    // 依赖保持 [pages, status]：canvas 尺寸/命中层已在 pages 里；其余 ref 读取均为此处最新值。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pages, status])

  useEffect(() => resetDoc, [resetDoc])

  const handleRetry = () => {
    drawSeqRef.current += 1
    setReload((r) => r + 1)
    onRetry?.()
  }

  const handleHitClick = (e: ReactMouseEvent<HTMLButtonElement>, hit: HitRect) => {
    e.stopPropagation()
    if (selectedKey === hit.key) {
      onSelectAnchor?.(null) // 再次点击取消选择
      return
    }
    onSelectAnchor?.(hit.anchor)
  }

  /* ——— 加载态（固定尺寸，外框不跳） ——— */
  if (status === 'loading') {
    return (
      <div className="pdf-preview pdf-preview--state" data-state="loading" role="status" aria-live="polite">
        <div className="pdf-preview__stateblock">
          <span className="pdf-preview__spinner" aria-hidden="true" />
          <span className="pdf-preview__statetitle">正在加载 PDF 成品预览…</span>
          <span className="pdf-preview__statesub">预览与「下载 PDF」读取同一文件</span>
        </div>
      </div>
    )
  }

  /* ——— 失败态：绝不回退 HTML 近似预览 ——— */
  if (status === 'error') {
    return (
      <div className="pdf-preview pdf-preview--state" data-state="error" role="alert">
        <div className="pdf-preview__stateblock">
          <div className="pdf-preview__statetitle">PDF 预览不可用</div>
          <p className="pdf-preview__statesub">{errorText || '无法解析该 PDF。'}</p>
          <div className="pdf-preview__stateactions">
            <Button variant="primary" size="sm" onClick={handleRetry}>
              重试
            </Button>
            {onBackToEdit && (
              <Button variant="secondary" size="sm" onClick={onBackToEdit}>
                返回修改输入
              </Button>
            )}
          </div>
        </div>
      </div>
    )
  }

  /* ——— 就绪态：成品 PDF 页面纵向排列，仅预览卡内容区滚动 ——— */
  return (
    <div className="pdf-preview" data-state="ready">
      <div className="pdf-preview__note" role="note">
        预览即 PDF 成品（与「下载 PDF」为同一文件）；Word 文档在不同软件中打开时可能有轻微排版差异。
      </div>
      {(!docMeta || docMeta.length === 0) && (
        <div className="pdf-preview__note pdf-preview__note--warn">该 PDF 未包含可解析页面。</div>
      )}
      <div className="pdf-preview__pages" ref={scrollAreaRef}>
        {(pages ?? []).map((pv) => (
          <div
            key={pv.pageNo}
            className="pdf-page"
            style={{ width: pv.cssW, height: pv.cssH }}
            onClick={() => onSelectAnchor?.(null)}
            aria-hidden={false}
          >
            <canvas
              ref={(el) => {
                if (el) canvasRefs.current.set(pv.pageNo, el)
                else canvasRefs.current.delete(pv.pageNo)
              }}
              className="pdf-page__canvas"
              role="img"
              aria-label={`PDF 第 ${pv.pageNo} 页`}
            />
            <div className="pdf-page__overlay">
              {pv.hits.map((hit) => {
                const active = selectedKey === hit.key
                return (
                  <button
                    key={hit.key}
                    type="button"
                    className={'pdf-hit' + (active ? ' pdf-hit--selected' : '')}
                    style={{ left: hit.left, top: hit.top, width: hit.width, height: hit.height }}
                    aria-pressed={active}
                    aria-label={hit.anchor.text || `第 ${hit.anchor.page_index + 1} 页内容行`}
                    title={hit.anchor.text}
                    onClick={(e) => handleHitClick(e, hit)}
                  />
                )
              })}
            </div>
          </div>
        ))}
      </div>
      {(!pages || pages.length === 0) && docMeta && docMeta.length > 0 && (
        <div className="pdf-preview__note pdf-preview__note--warn">
          PDF 已加载；正在生成页面…（可用宽度测量中）
        </div>
      )}
    </div>
  )
}
