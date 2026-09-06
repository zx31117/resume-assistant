import PageHeader from '../components/PageHeader'
import Card from '../components/ui/Card'

/**
 * V2.1.0 个人与隐私（T3 基础版，T7 将按 DS-002 精修信息架构与文案）。
 * 只陈述已验收的产品事实（见 docs/CURRENT_STATE.md 数据与基础设施），
 * 不虚构任何未支持的能力。
 */
export default function PrivacyPage() {
  return (
    <div className="page">
      <PageHeader
        title="个人与隐私"
        description="你的职业经历与简历输出在哪些设备处理、如何保存、如何删除。"
      />

      <Card title="数据保存在哪里" subtitle="本应用是本地单用户应用，不登录、不云端同步。">
        <ul className="next-steps">
          <li>职业经历库（Experience / Fact）与检索索引保存在本机 runtime data root 的 SQLite 数据库中。</li>
          <li>生成的 DOCX 输出到本机输出目录；PDF 上传与解析在本机完成，不保留中间文件副本。</li>
          <li>长期模型 API Key 使用系统凭据库保存（Windows Credential Manager），不以明文写入项目目录。</li>
        </ul>
      </Card>

      <Card title="第三方模型调用" subtitle="内容生成依赖你配置的模型服务。">
        <ul className="next-steps">
          <li>JD 分析、经历提取与受约束改写调用你配置的 LLM；向量计算在内存使用 numpy 完成，模型仅提供 Embedding 数值。</li>
          <li>提交给模型的文本按你的配置发送到对应服务；不发送未选中的经历或超出本次请求的事实。</li>
          <li>Provider 地址、模型名与 Key 仅在「开发者后台」管理与脱敏展示，不在普通导航中出现。</li>
        </ul>
      </Card>

      <Card title="删除与清理边界" subtitle="删除是明确动作，不会静默发生。">
        <ul className="next-steps">
          <li>在「我的经历」删除一条经历会同时失效其派生向量与事实引用，失败时页面明确提示。</li>
          <li>诊断日志（脱敏 JSONL）在 runtime data root 的 diagnostics 目录，最多保留 7 天且受大小上限约束，可在开发者后台清理。</li>
          <li>卸载或删除数据目录后本机数据即不可恢复；本项目不提供云端副本。</li>
        </ul>
      </Card>
    </div>
  )
}
