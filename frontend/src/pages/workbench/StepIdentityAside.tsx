import { Link } from 'react-router-dom'

/**
 * V2.2.0 T03/T04：步骤 1（身份与 JD）右侧说明卡，对应冻结 DS-003 `inputAside()`。
 * 信息层级：intro（eyebrow + big heading + 说明）→ 2/3/4 步导读 → 真实经历提示。
 * 不编造经历数量；使用真实提示与本机数据边界语义。
 */
export default function StepIdentityAside() {
  const guide: Array<{ n: string; title: string; body: string }> = [
    { n: '2', title: '理解岗位', body: '梳理岗位职责、要求和加分项。' },
    { n: '3', title: '匹配经历', body: '从真实经历中找到有依据的内容。' },
    { n: '4', title: '修改与下载', body: '润色、检查详情并导出文件。' },
  ]
  return (
    <>
      <div className="wb-panel__head">
        <div>
          <div className="wb-panel__head-title">从真实经历开始</div>
          <div className="wb-panel__head-sub">本次任务</div>
        </div>
      </div>
      <div className="wb-panel__scroll">
        <div className="wb-aside-intro">
          <div className="wb-aside-eyebrow">少一点准备，多一点进展</div>
          <h3 className="wb-aside-title">
            写下目标，
            <br />
            剩下的交给我们。
          </h3>
          <p className="wb-aside-desc">提供真实经历和目标岗位，系统完成选材、表达与排版。</p>
        </div>
        <div className="wb-aside-guide">
          {guide.map((g) => (
            <div className="wb-aside-guide__row" key={g.n}>
              <span className="wb-aside-guide__num" aria-hidden="true">
                {g.n}
              </span>
              <div>
                <div className="wb-aside-guide__title">{g.title}</div>
                <p className="wb-aside-guide__body">{g.body}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="wb-aside-note">
          <strong>只使用已确认的经历事实</strong>
          <p>不需要每次重新整理。发现遗漏时，再到「我的经历」补充相关事实。</p>
        </div>
      </div>
      <div className="wb-panel__foot">
        <span className="wb-aside-foottext">本次身份只用于当前生成任务。</span>
        <Link className="wb-btn wb-btn--ghost wb-btn--sm" to="/privacy">
          隐私说明
        </Link>
      </div>
    </>
  )
}