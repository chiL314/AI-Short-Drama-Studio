# ===================== 加载环境变量 =====================
import os
from dotenv import load_dotenv
from utils.logger import get_logger

# 加载 .env 文件（如果存在）
load_dotenv(override=True)


def reload_env():
    """重新加载 .env 文件并更新所有配置变量（用于运行时修改 .env 后刷新）"""
    load_dotenv(override=True)
    global DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL
    global SEEDANCE_API_KEY, SEEDANCE_API_URL, SEEDANCE_MODEL
    global TTS_PROVIDER, TTS_ALIYUN_APPKEY, TTS_ALIYUN_TOKEN
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "qwen3.5-flash")
    SEEDANCE_API_KEY = os.getenv("SEEDANCE_API_KEY", "")
    SEEDANCE_API_URL = os.getenv("SEEDANCE_API_URL", "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks")
    SEEDANCE_MODEL = os.getenv("SEEDANCE_MODEL", "doubao-seedance-1-0-pro-250528")
    TTS_PROVIDER = os.getenv("TTS_PROVIDER", "aliyun")
    TTS_ALIYUN_APPKEY = os.getenv("TTS_ALIYUN_APPKEY", "")
    TTS_ALIYUN_TOKEN = os.getenv("TTS_ALIYUN_TOKEN", "")

logger = get_logger(__name__)

# ===================== 大模型API配置 =====================
# 优先级：.env 文件 > 默认值
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "qwen3.5-flash")

# ===================== 视频生成API配置（即梦Seedance） =====================
SEEDANCE_API_KEY = os.getenv("SEEDANCE_API_KEY", "")
SEEDANCE_API_URL = os.getenv("SEEDANCE_API_URL", "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks")
SEEDANCE_MODEL = os.getenv("SEEDANCE_MODEL", "doubao-seedance-1-0-pro-250528")

# ===================== 全局统一配置（永久生效） =====================
# 注意：这个默认值会在步骤0被用户的配置覆盖
BASE_STYLE_PROMPT = """
9:16竖屏，日系动漫风格，2D动画质感，精美手绘风格，
色彩鲜艳明亮，线条流畅，人物造型精致可爱，
典型日本动画画风，场景细节丰富，光影效果柔和，
画面清新自然，无写实感，典型二次元美学。
"""

# 单分镜固定时长（秒）
SHOT_DURATION = 5

# 视频生成失败重试次数
MAX_RETRY = 3

# API请求间隔（秒，防止限流）
API_INTERVAL = 3

# ===================== 调试配置 =====================
# 模拟运行模式：跳过所有API调用，仅输出完整prompt和payload到日志
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes")

# ===================== 资源池配置 =====================
RESOURCE_POOL_DIR = "./resource_pool"  # 资源池根目录

# ===================== TTS配音配置 =====================
# TTS服务商（支持：aliyun, xunfei, azure）
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "aliyun")

# 阿里云TTS配置
TTS_ALIYUN_APPKEY = os.getenv("TTS_ALIYUN_APPKEY", "")
TTS_ALIYUN_TOKEN = os.getenv("TTS_ALIYUN_TOKEN", "")

# 默认音色列表
DEFAULT_VOICE_OPTIONS = [
    {"id": "xiaoyun", "name": "小云", "gender": "女", "style": "标准女声"},
    {"id": "xiaogang", "name": "小刚", "gender": "男", "style": "标准男声"},
    {"id": "xiaomei", "name": "小美", "gender": "女", "style": "温柔女声"},
    {"id": "xiaoming", "name": "小明", "gender": "男", "style": "青年男声"},
    {"id": "ailun", "name": "艾伦", "gender": "男", "style": "成熟男声"},
    {"id": "xiaoqian", "name": "小倩", "gender": "女", "style": "甜美少女"},
]