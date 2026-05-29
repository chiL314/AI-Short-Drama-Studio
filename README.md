# 🎬 AI短剧自动生成系统

> 从剧本到视频，全流程自动化生成的商业化解决方案

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.57.0-FF4B4B.svg)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## ✨ 功能特性

### 🎯 核心功能

- **智能分镜生成**: LLM自动将剧本拆分为结构化分镜
- **资源池管理**: 角色/场景/物品统一管理与复用
- **视频自动生成**: AI视频生成，支持多种画风和分辨率
- **TTS配音**: 自动配音与字幕生成
- **可视化编辑**: Web界面实时预览和编辑

### 🎨 界面特色

- **现代化UI**: 渐变色背景、卡片式设计、流畅动画
- **步骤式流程**: 6步引导式操作，简单直观
- **智能化匹配**: 自动关联资源，手动可调
- **实时预览**: 分镜提示词、视频、资源缩略图实时展示

### 📊 可配置项

- ✅ 分镜数量（1-50个）
- ✅ 单分镜时长（3-10秒）
- ✅ 分辨率（720p/1080p/4K）
- ✅ 帧率（24/30/60 fps）
- ✅ 画面比例（9:16/16:9/1:1）
- ✅ 画风预设（写实/动漫/赛博朋克/水彩）
- ✅ TTS配音开关
- ✅ 字幕开关与语言选择
- ✅ 自定义提示词模板
- ✅ 输出模式（分镜视频/完整剪辑）

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install streamlit
```

### 2. 启动界面

**方式1: 命令行**
```bash
cd D:\python\text-video
streamlit run app.py
```

**方式2: 双击脚本**
```
双击 启动界面.bat
```

### 3. 访问界面

浏览器打开: **http://localhost:8501**

---

## 📖 使用流程

### 步骤1: ⚙️ 参数配置

配置视频生成参数：
- 分镜数量
- 分辨率和帧率
- 画风预设
- 音频配置（配音/字幕）
- 自定义提示词

### 步骤2: 📝 输入剧本

- 输入完整剧本文本
- 点击"生成分镜"
- 系统自动拆分剧本

### 步骤3: ✏️ 编辑分镜

- 查看生成的分镜
- 编辑每个分镜的提示词
- 调整出场角色

### 步骤4: 🔗 关联资源

- 查看角色池/场景池/物品池
- 系统自动匹配资源
- 手动调整关联关系

### 步骤5: 🎬 生成视频

- 确认配置信息
- 点击"开始生成"
- 等待AI生成视频

### 步骤6: ✅ 检查导出

- 预览生成的视频
- 选择输出模式
- 重做不满意的分镜
- 导出最终视频

---

## 📁 项目结构

```
text-video/
├── app.py                      # Streamlit Web界面（主程序）
├── character_pool.py           # 角色池管理
├── scene_pool.py               # 场景池管理
├── prop_pool.py                # 物品池管理
├── config.py                   # 全局配置
├── script_processor.py         # 分镜生成
├── video_generator.py          # 视频生成
├── main.py                     # 命令行入口（旧版）
├── test_resource_pool.py       # 资源池测试
├── quick_start.py              # 快速上手示例
├── resource_pool/              # 资源池数据
│   ├── characters.json         # 角色池
│   ├── scenes.json             # 场景池
│   └── props.json              # 物品池
├── shots/                      # 分镜数据
├── output/                     # 生成的视频
├── 启动界面.bat                 # 快捷启动脚本
├── 启动说明.md                  # 启动说明
└── README.md                   # 本文档
```

---

## 💡 使用示例

### 添加角色到资源池

```python
from character_pool import CharacterPool

pool = CharacterPool()
pool.add(
    name="男主A",
    appearance="欧美男性，28岁，185cm，黑色短发",
    clothes="简约休闲度假风",
    character="沉稳冷静，心思缜密",
    image_path="D:/角色池/男主A.jpg",
    voice_id="elevenlabs_123",
    tags=["主角", "现代", "欧美"]
)
```

### 添加场景

```python
from scene_pool import ScenePool

