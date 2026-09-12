import type { DocPreviewSection } from '../api/types'

/**
 * ⚠ V2.1.0 R15b：已退出产品路径（死代码，保留仅作历史参考；不得再被引用）。
 * 结果页「内容预览」已由 components/PdfPreview.tsx（真实 PDF 成品 + 命中层）取代；
 * GeneratePage result 不再用本组件做版式渲染，doc_preview JSON 也不再承担版式渲染。

 * 历史职责（V2.1.0 T12-R10）：结果页内容预览（按 pm_template v1.2 忠实视觉）。
 * - 视觉真源 = backend/templates/pm_template.json（v1.2），禁止通用纸张排版；
 * - 预览内容直接铺在预览卡内容区，不再维护 720×1018 二级纸张与 transform: scale 缩放；
 * - 字号/行高/分隔线/条目行/bullet 规则全部映射 pm_template v1.2：
 *     姓名 20pt · 节标题 12pt · 条目 10.6pt · bullet 10pt 常规；
 *     节标题底分隔线 · ●/⚫ bullet 常规不加粗 · 经历行 = 名称/机构说明 与 日期右对齐；
 *     右上角照片占位框（空框） · profile 区不渲染「个人信息」普通章节卡片；
 * - 依据 onSelect 仅作为不改变排版尺寸的背景状态（圆角浅底 + padding，不挤压文本/换行）；
 * - 暴露 SelectedBullet 给上层做「逐条依据」联动；键盘可达（role=button / tabIndex / aria-pressed）。
 */

export interface SelectedBullet {
  sectionIdx: number
  entryIdx: number
  bulletIdx: number
}

interface Props {
  sections: DocPreviewSection[] | null
  selected: SelectedBullet | null
  onSelect: (s: SelectedBullet) => void
}

/** 把 "A · B · C" 切成 [A, B, C]，用于把 doc_preview entry.heading 拆成模板三列所需的字段。
 *  模板约定：work/project heading = "公司/项目 · 角色"，education = "学校 · 专业"。
 *  无分隔符时整串作为第一项，避免错把整段塞进居中列。 */
function splitHeading(heading: string): string[] {
  if (!heading) return ['']
  const parts = heading.split(' · ')
  return parts.length > 1 ? parts : [heading]
}

/** bullet 是否处于选中态。 */
function isSelectedBullet(
  selected: SelectedBullet | null,
  sIdx: number,
  eIdx: number,
  bIdx: number,
): boolean {
  return (
    selected != null &&
    selected.sectionIdx === sIdx &&
    selected.entryIdx === eIdx &&
    selected.bulletIdx === bIdx
  )
}

/** 解析个人 bullet 的语义前缀：目标岗位 / 所在地 / 自我评价 / 等。 */
const PROFILE_PREFIXES = ['目标岗位：', '所在地：', '自我评价：'] as const
type ProfilePrefix = (typeof PROFILE_PREFIXES)[number]

function stripProfilePrefix(text: string): { prefix: ProfilePrefix | null; rest: string } {
  for (const p of PROFILE_PREFIXES) {
    if (text.startsWith(p)) return { prefix: p, rest: text.slice(p.length) }
  }
  return { prefix: null, rest: text }
}

