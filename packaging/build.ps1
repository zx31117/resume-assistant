# V2.0.0 便携包构建脚本（PLAN §3.4 / §6 T7）
#
# 前置：本机已安装 Python 3.10+ 与 Node.js（npm）。
# 产物：packaging/dist/ResumeAssistant/（onedir 目录型便携包）
#       packaging/ResumeAssistant.spec
#
# 步骤：
#   1. 构建前端生产产物（frontend/dist）
#   2. 确保 pyinstaller 可用（缺失则 pip 安装到当前 Python）
#   3. 以 resume_assistant.spec 执行 onedir 打包（--noconfirm --clean）
#   4. 输出产物路径与简要校验（入口 exe、frontend/dist、templates、config 是否就位）
#
# 说明：本脚本不打包 .env / API Key / 数据库 / 输出 / 缓存；runtime 数据根在
#       %LOCALAPPDATA%/ResumeAssistant（源码与便携目录外），移动/删除包不影响用户数据。

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot   # repo root
$Frontend = Join-Path $Root "frontend"
$Packaging = Join-Path $Root "packaging"

Write-Host "==> [1/3] 构建前端生产产物" -ForegroundColor Cyan
Push-Location $Frontend
try {
    npm install --no-audit --no-fund | Out-Null
    npm run build
    if (-not (Test-Path (Join-Path $Frontend "dist\index.html"))) {
        throw "前端构建失败：frontend/dist/index.html 不存在"
    }
} finally {
    Pop-Location
}

Write-Host "==> [2/3] 确保 pyinstaller" -ForegroundColor Cyan
$pyi = Get-Command pyinstaller -ErrorAction SilentlyContinue
if (-not $pyi) {
    Write-Host "    pyinstaller 缺失，执行 pip install pyinstaller ..."
    python -m pip install pyinstaller
}

Write-Host "==> [3/3] PyInstaller onedir 打包" -ForegroundColor Cyan
Push-Location $Root
try {
    python -m PyInstaller --noconfirm --clean (Join-Path $Packaging "resume_assistant.spec")
} finally {
    Pop-Location
}

$OutDir = Join-Path $Root "dist\ResumeAssistant"
Write-Host ""
Write-Host "==> 产物目录：$OutDir" -ForegroundColor Green
$checks = @(
    @{ Name = "入口 exe";         Path = (Join-Path $OutDir "ResumeAssistant.exe") },
    @{ Name = "前端 index.html";  Path = (Join-Path $OutDir "_internal\frontend\dist\index.html") },
    @{ Name = "模板 pm_template"; Path = (Join-Path $OutDir "_internal\templates\pm_template.docx") },
    @{ Name = "配置映射";         Path = (Join-Path $OutDir "_internal\config\template_mapping.json") }
)
foreach ($c in $checks) {
    $ok = Test-Path $c.Path
    $mark = if ($ok) { "[OK]" } else { "[MISS]" }
    Write-Host ("    {0} {1}" -f $mark, $c.Name)
    if (-not $ok) { $ErrorActionPreference = "Continue"; throw ("缺少产物: " + $c.Path) }
}

Write-Host ""
Write-Host "构建完成。可在干净 Windows x64 环境双击 ResumeAssistant\\ResumeAssistant.exe 启动。" -ForegroundColor Green