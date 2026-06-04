# scene_pool.py - 场景池管理模块

import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from utils.logger import get_logger

logger = get_logger(__name__)


class ScenePool:
    """场景池管理器"""
    
    def __init__(self, pool_dir: str = "./resource_pool"):
        self.pool_dir = Path(pool_dir)
        self.pool_dir.mkdir(parents=True, exist_ok=True)
        
        self.json_file = self.pool_dir / "scenes.json"
        self._init_json()
    
    def _init_json(self):
        """初始化JSON文件"""
        if not self.json_file.exists():
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            logger.info("创建场景池文件: %s", self.json_file)
    
    def _read_json(self) -> List[Dict]:
        """读取场景池JSON"""
        with open(self.json_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _write_json(self, data: List[Dict]):
        """写入场景池JSON"""
        with open(self.json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    # ==================== 核心API ====================
    
    def add(self, name: str, description: str = "", image_path: str = "") -> str:
        """
        添加场景到资源池
        
        Args:
            name: 场景名称（如"海边度假酒店"）
            description: 场景描述（如"豪华海景房，落地窗，清晨阳光"）
            image_path: 本地图片路径（如"D:/场景素材/海边度假酒店.jpg"）
        
        Returns:
            场景ID
        """
        scenes = self._read_json()
        
        # 检查重名
        for scene in scenes:
            if scene['name'] == name:
                raise ValueError(f"场景已存在: {name}")
        
        # 生成ID
        scene_id = f"scene_{len(scenes) + 1:03d}"
        
        scene_data = {
            "id": scene_id,
            "name": name,
            "description": description,
            "image_path": image_path,
            "created_at": datetime.now().isoformat()
        }
        
        scenes.append(scene_data)
        self._write_json(scenes)
        
        logger.info("添加场景成功: %s (ID: %s)", name, scene_id)
        return scene_id
    
    def delete(self, scene_id: str) -> bool:
        """
        删除场景
        
        Args:
            scene_id: 场景ID
        
        Returns:
            是否删除成功
        """
        scenes = self._read_json()
        original_count = len(scenes)
        
        scenes = [s for s in scenes if s['id'] != scene_id]
        
        if len(scenes) == original_count:
            logger.warning("场景不存在: %s", scene_id)
            return False

        self._write_json(scenes)
        logger.info("删除场景成功: %s", scene_id)
        return True

    def get_by_name(self, name: str) -> Optional[Dict]:
        """
        根据场景名获取完整配置
        
        Args:
            name: 场景名称
        
        Returns:
            场景完整配置字典，不存在返回None
        """
        scenes = self._read_json()
        
        for scene in scenes:
            if scene['name'] == name:
                return scene
        
        return None

    def get_all(self) -> List[Dict]:
        """获取所有场景"""
        return self._read_json()

    def search_by_name(self, text: str) -> List[Dict]:
        """
        根据文本检索场景（匹配场景名）
        
        Args:
            text: 搜索文本（如剧本内容）
        
        Returns:
            匹配的场景列表
        """
        scenes = self._read_json()
        return [s for s in scenes if s['name'] in text]

    def count(self) -> int:
        """获取场景数量"""
        return len(self._read_json())


# ==================== 便捷函数 ====================

# 全局单例
_scene_pool = None


def get_scene_pool(pool_dir: str = "./resource_pool") -> ScenePool:
    """获取场景池单例"""
    global _scene_pool
    if _scene_pool is None:
        _scene_pool = ScenePool(pool_dir)
    return _scene_pool


def add_scene(name: str, description: str = "", image_path: str = "") -> str:
    """添加场景（便捷函数）"""
    return get_scene_pool().add(name, description, image_path)


def get_scene(name: str) -> Optional[Dict]:
    """获取场景（便捷函数）"""
    return get_scene_pool().get_by_name(name)


def search_scenes(text: str) -> List[Dict]:
    """检索场景（便捷函数）"""
    return get_scene_pool().search_by_name(text)


# ==================== 测试代码 ====================

if __name__ == "__main__":
    print("="*50)
    print("🎬 场景池模块测试")
    print("="*50)
    
    pool = ScenePool()
    
    # 测试1: 添加场景
    print("\n📝 测试1: 添加场景")
    try:
        scene_id = pool.add(
            name="海边度假酒店",
            description="豪华海景房，落地窗，清晨阳光",
            image_path="D:/场景素材/海边度假酒店.jpg"
        )
        print(f"✅ 场景ID: {scene_id}")
    except Exception as e:
        print(f"❌ 添加失败: {e}")
    
    # 测试2: 获取所有场景
    print("\n📋 测试2: 获取所有场景")
    all_scenes = pool.get_all()
    print(f"场景数量: {len(all_scenes)}")
    for scene in all_scenes:
        print(f"  - {scene['name']} ({scene['id']})")
    
    # 测试3: 根据名称获取
    print("\n🔍 测试3: 根据名称获取场景")
    scene = pool.get_by_name("海边度假酒店")
    if scene:
        print(f"找到场景: {scene['name']}")
        print(f"  描述: {scene['description']}")
        print(f"  图片路径: {scene['image_path']}")
    
    # 测试4: 检索场景
    print("\n🔎 测试4: 检索场景")
    text = "男主A在海边度假酒店醒来"
    matched = pool.search_by_name(text)
    print(f"文本: {text}")
    print(f"匹配场景: {[s['name'] for s in matched]}")
    
    print("\n" + "="*50)
    print("✅ 测试完成")
    print("="*50)
