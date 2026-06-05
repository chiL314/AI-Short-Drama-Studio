@echo off
chcp 65001 >nul
echo ================================
echo AI短剧生成器 - 一键打包工具
echo ================================
echo.

echo [步骤 1/4] 检查PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller未安装，正在安装...
    pip install pyinstaller
    if errorlevel 1 (
        echo ❌ PyInstaller安装失败！
        pause
        exit /b 1
    )
) else (
    echo ✅ PyInstaller已安装
)

echo.
echo [步骤 2/4] 检查FFmpeg...
if not exist "ffmpeg\ffmpeg.exe" if not exist "ffmpeg\bin\ffmpeg.exe" (
    echo ❌ 未找到 ffmpeg.exe（请放到 ffmpeg\ 或 ffmpeg\bin\ 目录下）
    echo 请确保FFmpeg已放置在项目目录
    pause
    exit /b 1
) else (
    echo ✅ FFmpeg已找到
)

echo.
echo [步骤 3/4] 清理旧文件...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "*.spec" del /q "*.spec"
echo ✅ 清理完成

echo.
echo [步骤 4/4] 开始打包（这可能需要几分钟）...
echo.

pyinstaller --name "AI短剧生成器" ^
            --windowed ^
            --add-data "ffmpeg;ffmpeg" ^
            --add-data "resource_pool;resource_pool" ^
            --add-data ".env.example;.env.example" ^
            --hidden-import streamlit ^
            --hidden-import requests ^
            --hidden-import python_dotenv ^
            --clean ^
            app.py

if errorlevel 1 (
    echo.
    echo ❌ 打包失败！请检查错误信息
    pause
    exit /b 1
)

echo.
echo ================================
echo ✅ 打包成功！
echo ================================
echo.
echo 📁 输出目录：dist\AI短剧生成器\
echo.
echo 📦 分发说明：
echo 1. 将 dist\AI短剧生成器\ 整个文件夹打包成zip
echo 2. 用户解压后双击 AI短剧生成器.exe 即可运行
echo 3. 无需安装Python、FFmpeg等任何依赖
echo.
echo ⚠️  注意：
echo - .env文件未打包（包含API密钥）
echo - 用户需要首次运行时配置API密钥
echo.
pause
