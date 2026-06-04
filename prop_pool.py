# prop_pool.py - 物品池管理模块

import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from utils.logger import get_logger

logger = get_logger(__name__)


class PropPool:
    """物品池管理器"""
    
    def __init__(self, pool_dir: str = "./resource_pool"):
        self.pool_dir = Path(pool_dir)
        self.pool_dir.mkdir(parents=True, exist_ok=True)
        
        self.json_file = self.pool_dir / "props.json"
        self._init_json()
    
    def _init_json(self):
        """初始化JSON文件"""
        if not self.json_file.exists():
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            logger.info("创建物品池文件: %s", self.json_file)
    
    def _read_json(self) -> List[Dict]:
        """读取物品池JSON"""
        with open(self.json_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _write_json(self, data: List[Dict]):
        """写入物品池JSON"""
        with open(self.json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    # ==================== 核心API ====================
    
    def add(self, name: str, description: str = "", image_path: str = "") -> str:
        """
        添加物品到资源池
        
        Args:
            name: 物品名称（如"手机"）
            description: 物品描述（如"iPhone 15 Pro，深空黑色"）
            image_path: 本地图片路径（如"D:/道具库/手机.jpg"）
        
        Returns:
            物品ID
        """
        props = self._read_json()
        
        # 检查重名
        for prop in props:
            if prop['name'] == name:
                raise ValueError(f"物品已存在: {name}")
        
        # 生成ID
        prop_id = f"prop_{len(props) + 1:03d}"
        
        prop_data = {
            "id": prop_id,
            "name": name,
            "description": description,
            "image_path": image_path,
            "created_at": datetime.now().isoformat()
        }
        
        props.append(prop_data)
        self._write_json(props)
        
        logger.info("添加物品成功: %s (ID: %s)", name, prop_id)
        return prop_id
    
    def delete(self, prop_id: str) -> bool:
        """
        删除物品
        
        Args:
            prop_id: 物品ID
        
        Returns:
            是否删除成功
        """
        props = self._read_json()
        original_count = len(props)
        
        props = [p for p in props if p['id'] != prop_id]
        
        if len(props) == original_count:
            logger.warning("物品不存在: %s", prop_id)
            return False

        self._write_json(props)
        logger.info("删除物品成功: %s", prop_id)
        return True

    def get_by_name(self, name: str) -> Optional[Dict]:
        """
        根据物品名获取完整配置
        
        Args:
            name: 物品名称
        
        Returns:
            物品完整配置字典，不存在返回None
        """
        props = self._read_json()
        
        for prop in props:
            if prop['name'] == name:
                return prop
        
        return None

    def get_all(self) -> List[Dict]:
        """获取所有物品"""
        return self._read_json()

    def search_by_name(self, text: str) -> List[Dict]:
        """
        根据文本检索物品（匹配物品名）
        
        Args:
            text: 搜索文本（如剧本内容）
        
        Returns:
            匹配的物品列表
        """
        props = self._read_json()
        return [p for p in props if p['name'] in text]

    def count(self) -> int:
        """获取物品数量"""
        return len(self._read_json())


# ==================== 便捷函数 ====================

# 全局单例
_prop_pool = None


def get_prop_pool(pool_dir: str = "./resource_pool") -> PropPool:
    """获取物品池单例"""
    global _prop_pool
    if _prop_pool is None:
        _prop_pool = PropPool(pool_dir)
    return _prop_pool


def add_prop(name: str, description: str = "", image_path: str = "") -> str:
    """添加物品（便捷函数）"""
    return get_prop_pool().add(name, description, image_path)


def get_prop(name: str) -> Optional[Dict]:
    """获取物品（便捷函数）"""
    return get_prop_pool().get_by_name(name)


def search_props(text: str) -> List[Dict]:
    """检索物品（便捷函数）"""
    return get_prop_pool().search_by_name(text)


# ==================== 测试代码 ====================

if __name__ == "__main__":
    print("="*50)
    print("🎒 物品池模块测试")
    print("="*50)
    
    pool = PropPool()
    
    # 测试1: 添加物品
    print("\n📝 测试1: 添加物品")
    try:
        prop_id = pool.add(
            name="手机",
            description="iPhone 15 Pro，深空黑色",
            image_path="D:/道具库/手机.jpg"
        )
        print(f"✅ 物品ID: {prop_id}")
    except Exception as e:
        print(f"❌ 添加失败: {e}")
    
    # 测试2: 获取所有物品
    print("\n📋 测试2: 获取所有物品")
    all_props = pool.get_all()
    print(f"物品数量: {len(all_props)}")
    for prop in all_props:
        print(f"  - {prop['name']} ({prop['id']})")
    
    # 测试3: 根据名称获取
    print("\n🔍 测试3: 根据名称获取物品")
    prop = pool.get_by_name("手机")
    if prop:
        print(f"找到物品: {prop['name']}")
        print(f"  描述: {prop['description']}")
        print(f"  图片路径: {prop['image_path']}")
    
    # 测试4: 检索物品
    print("\n🔎 测试4: 检索物品")
    text = "男主A拿起手机查看消息"
    matched = pool.search_by_name(text)
    print(f"文本: {text}")
    print(f"匹配物品: {[p['name'] for p in matched]}")
    
    print("\n" + "="*50)
    print("✅ 测试完成")
    print("="*50)
