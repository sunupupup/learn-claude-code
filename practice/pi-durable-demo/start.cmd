@echo off
chcp 65001 >nul
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo 请先安装 Node.js 22.19 或以上版本。
  pause
  exit /b 1
)
if not exist "node_modules\@earendil-works\pi-durable\dist\index.js" (
  echo 首次启动：正在安装依赖...
  call npm install --ignore-scripts --no-audit --no-fund
  if errorlevel 1 (
    echo 依赖安装失败，请检查网络后重试。
    pause
    exit /b 1
  )
)
set VIDEO_DEMO_OPEN_BROWSER=1
call npm start
if errorlevel 1 pause
