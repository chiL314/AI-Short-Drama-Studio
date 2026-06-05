# character_pool.py - 角色池管理模块

import json
import os
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from utils.logger import get_logger

logger = get_logger(__name__)


class CharacterPool:
    """角色池管理器 - 使用本地路径引用，不复制文件"""
    
    def __init__(self, pool_dir: str = "./resource_pool"):
        self.pool_dir = Path(pool_dir)
        self.pool_dir.mkdir(parents=True, exist_ok=True)
        
        self.json_file = self.pool_dir / "characters.json"
        self._init_json()
    
    def _init_json(self):
        """初始化JSON文件"""
        if not self.json_file.exists():
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            logger.info("创建角色池文件: %s", self.json_file)
    
    def _read_json(self) -> List[Dict]:
        """读取角色池JSON"""
        with open(self.json_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _write_json(self, data: List[Dict]):
        """写入角色池JSON"""
        with open(self.json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _validate_image_path(self, image_path: str) -> bool:
        """验证本地图片路径是否有效"""
        if not image_path:
            return False
        
        # 支持多种图片格式
        valid_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
        path = Path(image_path)
        
        if not path.exists():
            logger.warning("图片文件不存在: %s", image_path)
            return False

        if path.suffix.lower() not in valid_extensions:
            logger.warning("不支持的图片格式: %s", path.suffix)
            return False
        
        return True
    
    # ==================== 核心API ====================
    
    def add(self, name: str, appearance: str, clothes: str = "", 
            character: str = "", image_path: str = "", 
            voice_id: str = "", tags: List[str] = None) -> str:
        """
        添加角色到资源池
        
        Args:
            name: 角色名称（如"男主A"）
            appearance: 外观描述（如"欧美男性，28岁，185cm"）
            clothes: 服装描述（如"简约休闲度假风"）
            character: 性格描述（如"沉稳冷静，心思缜密"）
            image_path: 本地图片路径（如"D:/角色池/男主A.jpg"）
            voice_id: 音色ID
            tags: 标签列表
        
        Returns:
            角色ID
        """
        characters = self._read_json()
        
        # 检查重名
        for char in characters:
            if char['name'] == name:
                raise ValueError(f"角色已存在: {name}")
        
        # 验证图片路径
        if image_path and not self._validate_image_path(image_path):
            logger.warning("图片路径无效，但仍会保存: %s", image_path)
        
        # 生成ID
        char_id = f"char_{len(characters) + 1:03d}"
        
        character_data = {
            "id": char_id,
            "name": name,
            "appearance": appearance,
            "clothes": clothes,
            "character": character,
            "image_path": image_path,
            "voice_id": voice_id,
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        characters.append(character_data)
        self._write_json(characters)
        
        logger.info("添加角色成功: %s (ID: %s)", name, char_id)
        return char_id
    
    def delete(self, char_id: str) -> bool:
        """
        删除角色（同时清理关联的图片文件）

        Args:
            char_id: 角色ID

        Returns:
            是否删除成功
        """
        characters = self._read_json()

        # 找到要删除的角色，记录图片路径
        target = next((c for c in characters if c['id'] == char_id), None)
        if target is None:
            logger.warning("角色不存在: %s", char_id)
            return False

        characters = [c for c in characters if c['id'] != char_id]
        self._write_json(characters)

        # 删除关联的图片文件（仅清理 resource_pool/images/ 下的文件）
        image_path = target.get('image_path', '')
        if image_path:
            self._cleanup_image(image_path)

        logger.info("删除角色成功: %s", char_id)
        return True

    def _cleanup_image(self, image_path: str):
        """删除 resource_pool/images/ 目录下的图片文件"""
        images_dir = self.pool_dir / "images"
        try:
            abs_image = os.path.abspath(image_path)
            abs_dir = os.path.abspath(str(images_dir))
            if abs_image.startswith(abs_dir) and os.path.exists(image_path):
                os.remove(image_path)
                logger.info("已清理图片文件: %s", image_path)
        except OSError as e:
            logger.warning("清理图片文件失败: %s", e)
    
    def update(self, char_id: str, **kwargs) -> bool:
        """
        更新角色信息
        
        Args:
            char_id: 角色ID
            **kwargs: 要更新的字段
        
        Returns:
            是否更新成功
        """
        characters = self._read_json()
        
        for char in characters:
            if char['id'] == char_id:
                # 如果更新图片路径，验证有效性
                if 'image_path' in kwargs:
                    if not self._validate_image_path(kwargs['image_path']):
                        logger.warning("新图片路径无效: %s", kwargs['image_path'])

                char.update(kwargs)
                char['updated_at'] = datetime.now().isoformat()
                self._write_json(characters)
                logger.info("更新角色成功: %s", char['name'])
                return True

        logger.warning("角色不存在: %s", char_id)
        return False
    
    def get_by_name(self, name: str) -> Optional[Dict]:
        """
        根据角色名获取完整配置
        
        Args:
            name: 角色名称
        
        Returns:
            角色完整配置字典，不存在返回None
        """
        characters = self._read_json()
        
        for char in characters:
            if char['name'] == name:
                return char
        
        return None

    def get_all(self) -> List[Dict]:
        """获取所有角色"""
        return self._read_json()
    
    def get_image_path(self, name: str) -> Optional[str]:
        """
        获取角色的本地图片路径
        
        Args:
            name: 角色名称
        
        Returns:
            图片路径，不存在返回None
        """
        char = self.get_by_name(name)
        if char:
            return char.get('image_path', '')
        return None
    
    def search_by_name(self, text: str) -> List[Dict]:
        """
        根据文本检索角色（匹配角色名或标签）
        
        Args:
            text: 搜索文本（如剧本内容）
        
        Returns:
            匹配的角色列表
        """
        characters = self._read_json()
        results = []
        
        for char in characters:
            # 匹配角色名
            if char['name'] in text:
                results.append(char)
            # 匹配标签
            elif any(tag in text for tag in char.get('tags', [])):
                results.append(char)
        
        return results
    
    def build_role_prompt(self, name: str) -> str:
        """
        构建角色完整提示词（用于视频生成）
        
        Args:
            name: 角色名称
        
        Returns:
            角色提示词字符串
        """
        char = self.get_by_name(name)
        if not char:
            return ""
        
        parts = []
        if char.get('appearance'):
            parts.append(char['appearance'])
        if char.get('clothes'):
            parts.append(f"穿着{char['clothes']}")
        if char.get('character'):
            parts.append(f"性格{char['character']}")
        
        return "，".join(parts)

    def count(self) -> int:
        """获取角色数量"""
        return len(self._read_json())


# ==================== 便捷函数（向后兼容） ====================

# 全局单例
_character_pool = None


def get_character_pool(pool_dir: str = "./resource_pool") -> CharacterPool:
    """获取角色池单例"""
    global _character_pool
    if _character_pool is None:
        _character_pool = CharacterPool(pool_dir)
    return _character_pool


def add_character(name: str, appearance: str, **kwargs) -> str:
    """添加角色（便捷函数）"""
    return get_character_pool().add(name, appearance, **kwargs)


def get_character(name: str) -> Optional[Dict]:
    """获取角色（便捷函数）"""
    return get_character_pool().get_by_name(name)


def search_characters(text: str) -> List[Dict]:
    """检索角色（便捷函数）"""
    return get_character_pool().search_by_name(text)


# ==================== 测试代码 ====================

if __name__ == "__main__":
    print("="*50)
    print("🎭 角色池模块测试")
    print("="*50)
    
    pool = CharacterPool()
    
    # 测试1: 添加角色
    print("\n📝 测试1: 添加角色")
    try:
        char_id = pool.add(
            name="男主A",
            appearance="欧美男性，28岁，185cm，黑色短发，五官立体",
            clothes="简约休闲度假风",
            character="沉稳冷静，心思缜密",
            image_path="D:/角色池/男主A.jpg",
            voice_id="elevenlabs_123",
            tags=["主角", "现代", "欧美"]
        )
        print(f"✅ 角色ID: {char_id}")
    except Exception as e:
        print(f"❌ 添加失败: {e}")
    
    # 测试2: 获取所有角色
    print("\n📋 测试2: 获取所有角色")
    all_chars = pool.get_all()
    print(f"角色数量: {len(all_chars)}")
    for char in all_chars:
        print(f"  - {char['name']} ({char['id']})")
    
    # 测试3: 根据名称获取
    print("\n🔍 测试3: 根据名称获取角色")
    char = pool.get_by_name("男主A")
    if char:
        print(f"找到角色: {char['name']}")
        print(f"  外观: {char['appearance']}")
        print(f"  图片路径: {char['image_path']}")
        print(f"  音色: {char['voice_id']}")
    
    # 测试4: 检索角色
    print("\n🔎 测试4: 检索角色")
    text = "男主A在海边度假酒店醒来"
    matched = pool.search_by_name(text)
    print(f"文本: {text}")
    print(f"匹配角色: {[c['name'] for c in matched]}")
    
    # 测试5: 构建提示词
    print("\n📝 测试5: 构建角色提示词")
    prompt = pool.build_role_prompt("男主A")
    print(f"角色提示词: {prompt}")
    
    # 测试6: 获取图片路径
    print("\n🖼️ 测试6: 获取图片路径")
    img_path = pool.get_image_path("男主A")
    print(f"图片路径: {img_path}")
    if img_path:
        print(f"文件存在: {os.path.exists(img_path)}")
    
    print("\n" + "="*50)
    print("✅ 测试完成")
    print("="*50)
