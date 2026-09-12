/**
 * H5 R26：Hooks 顺序门禁专用 ESLint 配置。
 *
 * 只启一条规则 `react-hooks/rules-of-hooks`（error），关闭该插件其余规则与
 * 其它规则集 —— 使「产品源码存在 rules-of-hooks 违规」成为可被 CI/precheck 单独
 * 阻断的信号，而不受 `set-state-in-effect / purity / exhaustive-deps` 等既有
 * 风格性问题的噪声干扰（完整 lint 见 eslint.config.js，仍为非阻断报告项）。
 *
 * 用法：eslint -c eslint.rules-of-hooks.config.js src
 */
import reactHooks from 'eslint-plugin-react-hooks'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  {
    ignores: [
      'dist',
      'node_modules',
      '*.tsbuildinfo',
      'vite.config.js',
      'vite.config.d.ts',
    ],
  },
  {
    linterOptions: {
      // 本门禁只关心 rules-of-hooks；exhaustive-deps 已关闭时源码里既有
      // eslint-disable 注释会被 ESLint 报告为“unused disable”，属噪声，不显示。
      reportUnusedDisableDirectives: 'off',
    },
  },
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: {
        ecmaVersion: 'latest',
        sourceType: 'module',
      },
    },
    plugins: {
      'react-hooks': reactHooks,
    },
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'off',
    },
  },
)
