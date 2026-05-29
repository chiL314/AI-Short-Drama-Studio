@echo off
chcp 65001
echo ========================================
echo   🎬 AI短剧自动生成系统
echo ========================================
echo.
echo 正在启动Web界面...
echo.
echo 访问地址: http://localhost:8501
echo.
echo 按 Ctrl+C 可停止服务
echo.
echo ========================================
echo.

cd /d "%~dp0"
streamlit run app.py

pause
