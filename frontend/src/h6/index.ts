/**
 * V2.1.0 H6 test-only：四区域 render-exception 注入辅助（PLAN §18.2.3）。
 *
 * - 只用于可移交测试环境（R29 dev/production test build 全矩阵）。
 * - 触发条件来自构建期常量 __H6_INJECT__（vite define，读 VITE_H6_INJECT，默认 null）。
 *   正式生产构建不设该 env → 常量替换为 null → `if (null === target)` 恒 false →
 *   throw 为不可达代码，被压缩器消除；正式产物不包含注入入口。
 * - 不在任何正式路由/UI 暴露开关，不读取本地配置，无副作用。
 */

export type H6Target = 'pdf' | 'overlay' | 'basis' | 'export'

declare const __H6_INJECT__: H6Target | null

export function maybeInjectH6(target: H6Target): void {
  // import.meta.env.DEV 在生产构建被替换为 false → 与 null 判断一起被压缩器作为不可达
  // 死代码删除，正式产物不含注入入口与测试字符串（PLAN §18.2.3/§18.3）。
  if (import.meta.env.DEV && __H6_INJECT__ === target) {
    // eslint-disable-next-line no-throw-literal
    throw new Error('H6-inject:' + target)
  }
}
