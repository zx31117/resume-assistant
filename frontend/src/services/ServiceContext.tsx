/**
 * 服务注入上下文（PLAN §6.3 的依赖入口）。
 *
 * - 应用根部由 <ServicesProvider services={realServices}> 注入 Real API；
 * - 测试 / 设计环境注入同契约的 fakeServices；
 * - useServices 在未提供 provider 时抛错（fail closed），绝不返回
 *   假 service 或静默降级。
 */
import { createContext, useContext } from 'react'
import type { ReactNode } from 'react'
import type { AppServices } from './ports'

export const ServicesContext = createContext<AppServices | null>(null)

export interface ServicesProviderProps {
  services: AppServices
  children: ReactNode
}

export function ServicesProvider({ services, children }: ServicesProviderProps) {
  return <ServicesContext.Provider value={services}>{children}</ServicesContext.Provider>
}

export function useServices(): AppServices {
  const services = useContext(ServicesContext)
  if (!services) {
    throw new Error(
      'ServicesContext 未提供：应用必须由 <ServicesProvider services={...}> 包裹；运行模式注入 realServices。',
    )
  }
  return services
}