pool = ScenePool()
pool.add(
    name="海边度假酒店",
    description="豪华海景房，落地窗，清晨阳光",
    image_path="D:/场景素材/海边度假酒店.jpg"
)
```

### 批量导入资源

```python
from character_pool import CharacterPool

pool = CharacterPool()

characters = [
    {"name": "男主A", "appearance": "欧美男性，28岁", "image_path": "D:/男主A.jpg"},
    {"name": "女主B", "appearance": "欧美女性，25岁", "image_path": "D:/女主B.jpg"}
]

for char in characters:
    try:
        pool.add(**char)
    except ValueError:
        print(f"角色已存在: {char['name']}")
```

---

## 🎨 界面截图

### 参数配置页面
- 分镜数量、时长设置
- 分辨率、帧率选择
- 画风预设
- 音频配置

### 分镜编辑页面
- 分镜列表展示
- 提示词实时编辑
- 出场角色显示

### 资源关联页面
- 角色池/场景池/物品池标签页
- 资源卡片缩略图
- 自动匹配与手动选择

### 视频生成页面
- 配置摘要显示
- 进度条展示
- 视频实时预览

---

## ⚙️ 配置说明

### API配置 (config.py)

```python
# DeepSeek API（分镜生成）
DEEPSEEK_API_KEY = "your_api_key"
DEEPSEEK_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
DEEPSEEK_MODEL = "qwen3.5-flash"

# Seedance API（视频生成）
SEEDANCE_API_KEY = "your_api_key"
SEEDANCE_API_URL = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
SEEDANCE_MODEL = "doubao-seedance-1-0-pro-250528"

# 全局配置
BASE_STYLE_PROMPT = "9:16竖屏，美剧写实真人电影质感..."
SHOT_DURATION = 5
MAX_RETRY = 3
API_INTERVAL = 3
RESOURCE_POOL_DIR = "./resource_pool"
```

---

## 🔧 技术栈

- **前端**: Streamlit + 自定义CSS
- **后端**: Python 3.8+
- **AI模型**: 
  - 分镜生成: DeepSeek/Qwen
  - 视频生成: 即梦Seedance
- **资源管理**: 本地文件系统 + JSON
- **数据处理**: 原生Python

---

## 📝 开发计划

### Phase 1: 基础功能 ✅
- [x] 角色池/场景池/物品池
- [x] 分镜自动生成
- [x] Web界面基础版
- [x] 视频生成

### Phase 2: 界面优化 ✅
- [x] 现代化UI设计
- [x] 步骤式流程
- [x] 实时预览
- [x] 资源关联

### Phase 3: 高级功能 🚧
- [ ] TTS配音集成
- [ ] 字幕生成
- [ ] FFmpeg视频拼接
- [ ] 批量任务管理

### Phase 4: 商业化 📋
- [ ] 用户系统
- [ ] 项目管理
- [ ] 素材商城
- [ ] 云端同步
- [ ] 付费套餐

---

## 📊 性能优化

- **断点续跑**: 已生成的分镜自动跳过
- **批量处理**: 支持多任务队列
- **缓存机制**: 资源配置自动保存
- **错误重试**: API失败自动重试

---

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

---

## 📞 联系方式

- 项目地址: [GitHub Repository](https://github.com/your-repo)
- 问题反馈: [Issues](https://github.com/your-repo/issues)
- 邮箱: your-email@example.com

---

## 🙏 致谢

感谢以下开源项目：
- [Streamlit](https://streamlit.io/) - Web界面框架
- [DeepSeek](https://deepseek.com/) - LLM分镜生成
- [Seedance](https://seedance.com/) - AI视频生成

---

**最后更新**: 2026-05-20

**Made with ❤️ by AI短剧团队**
