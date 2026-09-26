/**
 * V2.2.0 Revision 3 返工：用户 artifact 下载 URL 的**唯一权威**构造点。
 *
 * 用户简历 DOCX/PDF 只能通过 task-scoped、owner-scoped 的服务端路由下载：
 *   GET|HEAD /api/task/{task_id}/artifact/{kind}
 * 服务端用「当前 owner + task_id + 已登记的不可变 artifact 引用 + 明确 kind」解析文件；
 * 客户端不再拼接 filename/basename/相对路径（旧 `/api/template/download?path=...` 已收口
 * 为公开模板资产专用，不再服务用户简历）。
 */
export type ArtifactKind = 'docx' | 'pdf'

export function taskArtifactUrl(taskId: string | null | undefined, kind: ArtifactKind): string {
  const t = (taskId || '').trim()
  if (!t) return ''
  return `/api/task/${encodeURIComponent(t)}/artifact/${kind}`
}

/** 下载锚点建议的文件名（仅用于 <a download> 提示，不参与服务端授权）。 */
export function artifactFileName(taskId: string | null | undefined, kind: ArtifactKind): string {
  const t = (taskId || '').slice(0, 8) || 'resume'
  return `resume_${t}.${kind}`
}
