# 资源池使用指南

## 📂 项目结构

```
text-video/
├── character_pool.py      # 角色池管理模块
├── scene_pool.py          # 场景池管理模块
├── prop_pool.py           # 物品池管理模块
├── config.py              # 配置文件（含资源池路径）
├── script_processor.py    # 分镜生成（已集成角色池）
├── video_generator.py     # 视频生成（已集成角色池）
├── test_resource_pool.py  # 测试脚本
├── resource_pool/         # 资源池数据目录
│   ├── characters.json    # 角色池数据
│   ├── scenes.json        # 场景池数据
│   └── props.json         # 物品池数据
└── README_RESOURCE_POOL.md # 本文档
```

---

## 🎯 核心设计理念

### 资源池 vs 项目分离

- **资源池** (`resource_pool/`): 全局共享的角色、场景、物品库
- **项目区** (`projects/`): 每个剧本的分镜数据和生成输出
- **优势**: 一个角色可以被多个剧本复用，避免重复存储

### 本地路径引用

- 不复制图片文件到项目目录
- 直接记录本地路径（如 `D:/角色池/男主A.jpg`）
- 支持多种图片格式：`.jpg`, `.png`, `.webp`, `.bmp`

---

## 📖 使用方法

### 1️⃣ 角色池使用

#### 添加角色

```python
from character_pool import CharacterPool

pool = CharacterPool()

char_id = pool.add(
    name="男主A",                          # 角色名称
    appearance="欧美男性，28岁，185cm",     # 外观描述
    clothes="简约休闲度假风",               # 服装描述
    character="沉稳冷静，心思缜密",         # 性格描述
    image_path="D:/角色池/男主A.jpg",      # 本地图片路径
    voice_id="elevenlabs_123",             # 音色ID（可选）
    tags=["主角", "现代", "欧美"]           # 标签（可选）
)

print(f"角色ID: {char_id}")  # 输出: char_001
```

#### 检索角色

```python
# 从剧本中自动检索出场角色
script = "男主A在海边度假酒店醒来"
matched_chars = pool.search_by_name(script)

for char in matched_chars:
    print(f"匹配角色: {char['name']}")
    print(f"  外观: {char['appearance']}")
    print(f"  图片路径: {char['image_path']}")
```

#### 获取角色完整信息

```python
char = pool.get_by_name("男主A")

if char:
    print(f"名称: {char['name']}")
    print(f"外观: {char['appearance']}")
    print(f"服装: {char['clothes']}")
    print(f"性格: {char['character']}")
    print(f"图片: {char['image_path']}")
    print(f"音色: {char['voice_id']}")
    print(f"标签: {char['tags']}")
```

#### 构建角色提示词

```python
# 自动生成完整的角色描述提示词（用于视频生成）
prompt = pool.build_role_prompt("男主A")
print(prompt)
# 输出: 欧美男性，28岁，185cm，穿着简约休闲度假风，性格沉稳冷静，心思缜密
```

#### 更新角色

```python
pool.update(
    "char_001",
    clothes="黑色西装",  # 更新服装
    image_path="D:/角色池/男主A_新.jpg"  # 更新图片
)
```

#### 删除角色

```python
pool.delete("char_001")
```

#### 获取所有角色

```python
all_chars = pool.get_all()
print(f"角色总数: {len(all_chars)}")

for char in all_chars:
    print(f"  - {char['name']} ({char['id']})")
```

---

### 2️⃣ 场景池使用

#### 添加场景

```python
from scene_pool import ScenePool

pool = ScenePool()

scene_id = pool.add(
    name="海边度假酒店",                    # 场景名称
    description="豪华海景房，落地窗，清晨阳光",  # 场景描述
    image_path="D:/场景素材/海边度假酒店.jpg"  # 本地图片路径
)

print(f"场景ID: {scene_id}")  # 输出: scene_001
```

#### 检索场景

```python
script = "男主A在海边度假酒店醒来"
matched_scenes = pool.search_by_name(script)

for scene in matched_scenes:
    print(f"匹配场景: {scene['name']}")
    print(f"  描述: {scene['description']}")
```

#### 获取所有场景

```python
all_scenes = pool.get_all()
for scene in all_scenes:
    print(f"  - {scene['name']}")
```

---

### 3️⃣ 物品池使用

#### 添加物品

```python
from prop_pool import PropPool

pool = PropPool()

prop_id = pool.add(
    name="手机",                           # 物品名称
    description="iPhone 15 Pro，深空黑色",  # 物品描述
    image_path="D:/道具库/手机.jpg"         # 本地图片路径
)

print(f"物品ID: {prop_id}")  # 输出: prop_001
```

#### 检索物品

```python
script = "男主A拿起手机查看消息"
matched_props = pool.search_by_name(script)

for prop in matched_props:
    print(f"匹配物品: {prop['name']}")
    print(f"  描述: {prop['description']}")
```

---

## 🔗 与现有代码集成

### 分镜生成（script_processor.py）

已自动集成角色池，无需修改代码：

```python
from script_processor import generate_shots_from_script

script = "男主A在海边度假酒店醒来..."
shots = generate_shots_from_script(script, shot_count=5, episode_num=1)

# 系统会自动从角色池检索"男主A"，并将其人设信息发送给LLM
```

### 视频生成（video_generator.py）

