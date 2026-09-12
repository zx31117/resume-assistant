import { Link } from 'react-router-dom'
import PageHeader from '../components/PageHeader'
import Badge from '../components/ui/Badge'
import Card from '../components/ui/Card'

/**
 * V2.1.0 个人与隐私（T7 精修，按 DS-002 信息架构）。
 *
 * 只陈述 docs/CURRENT_STATE.md 中已验收的真实能力，边界如实标注：
 * - 数据保存位置：本机 SQLite / runtime 数据目录 / 输出目录 / 系统凭据库；
 * - 第三方模型调用边界与缺失信息处理均以真实规则为准，不编造等级承诺；
 * - 删除与清理只给真实可执行路径（逐条删除经历、开发者后台清理诊断日志、
 *   删除数据目录）；后端没有清空业务数据的 API，故不提供「一键清空」按钮。
 */
export default function PrivacyPage() {
  return (
    <div className="page">
      <PageHeader
        title="个人与隐私"
        description="数据边界、可见性与你的权利：数据保存在哪里、缺失信息如何处理、如何真正删除。"
      />

      {/* T12-R12：页头固定；长文多卡在单一滚动宿主内（页面壳层零滚动） */}
      <div className="page-scroll privacy-cards">
      <Card title="数据保存在哪里" subtitle="本地单用户应用：不登录、不账号体系、不上传云端。">
        <ul className="privacy-list">
          <li className="privacy-row">
            <span className="privacy-row__title">本机应用数据目录</span>
            <span className="privacy-row__desc">
              职业经历（Experience / Fact）、向量索引与运行记录保存在本机 SQLite
              数据库中；诊断日志为同目录下的脱敏 JSONL。数据目录位于本机应用数据区（Windows
              默认为 <code>%LOCALAPPDATA%\ResumeAssistant</code>），仅本机可访问。
            </span>
          </li>
          <li className="privacy-row">
            <span className="privacy-row__title">生成输出</span>
            <span className="privacy-row__desc">
              生成的 DOCX 写入本机数据目录的输出子目录，下载链接指向该本机文件；应用不把文件上传到任何云端。
            </span>
          </li>
          <li className="privacy-row">
            <span className="privacy-row__title">PDF 与中间文本</span>
            <span className="privacy-row__desc">
              上传的 PDF 在本机解析为文本后用于提取，不保留中间文件副本；提取条目需经确认后写入经历库。
            </span>
          </li>
          <li className="privacy-row">
            <span className="privacy-row__title">凭据保存</span>
            <span className="privacy-row__desc">
              长期模型 API Key 使用系统凭据库保存（Windows Credential
              Manager），不以明文写入项目目录或浏览器存储；非密钥配置保存在本机 runtime 配置中。
            </span>
          </li>
          <li className="privacy-row">
            <span className="privacy-row__title">账号与云端</span>
            <span className="privacy-row__desc">
              当前版本无账号体系，不登录、不云同步、不提供云端副本；卸载或删除数据目录前，本机数据不会在其他位置留存。
            </span>
          </li>
        </ul>
      </Card>

      <Card title="第三方模型调用边界" subtitle="完成任务所需的文本会发送给你配置的模型服务；边界如下。">
        <ul className="privacy-list">
          <li className="privacy-row">
            <span className="privacy-row__title">调用范围</span>
            <span className="privacy-row__desc">
              JD 分析、PDF/文本经历提取、受约束改写与 Embedding
              数值生成会按你在「开发者后台」配置的 Provider 发送完成任务所需的文本；向量相似度计算在本机内存完成。
            </span>
          </li>
          <li className="privacy-row">
            <span className="privacy-row__title">发送哪些内容</span>
            <span className="privacy-row__desc">
              改写只使用本次被选中的经历事实与当前 JD；未选中、未提交或与本次请求无关的内容不会发出。
            </span>
          </li>
          <li className="privacy-row">
            <span className="privacy-row__title">失败与兜底</span>
            <span className="privacy-row__desc">
              关键结构化阶段采用 strict failure：失败时返回明确领域错误并阻断生成，不会退化为空成功或「全部事实」式兜底。
            </span>
          </li>
          <li className="privacy-row">
            <span className="privacy-row__title">配置可见性</span>
            <span className="privacy-row__desc">
              Provider 地址、模型名与 Key 只在隐藏的「开发者后台」管理与脱敏展示；普通界面不出现配置项，也不会显示完整 Key。
            </span>
          </li>
        </ul>
      </Card>

      <Card title="缺失信息如何处理" subtitle="不因某项缺失就拒绝完成，但也绝不替你编造事实。">
        <ul className="privacy-list">
          <li className="privacy-row">
            <span className="privacy-row__title">阻断 · 无法正确完成时停下</span>
            <span className="privacy-row__desc">
              界面可真实判定的硬阻断：姓名缺失（无法署名）、没有任何经历（没有可选事实）、JD
              过短或解析不到目标岗位、数据库或索引未就绪——生成前检查会给出原因并阻止提交。
            </span>
          </li>
          <li className="privacy-row">
            <span className="privacy-row__title">排除并说明 · 局部材料不符合规则</span>
            <span className="privacy-row__desc">
              工作/实习只取日期可解析的最近至多 3 段；项目/论文取生成基准日前 3 年内的至多 2
              项。日期缺失、不可解析或超出时限的条目会被排除并在结果中说明，不足数量不补造。
            </span>
          </li>
          <li className="privacy-row">
            <span className="privacy-row__title">需确认 · 仅处理推断与补全项</span>
            <span className="privacy-row__desc">
              PDF 提取中「有原文直接支撑」的条目可自动整理入库；AI 推断或补全的条目进入「需确认」列表，逐条核对原文后再保存。
            </span>
          </li>
          <li className="privacy-row">
            <span className="privacy-row__title">留空不编造 · 缺失字段</span>
            <span className="privacy-row__desc">
              电话、邮箱、所在地等缺失时留空，不从数据库、模板或经历库回填；AI
              只做受事实约束的表达改写，不写回事实库。
            </span>
          </li>
        </ul>
      </Card>

      <Card title="你能看到的可靠性（分三层）" subtitle="可靠感来自真实的信息边界，而不是虚构百分比或「AI 思考」文案。">
        <div>
          <div className="reliability-layer">
            <div className="reliability-layer__head">
              <Badge tone="ok">第 1 层</Badge>
              <span className="reliability-layer__title">默认可见</span>
            </div>
            <div className="reliability-layer__items">
              <span className="tag">当前真实阶段</span>
              <span className="tag">已用时间</span>
              <span className="tag">输入是否保留</span>
              <span className="tag">材料缺口与下一步</span>
            </div>
          </div>
          <div className="reliability-layer">
            <div className="reliability-layer__head">
              <Badge tone="accent">第 2 层</Badge>
              <span className="reliability-layer__title">按需展开</span>
            </div>
            <div className="reliability-layer__items">
              <span className="tag">每条 bullet 的真实事实原文</span>
              <span className="tag">所属经历</span>
              <span className="tag">本次结果统计与告警</span>
            </div>
          </div>
          <div className="reliability-layer">
            <div className="reliability-layer__head">
              <Badge tone="neutral">第 3 层</Badge>
              <span className="reliability-layer__title">隐藏开发者后台</span>
            </div>
            <div className="reliability-layer__items">
              <span className="tag">Provider / 模型配置</span>
              <span className="tag">连接测试</span>
              <span className="tag">运行活动与阶段明细</span>
              <span className="tag">脱敏诊断摘要与后台日志</span>
            </div>
          </div>
        </div>
      </Card>

      <Card title="删除与清理：真实路径" subtitle="删除都是明确动作、完成后不可恢复；后端没有清空业务数据的 API，因此没有「一键清空」按钮。">
        <ul className="privacy-list">
          <li className="privacy-row">
            <span className="privacy-row__title">删除一段经历</span>
            <span className="privacy-row__desc">
              在「我的经历」对单条经历点「删除」并确认后，该经历及其事实、派生向量与引用一并清理且不可恢复；失败会明确提示。
              <span className="privacy-actions" style={{ marginTop: 'var(--s2)' }}>
                <Link to="/profile">去「我的经历」删除 ›</Link>
              </span>
            </span>
          </li>
          <li className="privacy-row">
            <span className="privacy-row__title">清理诊断日志</span>
            <span className="privacy-row__desc">
              脱敏诊断日志保留在本机数据目录的 diagnostics 子目录，最多保留 7 天且受大小上限约束，会自动轮转；也可在「开发者后台」手动「清理日志」，立即清空历史日志而不影响任何业务数据。
              <span className="privacy-actions" style={{ marginTop: 'var(--s2)' }}>
                <Link to="/system">去开发者后台清理 ›</Link>
              </span>
            </span>
          </li>
          <li className="privacy-row">
            <span className="privacy-row__title">清空全部业务数据</span>
            <span className="privacy-row__desc">
              需要从零开始时，请逐条删除经历，或停止应用后删除整个数据目录再重新启动（全新数据库会按空库自动初始化）。
            </span>
          </li>
          <li className="privacy-row">
            <span className="privacy-row__title">卸载与残留</span>
            <span className="privacy-row__desc">
              应用本体是本地程序目录，卸载或删除程序不会自动清除上面的数据目录；如需彻底移除本机数据，请在删除程序后手动删除数据目录。
            </span>
          </li>
        </ul>
      </Card>
      </div>
    </div>
  )
}
