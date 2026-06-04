"""
图片处理工具函数
"""
import os
import base64
from utils.logger import get_logger

logger = get_logger(__name__)


def image_to_base64(image_path: str) -> str:
    """将本地图片转换为base64格式
    
    Args:
        image_path: 图片本地路径
        
    Returns:
        base64编码的图片字符串，格式: data:image/jpeg;base64,/9j/4AAQ...
        
    Raises:
        FileNotFoundError: 图片文件不存在
        ValueError: 不支持的图片格式
        Exception: 图片读取失败
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"图片文件不存在: {image_path}")
    
    # 读取并编码图片
    with open(image_path, "rb") as img_file:
        encoded = base64.b64encode(img_file.read()).decode('utf-8')
    
    # 确定MIME类型
    ext = os.path.splitext(image_path)[1].lower()
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.webp': 'image/webp'
    }
    mime_type = mime_types.get(ext)
    
    if not mime_type:
        raise ValueError(f"不支持的图片格式: {ext}，支持的格式: {', '.join(mime_types.keys())}")
    
    return f"data:{mime_type};base64,{encoded}"