已自动集成角色池，无需修改代码：

```python
from video_generator import batch_generate_videos

batch_generate_videos(episode_num=1)

# 系统会：
# 1. 从分镜JSON中读取角色名
# 2. 从角色池获取角色的本地图片路径
# 3. 将图片转换为base64
# 4. 发送给视频生成API
```

---

## 🧪 测试验证

运行测试脚本验证所有功能：

```bash
cd D:\python\text-video
python test_resource_pool.py
```

**预期输出：**
```
============================================================
🚀 资源池完整测试
============================================================

============================================================
🎭 测试角色池
============================================================
✅ 创建角色池文件: resource_pool\characters.json

📝 1. 添加角色
✅ 添加角色成功: 男主A (ID: char_001)

📋 2. 获取所有角色
角色总数: 1
  - 男主A (char_001)

🔍 3. 根据名称获取角色
✅ 找到: 男主A
   外观: 欧美男性，28岁，185cm，黑色短发，五官立体
   ...

============================================================
✅ 所有测试完成
============================================================
```

---

## 📝 JSON数据结构

### characters.json（角色池）

```json
[
  {
    "id": "char_001",
    "name": "男主A",
    "appearance": "欧美男性，28岁，185cm，黑色短发，五官立体",
    "clothes": "简约休闲度假风",
    "character": "沉稳冷静，心思缜密",
    "image_path": "D:/角色池/男主A.jpg",
    "voice_id": "elevenlabs_123",
    "tags": ["主角", "现代", "欧美"],
    "created_at": "2026-05-20T21:58:02.886628",
    "updated_at": "2026-05-20T21:58:02.886628"
  }
]
```

### scenes.json（场景池）

```json
[
  {
    "id": "scene_001",
    "name": "海边度假酒店",
    "description": "豪华海景房，落地窗，清晨阳光",
    "image_path": "D:/场景素材/海边度假酒店.jpg",
    "created_at": "2026-05-20T21:58:02.889629"
  }
]
```

### props.json（物品池）

```json
[
  {
    "id": "prop_001",
    "name": "手机",
    "description": "iPhone 15 Pro，深空黑色",
    "image_path": "D:/道具库/手机.jpg",
    "created_at": "2026-05-20T21:58:02.891628"
  }
]
```

---

## ⚙️ 配置说明

在 `config.py` 中配置资源池路径：

```python
# 资源池配置
RESOURCE_POOL_DIR = "./resource_pool"  # 资源池根目录
```

如需自定义路径：

```python
RESOURCE_POOL_DIR = "D:/我的资源池"
```

---

## 💡 最佳实践

### 1. 图片路径规范

推荐使用正斜杠（`/`）或双反斜杠（`\\`）：

```python
# ✅ 正确
"D:/角色池/男主A.jpg"
"D:\\角色池\\男主A.jpg"

# ❌ 错误（可能导致路径解析问题）
"D:\角色池\男主A.jpg"
```

### 2. 角色命名规范

- 使用有意义的名称：`男主A`, `女主B`, `反派C`
- 避免特殊字符和空格
- 保持名称一致性

### 3. 标签使用

为角色添加标签，便于检索：

```python
tags=["主角", "现代", "欧美", "动作"]
```

### 4. 图片格式

支持以下格式：
- `.jpg` / `.jpeg` - 推荐（文件小）
- `.png` - 支持透明背景
- `.webp` - 现代格式
- `.bmp` - 无损但文件大

---

## 🔧 常见问题

### Q1: 图片路径验证失败？

**原因**: 图片文件不存在或格式不支持

**解决**:
```python
import os

# 检查文件是否存在
if os.path.exists("D:/角色池/男主A.jpg"):
    print("文件存在")
else:
    print("文件不存在，请检查路径")
```

### Q2: 角色检索不到？

**原因**: 角色名不匹配

**解决**:
```python
# 确保剧本中的角色名与角色池一致
# 角色池: "男主A"
# 剧本: "男主A在海边醒来"  ✅
# 剧本: "男主角A在海边醒来"  ❌（不匹配）
```

### Q3: 如何批量导入角色？

```python
from character_pool import CharacterPool

pool = CharacterPool()

# 批量添加
characters = [
    {
        "name": "男主A",
        "appearance": "欧美男性，28岁",
        "image_path": "D:/角色池/男主A.jpg"
    },
    {
        "name": "女主B",
        "appearance": "欧美女性，25岁",
        "image_path": "D:/角色池/女主B.jpg"
    }
]

for char_data in characters:
    try:
        pool.add(**char_data)
    except ValueError as e:
        print(f"跳过: {e}")
```

---

## 📞 技术支持

如有问题，请检查：
1. Python版本 >= 3.8
2. 依赖库已安装
3. 路径格式正确
4. 文件权限正常

---

## ✅ 完成清单

- ✅ 角色池模块 (`character_pool.py`)
- ✅ 场景池模块 (`scene_pool.py`)
- ✅ 物品池模块 (`prop_pool.py`)
- ✅ 配置文件更新 (`config.py`)
- ✅ 分镜生成集成 (`script_processor.py`)
- ✅ 视频生成集成 (`video_generator.py`)
- ✅ 测试脚本 (`test_resource_pool.py`)
- ✅ 使用文档 (本文档)

---

**最后更新**: 2026-05-20
