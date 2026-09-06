/**
 * V2.1.0 Real API 服务实现（普通运行模式的唯一默认实现）。
 *
 * 直接组合既有 typed endpoints（../api/endpoints），不新增请求路径；
 * 只把具体实现绑定到 AppServices 端口。Mock / 设计 fixture 只能存在于
 * 测试或显式隔离的设计环境，不在运行模式自动 fallback —— 本文件不包含
 * 任何 Mock 分支。
 */
import {
  configApi,
  experienceApi,
  jdApi,
  resumeApi,
  systemApi,
  templateApi,
} from '../api/endpoints'
import type { AppServices } from './ports'

export const realServices: AppServices = {
  resume: resumeApi,
  experience: experienceApi,
  jd: jdApi,
  template: templateApi,
  config: configApi,
  system: systemApi,
}
