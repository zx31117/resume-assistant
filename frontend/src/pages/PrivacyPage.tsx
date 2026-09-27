import { Link } from 'react-router-dom'
import WbTaskHeading from '../components/layout/WbTaskHeading'

/**
 * V2.2.0 R2-16 返工：个人与隐私——Theme A 页面壳。
 * 只陈述本机 / 第三方边界与已有清理能力，不展示面向开发者的技术卡片。
 * 文案真源：docs/CURRENT_STATE.md 已验收能力。
 */
function Section({ title, children }: { title: string; children: Array<{ t: string; d: string; link?: { to: string; label: string } }> }) {
  return (
    <section className="wb-privacy">
      <h2 className="wb-privacy__title">{title}</h2>
      <ul className="wb-privacy__list">
        {children.map((row) => (
          <li className="wb-privacy__row" key={row.t}>
            <span className="wb-privacy__term">{row.t}</span>
            <span className="wb-privacy__def">
              {row.d}
              {row.link && (
                <span className="wb-privacy__link">
                  <Link to={row.link.to}>{row.link.label} ›</Link>
                </span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}

export default function PrivacyPage() {
  return (
    <div className="wb-subpage">
      <WbTaskHeading
        title="个人与隐私"
        desc="了解本次输入会用在哪里，以及哪些内容由你决定。"
      />
      <div className="wb-panel wb-panel--main">
        <div className="wb-panel__head">
          <div>
            <div className="wb-panel__head-title">本次身份与数据边界</div>
            <div className="wb-panel__head-sub">本地单用户应用 · 本机使用</div>
          </div>
        </div>
        <div className="wb-panel__scroll">
          <Section
            title="数据保存在哪里"
            children={[
              {
                t: '本机应用数据目录',
                d: '职业经历、向量索引与运行记录保存在本机 SQLite；诊断日志为同目录脱敏 JSONL。数据目录位于本机应用数据区（Windows 默认为 %LOCALAPPDATA%\ResumeAssistant），仅本机可访问。',
              },
              {
                t: '生成输出',
                d: '生成的 DOCX / PDF 写入本机数据目录的输出子目录，下载链接指向该本机文件；应用不把文件上传到任何云端。',
              },
              {
                t: '账号与云端',
                d: '当前版本无账号体系，不登录、不云同步、不提供云端副本；卸载或删除数据目录前，本机数据不会在其他位置留存。',
              },
            ]}
          />
          <Section
            title="第三方模型调用边界"
            children={[
              {
                t: '调用范围',
                d: 'JD 分析、文本经历提取、受约束改写与 Embedding 数值生成会按配置的 Provider 发送完成任务所需的文本；向量相似度计算在本机内存完成。',
              },
              {
                t: '发送哪些内容',
                d: '改写只使用本次被选中的经历事实与当前 JD；未选中、未提交或与本次请求无关的内容不会发出。',
              },
              {
                t: '配置可见性',
                d: 'Provider 地址、模型名与 Key 只在隐藏的「开发者后台」管理与脱敏展示；普通界面不出现配置项，也不会显示完整 Key。',
              },
            ]}
          />
          <Section
            title="缺失信息如何处理"
            children={[
              {
                t: '阻断 · 无法正确完成时停下',
                d: '姓名缺失、没有任何经历、JD 过短或解析不到目标岗位、数据库或索引未就绪时，生成前会给出原因并阻止提交。',
              },
              {
                t: '排除并说明 · 局部材料不符合规则',
                d: '工作/实习只取日期可解析的最近至多 3 段；项目/论文取基准日前 3 年内至多 2 项。超出时限的条目会被排除并说明，不足数量不补造。',
              },
              {
                t: '留空不编造 · 缺失字段',
                d: '电话、邮箱、所在地等缺失时留空，不从数据库、模板或经历库回填；AI 只做受事实约束的表达改写，不写回事实库。',
              },
            ]}
          />
          <Section
            title="删除与清理：真实路径"
            children={[
              {
                t: '清空当前未运行草稿',
                d: '在工作台顶栏，「＋ 开始新任务」会丢弃当前未生成（DRAFT / 已取消）任务的本地草稿输入，并准备全新任务；不触碰已生成的经历库或历史成品。该入口只出现在工作台；在「我的经历 / 我的简历 / 个人与隐私」等页面顶栏只提供「← 返回工作台」，返回不会新建任务、不会清空当前任务，也不产生任何模型调用。',
                link: { to: '/', label: '去工作台' },
              },
              {
                t: '删除一段经历',
                d: '在「我的经历」对单条经历点「删除」并确认后，该经历及其事实、派生向量与引用一并清理且不可恢复；失败会明确提示。',
                link: { to: '/experiences', label: '去删除' },
              },
              {
                t: '清理诊断日志',
                d: '脱敏诊断日志保留在本机数据目录的 diagnostics 子目录，最多 7 天且受大小上限约束，会自动轮转；也可在「开发者后台」手动清理。',
                link: { to: '/system', label: '去开发者后台' },
              },
            ]}
          />
        </div>
      </div>
    </div>
  )
}