export default function ResultPaperPreview({ sections, selected, onSelect }: Props) {
  if (!sections || sections.length === 0) {
    return (
      <div className="pm-paper__empty">
        <div className="empty__title">本次响应未携带内容预览</div>
        <div className="empty__desc">可直接下载下方 DOCX / PDF；预览依赖 V2.1.0 T6 字段。</div>
      </div>
    )
  }

  // personal 段单独走 header 渲染（不放进节列表），与模板「姓名 + 联系行 + 照片框」一致；
  // 后端已按 pm_template v1.2 顺序排序（personal→education→work→project→skills→awards）。
  const personalIdx = sections.findIndex((s) => s.section === 'personal')
  const personal = personalIdx >= 0 ? sections[personalIdx] : null
  const restSections = sections.filter((s) => s.section !== 'personal')

  // 重新计算 sectionIdx：restSections 里的下标用于 selected.sectionIdx 解析。
  const remap = new Map<number, number>()
  restSections.forEach((sec, i) => {
    const originalIdx = sections.findIndex((s) => s === sec)
    if (originalIdx >= 0) remap.set(originalIdx, i)
  })

  return (
    <article className="pm-paper" aria-label="简历内容预览">
      {/* 右上角照片占位框（空框）。absolute 定位不挤压文本流，不影响换行。 */}
      <div className="pm-photo" aria-hidden="true" />

      {personal && personal.entries.length > 0 && (
        <ProfileHeader
          entry={personal.entries[0]!}
          personalIndex={personalIdx}
          selected={selected}
          onSelect={onSelect}
        />
      )}

      {restSections.map((sec, sIdx) => {
        const originalIdx = sections.findIndex((s) => s === sec)
        return (
          <section key={`${sec.section}-${originalIdx}`} className="pm-section">
            <SectionTitle title={displayTitle(sec.section)} />
            {sec.entries.length === 0 ? null : (
              <div className="pm-section__entries">
                {sec.entries.map((ent, eIdx) => (
                  <PreviewEntry
                    key={`${originalIdx}-${eIdx}`}
                    sectionKind={sec.section}
                    entry={ent}
                    sIdx={sIdx}
                    eIdx={eIdx}
                    selected={selected}
                    onSelect={onSelect}
                  />
                ))}
              </div>
            )}
          </section>
        )
      })}
    </article>
  )
}

/* ───────────────────────── Profile 头部 ───────────────────────── */

function ProfileHeader({
  entry,
  personalIndex,
  selected,
  onSelect,
}: {
  entry: import('../api/types').DocPreviewEntry
  personalIndex: number
  selected: SelectedBullet | null
  onSelect: (s: SelectedBullet) => void
}) {
  const name = entry.heading || '（未署名）'
  const contact = entry.subhead || ''
  // profile 区 bullets（目标岗位 / 所在地 / 自我评价）按行渲染，无 bullet 前缀。
  return (
    <header className="pm-header">
      <div className="pm-header__name">{name}</div>
      {contact && <div className="pm-header__contact">{contact}</div>}
      {entry.bullets.length > 0 && (
        <div className="pm-header__lines">
          {entry.bullets.map((b, bIdx) => {
            const isSelected = isSelectedBullet(selected, personalIndex, 0, bIdx)
            const { prefix, rest } = stripProfilePrefix(b)
            return (
              <div
                key={`p-${bIdx}`}
                className={
                  'pm-header__line' + (isSelected ? ' pm-bullet pm-bullet--selected' : '')
                }
                onClick={() => onSelect({ sectionIdx: personalIndex, entryIdx: 0, bulletIdx: bIdx })}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    onSelect({ sectionIdx: personalIndex, entryIdx: 0, bulletIdx: bIdx })
                  }
                }}
                role="button"
                tabIndex={0}
                aria-pressed={isSelected}
                aria-label={b}
              >
                {prefix ? (
                  <>
                    <span className="pm-header__line-prefix">{prefix}</span>
                    <span>{rest}</span>
                  </>
                ) : (
                  <span>{b}</span>
                )}
              </div>
            )
          })}
        </div>
      )}
    </header>
  )
}

/* ───────────────────────── 节标题 ───────────────────────── */

function SectionTitle({ title }: { title: string }) {
  return <h2 className="pm-section__title">{title}</h2>
}

/** doc_preview section 名 → pm_template v1.2 章节显示标题（与 docx/pdf 同源）。
 *  仅维护这一组常量，避免通用纸张排版的同时保留模板视觉真源。 */
