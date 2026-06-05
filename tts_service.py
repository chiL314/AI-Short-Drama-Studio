"""
TTS配音服务模块
支持多种TTS服务商：阿里云、讯飞、Azure
"""
import os
import requests
from typing import Dict, List
import config as cfg
from utils.logger import get_logger

logger = get_logger(__name__)


class TTSService:
    """TTS配音服务"""
    
    def __init__(self, provider: str = None):
        """初始化TTS服务
        
        Args:
            provider: TTS服务商（aliyun/xunfei/azure）
        """
        self.provider = provider or cfg.TTS_PROVIDER
        self.voice_cache = {}  # 缓存已生成的音频
        
    def get_available_voices(self) -> List[Dict]:
        """获取可用音色列表（从TTS服务商API动态获取）
        
        Returns:
            音色列表 [{"id": "xiaoyun", "name": "小云", "gender": "女", "style": "标准女声"}]
        """
        if self.provider == "aliyun":
            # 从阿里云API动态获取音色列表
            return self._fetch_aliyun_voices()
        elif self.provider == "xunfei":
            # 从讯飞API动态获取音色列表
            return self._fetch_xunfei_voices()
        elif self.provider == "azure":
            # 从Azure API动态获取音色列表
            return self._fetch_azure_voices()
        else:
            # 如果未配置或获取失败，返回空列表
            return []
    
    def _fetch_aliyun_voices(self) -> List[Dict]:
        """从阿里云TTS API获取音色列表"""
        # 检查是否配置了API密钥
        if not cfg.TTS_ALIYUN_TOKEN:
            return []  # 未配置，返回空列表
        
        try:
            # 调用阿里云百炼平台音色列表API
            url = "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization"
            headers = {
                "Authorization": f"Bearer {cfg.TTS_ALIYUN_TOKEN}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "qwen-voice-design",
                "input": {
                    "action": "list",
                    "page_size": 100,  # 获取最多100个音色
                    "page_index": 0
                }
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                voice_list = data.get("output", {}).get("voice_list", [])
                
                # 转换为统一格式
                voices = []
                for item in voice_list:
                    voice_id = item.get("voice", "")
                    target_model = item.get("target_model", "")
                    voice_prompt = item.get("voice_prompt", "")
                    language = item.get("language", "zh")
                    
                    # 根据语言判断性别和风格（简单推断）
                    gender = "女" if any(kw in voice_prompt for kw in ["女", "female", "萝莉", "温柔", "甜美"]) else "男"
                    style = voice_prompt if voice_prompt else "标准音色"
                    
                    voices.append({
                        "id": voice_id,
                        "name": voice_id,  # API返回的可能就是ID
                        "gender": gender,
                        "style": style,
                        "category": language,
                        "target_model": target_model
                    })
                
                logger.info("从阿里云API获取到 %d 个音色", len(voices))
                return voices
            else:
                logger.warning("阿里云API调用失败: HTTP %d", response.status_code)
                return []

        except Exception as e:
            logger.warning("获取阿里云音色列表失败: %s", e)
            return []
    
    def _fetch_xunfei_voices(self) -> List[Dict]:
        """从讯飞TTS API获取音色列表"""
        # TODO: 实现讯飞API调用
        logger.warning("讯飞TTS音色列表API尚未实现")
        return []
    
    def _fetch_azure_voices(self) -> List[Dict]:
        """从Azure TTS API获取音色列表"""
        # TODO: 实现Azure API调用
        logger.warning("Azure TTS音色列表API尚未实现")
        return []
    
    def synthesize(self, text: str, voice_id: str = None, output_path: str = None) -> str:
        """合成语音
        
        Args:
            text: 要合成的文本
            voice_id: 音色ID
            output_path: 输出文件路径
            
        Returns:
            音频文件路径
        """
        if not text or not text.strip():
            return None
        
        # 默认音色
        if not voice_id:
            voice_id = cfg.DEFAULT_VOICE_OPTIONS[0]["id"]
        
        # 检查缓存
        cache_key = f"{text}_{voice_id}"
        if cache_key in self.voice_cache:
            return self.voice_cache[cache_key]
        
        # 生成音频
        if self.provider == "aliyun":
            audio_path = self._aliyun_tts(text, voice_id, output_path)
        elif self.provider == "xunfei":
            audio_path = self._xunfei_tts(text, voice_id, output_path)
        elif self.provider == "azure":
            audio_path = self._azure_tts(text, voice_id, output_path)
        else:
            raise ValueError(f"不支持的TTS服务商: {self.provider}")
        
        # 缓存结果
        if audio_path:
            self.voice_cache[cache_key] = audio_path
        
        return audio_path
    
    def _aliyun_tts(self, text: str, voice_id: str, output_path: str = None) -> str:
        """阿里云TTS"""
        if not cfg.TTS_ALIYUN_TOKEN:
            raise ValueError("未配置阿里云TTS Token，请在API配置中设置")
        
        if output_path is None:
            os.makedirs("./output/tts", exist_ok=True)
            output_path = f"./output/tts/{voice_id}_{hash(text) % 10000}.wav"
        
        try:
            # 调用阿里云TTS API
            url = "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/speech-synthesis"
            headers = {
                "Authorization": f"Bearer {cfg.TTS_ALIYUN_TOKEN}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "qwen-tts",
                "input": {
                    "text": text
                },
                "parameters": {
                    "voice": voice_id,
                    "format": "wav",
                    "sample_rate": 48000,
                    "volume": 50,
                    "speech_rate": 0,
                    "pitch_rate": 0
                }
            }
            
            logger.info("正在调用阿里云TTS: %s, 文本: %s", voice_id, text[:50])
            last_error = None
            for attempt in range(3):
                try:
                    response = requests.post(url, json=payload, headers=headers, timeout=30)
                    break
                except requests.exceptions.RequestException as e:
                    last_error = e
                    if attempt < 2:
                        logger.warning("TTS请求失败（第%d次），重试中...", attempt + 1)
                        import time
                        time.sleep(2)
            if last_error:
                raise last_error
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                logger.info("TTS生成成功: %s", output_path)
                return output_path
            else:
                error_msg = response.json().get('message', '未知错误')
                raise Exception(f"TTS API调用失败 (HTTP {response.status_code}): {error_msg}")

        except Exception as e:
            logger.error("TTS调用失败: %s", e)
            raise
    
    def _xunfei_tts(self, text: str, voice_id: str, output_path: str = None) -> str:
        """讯飞TTS"""
        # TODO: 实现讯飞TTS
        logger.info("使用讯飞TTS合成语音: %s", voice_id)
        return None
    
    def _azure_tts(self, text: str, voice_id: str, output_path: str = None) -> str:
        """Azure TTS"""
        # TODO: 实现Azure TTS
        logger.info("使用Azure TTS合成语音: %s", voice_id)
        return None


def get_tts_service(provider: str = None) -> TTSService:
    """获取TTS服务实例
    
    Args:
        provider: TTS服务商
        
    Returns:
        TTS服务实例
    """
    return TTSService(provider)
