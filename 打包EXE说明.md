# 项目打包成EXE说明

## ✅ 已完成配置

### 1. FFmpeg已集成到项目
- ✅ FFmpeg位置：`项目目录/ffmpeg/bin/ffmpeg.exe`
- ✅ 代码已配置为优先使用项目自带的FFmpeg
- ✅ 打包后其他电脑无需安装FFmpeg

### 2. 自动查找FFmpeg逻辑
```python
# audio_processor.py 中的逻辑
def get_ffmpeg_path():
    # 1. 优先使用项目自带的FFmpeg
    project_ffmpeg = os.path.join(os.path.dirname(__file__), "ffmpeg", "bin", "ffmpeg.exe")
    if os.path.exists(project_ffmpeg):
        return project_ffmpeg
    # 2. 如果项目内没有，尝试使用系统PATH中的
    return "ffmpeg"
```

---

## 📦 打包步骤

### 方法一：使用PyInstaller（推荐）

#### 1. 安装PyInstaller
```bash
pip install pyinstaller
```

#### 2. 打包命令
```bash
pyinstaller --name "AI短剧生成器" ^
            --windowed ^
            --add-data "ffmpeg;ffmpeg" ^
            --add-data "resource_pool;resource_pool" ^
            --add-data ".env;.env" ^
            --hidden-import streamlit ^
            --hidden-import requests ^
            app.py
```

**参数说明**：
- `--name`: 生成的exe名称
- `--windowed`: 不显示控制台窗口
- `--add-data "ffmpeg;ffmpeg"`: 将ffmpeg文件夹打包进去（Windows用`;`分隔）
- `--add-data "resource_pool;resource_pool"`: 打包资源池
- `--hidden-import`: 确保依赖被包含

#### 3. 生成的文件
打包完成后，在`dist/AI短剧生成器/`目录下会有：
```
AI短剧生成器/
├── AI短剧生成器.exe      # 主程序
├── ffmpeg/               # FFmpeg完整目录
│   └── bin/
│       └── ffmpeg.exe
├── resource_pool/        # 资源池
└── _internal/            # Python依赖
```

---

### 方法二：使用Nuitka（性能更好）

#### 1. 安装Nuitka
```bash
pip install nuitka
```

#### 2. 打包命令
```bash
python -m nuitka --standalone ^
                 --windows-disable-console ^
                 --include-data-dir=ffmpeg=ffmpeg ^
                 --include-data-dir=resource_pool=resource_pool ^
                 --output-filename=AI短剧生成器.exe ^
                 app.py
```

---

## 🚀 分发和运行

### 打包后的文件夹结构
```
AI短剧生成器_v1.0/
├── AI短剧生成器.exe      # 双击运行
├── ffmpeg/               # 自带FFmpeg
├── resource_pool/        # 角色/场景/物品池
├── README.txt           # 使用说明
└── .env.example         # 配置示例
```

### 用户只需：
1. ✅ 解压整个文件夹
2. ✅ 双击 `AI短剧生成器.exe`
3. ✅ 在界面中配置API密钥
4. ✅ 开始使用！

**无需安装**：
- ❌ 不需要安装Python
- ❌ 不需要安装FFmpeg
- ❌ 不需要配置环境变量
- ❌ 不需要安装任何依赖

---

## ⚠️ 注意事项

### 1. FFmpeg大小
- FFmpeg文件夹约 **200-300MB**
- 打包后的exe约 **300-400MB**
- 可以使用UPX压缩减小体积

### 2. 杀毒软件误报
- PyInstaller打包的exe可能被杀毒软件误报
- 解决方案：
  - 添加到白名单
  - 使用代码签名证书
  - 使用Nuitka打包（误报率更低）

### 3. 配置文件
- `.env`文件包含API密钥，**不要打包进去**
- 让用户首次运行时自己配置
- 可以提供`.env.example`作为模板

### 4. 输出目录
- 建议在exe同目录创建`output`文件夹
- 使用相对路径：`os.path.join(os.path.dirname(__file__), "output")`

---

## 🔧 优化建议

### 减小打包体积
1. **使用虚拟环境**（只安装必要的包）
```bash
python -m venv build_env
build_env\Scripts\activate
pip install streamlit requests python-dotenv
```

2. **排除不必要的模块**
```bash
pyinstaller --exclude-module matplotlib ^
            --exclude-module numpy ^
            app.py
```

3. **使用UPX压缩**
```bash
# 下载UPX并添加到PATH
pyinstaller --upx-dir=/path/to/upx app.py
```

---

## 📝 快速打包脚本

创建 `build.bat`：
```batch
@echo off
echo ================================
echo AI短剧生成器 - 打包工具
echo ================================
echo.

echo [1/3] 安装PyInstaller...
pip install pyinstaller

echo.
echo [2/3] 开始打包...
pyinstaller --name "AI短剧生成器" ^
            --windowed ^
            --add-data "ffmpeg;ffmpeg" ^
            --add-data "resource_pool;resource_pool" ^
            --clean ^
            app.py

echo.
echo [3/3] 打包完成！
echo 输出目录：dist\AI短剧生成器\
echo.
pause
```

双击 `build.bat` 即可一键打包！

---

## 🎯 总结

**当前状态**：
- ✅ FFmpeg已集成到项目目录
- ✅ 代码已配置为自动查找项目内FFmpeg
- ✅ 可以直接打包，无需用户额外安装

**打包后**：
- ✅ 其他电脑可以直接运行
- ✅ 不需要安装Python、FFmpeg等任何依赖
- ✅ 开箱即用！
