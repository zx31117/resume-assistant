import { useState } from 'react'
import { useWorkbenchTask } from './WorkbenchTaskContext'

/**
 * V2.2.0 T03：步骤 1 身份与 JD 表单（主面板内容）。
 * - name/jd 必填；target 为会话本地可选输入，不发送后端、刷新不持久；
 * - 保存经后端 /api/task PUT 确认后才标「已保存」；失败保留输入；
 * - 主操作（生成岗位简历）固定在主面板 do底部 panel-foot，不随内容漂移；
 * - 校验失败在 role=alert 展示并聚焦出错字段（id = wb-name / wb-jd，供页脚按钮定位）。
 */
export default function StepOneIdentity() {
  const { input, status, saveError, generateError, setInputField, saveNow } = useWorkbenchTask()
  const [target, setTarget] = useState('')

  const editable = status === null || status === 'DRAFT'

  const alertMsg = saveError || generateError

  // 失焦时立即排空待保存内容（与 750ms 防抖互补）
  function flushSave() {
    if (!input.name.trim()) return
    saveNow()
  }

  return (
    <div className="wb-form">
      {alertMsg && (
        <div className="wb-alert" role="alert" aria-live="assertive">
          <svg className="wb-alert__icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v4M12 16h.01" />
          </svg>
          <span className="wb-alert__msg">{alertMsg}</span>
          {saveError && !generateError && (
            <button type="button" className="wb-alert__retry" onClick={saveNow}>
              重试保存
            </button>
          )}
        </div>
      )}

      <section className="wb-form__section">
        <div className="wb-form__section-title">本次身份</div>
        <div className="wb-identity-grid">
          <label className="wb-field">
            <span className="wb-field__label">
              姓名 <span className="wb-field__req">*</span>
            </span>
            <input
              id="wb-name"
              className="wb-input"
              value={input.name}
              onChange={(e) => setInputField('name', e.target.value)}
              onBlur={flushSave}
              readOnly={!editable}
              placeholder="请输入姓名"
              autoComplete="name"
            />
          </label>
          <label className="wb-field">
            <span className="wb-field__label">目标岗位</span>
            <input
              className="wb-input"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              placeholder="如：后端开发实习生"
            />
            <span className="wb-hint">仅本次会话输入；求职意向以 JD 分析为准，不会上传或持久化。</span>
          </label>
        </div>
      </section>

      <section className="wb-form__section">
        <div className="wb-form__section-title">联系方式</div>
        <div className="wb-contact-grid">
          <label className="wb-field">
            <span className="wb-field__label">电话</span>
            <input
              className="wb-input"
              value={input.phone}
              onChange={(e) => setInputField('phone', e.target.value)}
              onBlur={flushSave}
              readOnly={!editable}
              placeholder="可供联系的号码"
              autoComplete="tel"
            />
          </label>
          <label className="wb-field">
            <span className="wb-field__label">邮箱</span>
            <input
              className="wb-input"
              type="email"
              value={input.email}
              onChange={(e) => setInputField('email', e.target.value)}
              onBlur={flushSave}
              readOnly={!editable}
              placeholder="你的联系邮箱"
              autoComplete="email"
            />
          </label>
          <label className="wb-field">
            <span className="wb-field__label">所在地</span>
            <input
              className="wb-input"
              value={input.location}
              onChange={(e) => setInputField('location', e.target.value)}
              onBlur={flushSave}
              readOnly={!editable}
              placeholder="城市"
              autoComplete="address-level2"
            />
          </label>
        </div>
      </section>

      <section className="wb-form__section">
        <div className="wb-form__section-title">目标岗位 JD</div>
        <div className="wb-jd-field">
          <textarea
            id="wb-jd"
            className="wb-textarea"
            value={input.jd}
            maxLength={12000}
            onChange={(e) => setInputField('jd', e.target.value)}
            onBlur={flushSave}
            readOnly={!editable}
            placeholder="职位描述（JD）"
          />
          <div className="wb-jd-count">{input.jd.length} / 12000</div>
        </div>
        <div className="wb-hint">JD 至少 60 字；输入阶段只保存草稿，点击生成后开始理解与匹配。</div>
      </section>

      <div className="wb-step-hint">
        {!editable ? '当前任务已进入生成流程，输入已冻结；请等待处理完成后操作。' : '下拉到底完成填写，页面底部固定「生成岗位简历」按钮。'}
      </div>
    </div>
  )
}