function displayTitle(section: string): string {
  switch (section) {
    case 'education':
      return '教育背景'
    case 'work':
      return '实习经历'
    case 'project':
      return '项目经历'
    case 'skills':
      return '技能专长'
    case 'awards':
      return '荣誉奖项'
    case 'summary':
      return '自我评价'
    case 'personal':
      // 不应当以普通章节卡片出现；保留兜底。
      return '个人信息'
    default:
      return section
  }
}

/* ───────────────────────── 条目渲染 ───────────────────────── */

function PreviewEntry({
  sectionKind,
  entry,
  sIdx,
  eIdx,
  selected,
  onSelect,
}: {
  sectionKind: string
  entry: import('../api/types').DocPreviewEntry
  sIdx: number
  eIdx: number
  selected: SelectedBullet | null
  onSelect: (s: SelectedBullet) => void
}) {
  // skills / awards 走专用渲染
  if (sectionKind === 'skills') {
    return <SkillEntry heading={entry.heading} items={entry.bullets} />
  }
  if (sectionKind === 'awards') {
    return (
      <div className="pm-entry pm-entry--awards">
        {entry.bullets.length > 0 ? (
          <ul className="pm-bullets">
            {entry.bullets.map((b, bIdx) => {
              const isSelected = isSelectedBullet(selected, sIdx, eIdx, bIdx)
              return (
                <li
                  key={bIdx}
                  className={'pm-bullet' + (isSelected ? ' pm-bullet--selected' : '')}
                  onClick={() => onSelect({ sectionIdx: sIdx, entryIdx: eIdx, bulletIdx: bIdx })}
                  onKeyDown={(ev) => {
                    if (ev.key === 'Enter' || ev.key === ' ') {
                      ev.preventDefault()
                      onSelect({ sectionIdx: sIdx, entryIdx: eIdx, bulletIdx: bIdx })
                    }
                  }}
                  role="button"
                  tabIndex={0}
                  aria-pressed={isSelected}
                >
                  {b}
                </li>
              )
            })}
          </ul>
        ) : null}
      </div>
    )
  }

  // 经历行（work / project / education）：名称/机构说明 左 · 日期 右对齐
  const parts = splitHeading(entry.heading)
  const primary = parts[0] ?? ''
  const secondary = parts.length > 1 ? parts.slice(1).join(' · ') : ''
  const dateText = entry.subhead || ''

  return (
    <div className="pm-entry">
      {(primary || dateText) && (
        <div className="pm-entry__title-row">
          <span className="pm-entry__title">
            {primary}
            {secondary && <span className="pm-entry__sub"> · {secondary}</span>}
          </span>
          {dateText && <span className="pm-entry__date">{dateText}</span>}
        </div>
      )}
      {entry.bullets.length > 0 && (
        <ul className="pm-bullets">
          {entry.bullets.map((b, bIdx) => {
            const isSelected = isSelectedBullet(selected, sIdx, eIdx, bIdx)
            return (
              <li
                key={bIdx}
                className={'pm-bullet' + (isSelected ? ' pm-bullet--selected' : '')}
                onClick={() => onSelect({ sectionIdx: sIdx, entryIdx: eIdx, bulletIdx: bIdx })}
                onKeyDown={(ev) => {
                  if (ev.key === 'Enter' || ev.key === ' ') {
                    ev.preventDefault()
                    onSelect({ sectionIdx: sIdx, entryIdx: eIdx, bulletIdx: bIdx })
                  }
                }}
                role="button"
                tabIndex={0}
                aria-pressed={isSelected}
              >
                {b}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

/* ───────────────────────── 技能行 ───────────────────────── */

function SkillEntry({ heading, items }: { heading: string; items: string[] }) {
  if (items.length === 0 && !heading) return null
  return (
    <div className="pm-entry pm-entry--skill">
      <span className="pm-skill__line">
        {heading && <span className="pm-skill__category">{heading}：</span>}
        <span className="pm-skill__items">{items.join(' · ')}</span>
      </span>
    </div>
  )
}
