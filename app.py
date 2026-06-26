# -*- coding: utf-8 -*-
"""
AI短剧自动生成系统 - 商业化Web界面
使用Streamlit构建
"""

import streamlit as st
import json
import os
import shutil
import time
import requests
from pathlib import Path
from datetime import datetime

# 导入现有模块
import config
import task_manager
from character_pool import get_character_pool
from scene_pool import get_scene_pool
from prop_pool import get_prop_pool
from script_processor import generate_shots_from_script
from video_generator import batch_generate_videos, generate_single_video


# ==================== 页面配置 ====================
st.set_page_config(
    page_title="AI短剧自动生成系统",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
<style>
    .main-header {
        font-size: 3em;
        font-weight: bold;
        text-align: center;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 10px;
    }
    .sub-header {
        font-size: 1.2em;
        color: #666;
        text-align: center;
        margin-bottom: 30px;
    }
    .card {
        background: white;
        border-radius: 15px;
        padding: 20px;
        margin: 10px 0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border-left: 5px solid #667eea;
    }
    .shot-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        border: 2px solid #e0e0e0;
        transition: all 0.3s;
    }
    .shot-card:hover {
        border-color: #667eea;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
    }
    .resource-card {
        background: white;
        border-radius: 10px;
        padding: 10px;
        border: 2px solid #e0e0e0;
        text-align: center;
        cursor: pointer;
        transition: all 0.3s;
    }
    .resource-card:hover {
        border-color: #667eea;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);
    }
    .resource-card.selected {
        border-color: #667eea;
        background: #f5f7ff;
    }
    .stat-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
    }
    .stat-number {
        font-size: 2.5em;
        font-weight: bold;
    }
    .stat-label {
        font-size: 0.9em;
        opacity: 0.9;
    }
    .progress-bar {
        background: #e0e0e0;
        border-radius: 10px;
        height: 20px;
        overflow: hidden;
    }
    .progress-fill {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        height: 100%;
        transition: width 0.3s;
    }
    div[data-testid="stAppViewContainer"] > .main {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    .stButton > button {
        border-radius: 10px;
        font-weight: bold;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px 10px 0 0;
        padding: 10px 20px;
    }
    /* 资源卡片网格 */
    .res-card {
        background: white;
        border-radius: 12px;
        padding: 10px;
        border: 2px solid #e8e8e8;
        text-align: center;
        transition: all 0.3s ease;
        margin-bottom: 8px;
    }
    .res-card:hover {
        border-color: #667eea;
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.2);
        transform: translateY(-3px);
    }
    .res-card .res-name {
        font-weight: 600;
        font-size: 0.85em;
        color: #333;
        margin: 6px 0 2px 0;
        word-break: break-all;
    }
    .res-card .res-tags {
        font-size: 0.7em;
        color: #aaa;
        margin-bottom: 4px;
    }
    .res-card-empty {
        background: #fafbff;
        border: 2px dashed #d0d5f0;
        border-radius: 12px;
        text-align: center;
        padding: 20px 10px;
        min-height: 160px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        margin-bottom: 8px;
    }
    .res-section-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)


# ==================== 初始化Session State ====================
if 'current_step' not in st.session_state:
    st.session_state.current_step = 0
if 'show_api_config' not in st.session_state:
    st.session_state.show_api_config = False
if 'api_config_saved' not in st.session_state:
    st.session_state.api_config_saved = False
if 'tts_config' not in st.session_state:
    st.session_state.tts_config = {
        'provider': 'aliyun',
        'appkey': '',
        'token': '',
        'default_voice': 'xiaoyun',
        'voice_mapping': {}  # 角色名 -> 音色ID
    }
if 'config' not in st.session_state:
    # 每次启动时从 .env 重新加载配置（确保手动修改 .env 后能生效）
    config.reload_env()
    # api_config.json 只存储非敏感配置（画风/TTS等），模型名/URL/密钥统一从 .env 读取
    config_path = Path("./api_config.json")
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            saved_api_config = json.load(f)
        st.session_state.config = {
            'shot_count': 5,
            'shot_duration': 5,
            'resolution': '1080p',
            'fps': 24,
            'aspect_ratio': '9:16',
            'style_preset': 'realistic',
            'audio_mode': 'tts',  # tts / seedance_audio / silent
            'enable_subtitle': True,
            'subtitle_lang': 'zh',
            'base_style_prompt': saved_api_config.get('base_style_prompt', config.BASE_STYLE_PROMPT),
            'video_prompt_template': '',
            'action_prompt_template': '',
            'export_mode': 'shots'
        }
    else:
        st.session_state.config = {
            'shot_count': 5,
            'shot_duration': 5,
            'resolution': '1080p',
            'fps': 24,
            'aspect_ratio': '9:16',
            'style_preset': 'realistic',
            'audio_mode': 'tts',  # tts / seedance_audio / silent
            'enable_subtitle': True,
            'subtitle_lang': 'zh',
            'base_style_prompt': config.BASE_STYLE_PROMPT,
            'video_prompt_template': '',
            'action_prompt_template': '',
            'export_mode': 'shots'
        }
if 'script_content' not in st.session_state:
    st.session_state.script_content = ''
if 'current_task_id' not in st.session_state:
    st.session_state.current_task_id = None
if 'shots' not in st.session_state:
    st.session_state.shots = []
if 'resource_mapping' not in st.session_state:
    st.session_state.resource_mapping = {}
if 'generated_videos' not in st.session_state:
    st.session_state.generated_videos = []
if 'show_image_dialog' not in st.session_state:
    st.session_state.show_image_dialog = None


# ==================== 工具函数 ====================
def _update_env_var(key: str, value: str):
    """更新.env文件中的单个环境变量"""
    env_path = Path("./.env")
    lines = []
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            found = True
            break

    if not found:
        lines.append(f"{key}={value}\n")

    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)


def save_api_keys_to_env(deepseek_api_key: str, seedance_api_key: str):
    """保存API密钥到.env文件（密钥的唯一存储位置）"""
    _update_env_var("DEEPSEEK_API_KEY", deepseek_api_key)
    _update_env_var("SEEDANCE_API_KEY", seedance_api_key)
    config.DEEPSEEK_API_KEY = deepseek_api_key
    config.SEEDANCE_API_KEY = seedance_api_key


def save_api_config(deepseek_api_url, deepseek_model,
                   seedance_api_url, seedance_model,
                   base_style_prompt="", tts_config=None):
    """保存API配置到本地文件，同时同步模型名/URL到.env"""
    # 同步模型名/URL到 .env
    _update_env_var("DEEPSEEK_API_URL", deepseek_api_url)
    _update_env_var("DEEPSEEK_MODEL", deepseek_model)
    _update_env_var("SEEDANCE_API_URL", seedance_api_url)
    _update_env_var("SEEDANCE_MODEL", seedance_model)

    config_data = {
        "deepseek_api_url": deepseek_api_url,
        "deepseek_model": deepseek_model,
        "seedance_api_url": seedance_api_url,
        "seedance_model": seedance_model,
        "base_style_prompt": base_style_prompt,
        "tts_config": tts_config or {},
        "saved_at": datetime.now().isoformat()
    }

    config_path = Path("./api_config.json")
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)

    # 同步更新内存中的 config 模块变量
    config.DEEPSEEK_API_URL = deepseek_api_url
    config.DEEPSEEK_MODEL = deepseek_model
    config.SEEDANCE_API_URL = seedance_api_url
    config.SEEDANCE_MODEL = seedance_model

    return True


def load_api_config():
    """从本地文件加载API配置"""
    config_path = Path("./api_config.json")
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def generate_style_prompt(style_preset: str, resolution: str, aspect_ratio: str) -> str:
    """根据预设配置自动生成基础画风提示词"""
    style_prompts = {
        'realistic': f"""
{aspect_ratio}竖屏，写实真人电影质感，{resolution}高清画质，真实生活化镜头，
自然光+电影级柔和光影，色彩色调统一协调，运镜丝滑流畅，
画面真实不浮夸，无卡通感、无AI畸形人体，镜头衔接自然，
末日悬疑氛围感拉满，全程实景真实拍摄风格。
""",
        'anime': f"""
{aspect_ratio}竖屏，日系动漫风格，2D动画质感，精美手绘风格，
色彩鲜艳明亮，线条流畅，人物造型精致可爱，
典型日本动画画风，场景细节丰富，光影效果柔和，
画面清新自然，无写实感，典型二次元美学。
""",
        'cyberpunk': f"""
{aspect_ratio}竖屏，赛博朋克风格，未来科技感，霓虹灯光效，
暗黑色调+高对比度，雨夜城市街景，全息投影广告，
机械元素与人体改造，蒸汽朋客细节，电影级光影，
高科技低生活氛围，强烈的视觉冲击力。
""",
        'watercolor': f"""
{aspect_ratio}竖屏，水彩画风格，手绘质感，色彩温润柔和，
笔触自然流畅，水彩晕染效果，文艺清新气质，
淡雅色调，诗意浪漫氛围，艺术感强烈，
画面温馨治愈，无生硬边缘，典型水彩美学。
""",
        'oil_painting': f"""
{aspect_ratio}竖屏，油画风格，浓厚颜料质感，画布纹理清晰，
色彩饱和浓郁，笔触粗犷有力，光影层次丰富，
古典艺术氛围，印象派技法，强烈的情感表达，
画面厚重有质感，典型油画美学，无数码感。
""",
        'cartoon': f"""
{aspect_ratio}竖屏，卡通动画风格，2D扁平化设计，色彩明快简洁，
线条圆润可爱，人物造型夸张有趣，儿童友好，
轻松幽默氛围，色块分明，无渐变阴影，
典型迪士尼卡通风格，画面干净清爽。
""",
        'scifi': f"""
{aspect_ratio}竖屏，科幻未来风格，太空探索主题，金属质感强烈，
冷色调为主，蓝色紫色光影，高科技设备细节，
太空船、星球、未来城市元素，
强烈的未来感与科技感，电影级特效质感。
""",
        'fantasy': f"""
{aspect_ratio}竖屏，奇幻魔幻风格，魔法元素环绕，光效绚丽多彩，
神秘幽暗色调，古老建筑与自然景观并存，
龙、魔法、精灵等奇幻生物，
史诗级宏大场景，神秘庄严氛围，典型魔幻美学。
"""
    }
    return style_prompts.get(style_preset, style_prompts['realistic'])


# ==================== 主界面 ====================
# 标题
st.markdown('<div class="main-header">🎬 AI短剧自动生成系统</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">从剧本到视频，全流程自动化生成</div>', unsafe_allow_html=True)

# API配置弹窗
if st.session_state.show_api_config:
    st.markdown("---")
    
    # 弹窗标题栏
    col_title, col_close = st.columns([5, 1])
    with col_title:
        st.markdown("## ⚙️ API配置管理")
    with col_close:
        if st.button("❌", key="close_api_config", help="关闭配置"):
            st.session_state.show_api_config = False
            st.rerun()
    
    st.info("💡 提示：配置将保存到本地文件，下次启动自动加载")
    st.divider()
    
    # 加载已有配置
    saved_config = load_api_config()
    saved_tts_config = saved_config.get('tts_config', {}) if saved_config else {}
    
    # Tab页签
    api_tab1, api_tab2, api_tab3 = st.tabs(["🤖 分镜模型", "🎬 视频模型", "🎵 TTS配音"])
    
    with api_tab1:
        with st.form("deepseek_form"):
            col1, col2 = st.columns(2)
            with col1:
                ds_api_key = st.text_input(
                    "API密钥",
                    value=config.DEEPSEEK_API_KEY,
                    type="password",
                    help="用于分镜生成的API密钥（保存在.env文件中）"
                )
                ds_api_url = st.text_input(
                    "API地址",
                    value=config.DEEPSEEK_API_URL,
                    help="例如：https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
                )
            with col2:
                ds_model = st.text_input(
                    "模型名称",
                    value=config.DEEPSEEK_MODEL,
                    help="例如：qwen3.5-flash"
                )

            ds_submitted = st.form_submit_button("💾 保存分镜模型配置", type="primary", width='stretch')

            if ds_submitted:
                if ds_api_key:
                    try:
                        save_api_keys_to_env(ds_api_key, config.SEEDANCE_API_KEY)
                        save_api_config(
                            deepseek_api_url=ds_api_url,
                            deepseek_model=ds_model,
                            seedance_api_url=saved_config.get('seedance_api_url', config.SEEDANCE_API_URL) if saved_config else config.SEEDANCE_API_URL,
                            seedance_model=saved_config.get('seedance_model', config.SEEDANCE_MODEL) if saved_config else config.SEEDANCE_MODEL,
                            base_style_prompt=saved_config.get('base_style_prompt', '') if saved_config else '',
                            tts_config=saved_config.get('tts_config', {}) if saved_config else {}
                        )
                        st.session_state.api_config_saved = True
                        st.success("✅ 分镜模型配置已保存！")
                        st.session_state.show_api_config = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 保存失败：{str(e)}")
                else:
                    st.error("❌ 请填写API密钥")
    
    with api_tab2:
        with st.form("seedance_form"):
            col3, col4 = st.columns(2)
            with col3:
                sd_api_key = st.text_input(
                    "API密钥",
                    value=config.SEEDANCE_API_KEY,
                    type="password",
                    key="seedance_api_key_input",
                    help="用于视频生成的API密钥（保存在.env文件中）"
                )
                sd_api_url = st.text_input(
                    "API地址",
                    value=config.SEEDANCE_API_URL,
                    help="例如：https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
                )
            with col4:
                sd_model = st.text_input(
                    "模型名称",
                    value=config.SEEDANCE_MODEL,
                    help="例如：doubao-seedance-1-0-pro-250528"
                )

            sd_submitted = st.form_submit_button("💾 保存视频模型配置", type="primary", width='stretch')

            if sd_submitted:
                if sd_api_key:
                    try:
                        save_api_keys_to_env(config.DEEPSEEK_API_KEY, sd_api_key)
                        save_api_config(
                            deepseek_api_url=saved_config.get('deepseek_api_url', config.DEEPSEEK_API_URL) if saved_config else config.DEEPSEEK_API_URL,
                            deepseek_model=saved_config.get('deepseek_model', config.DEEPSEEK_MODEL) if saved_config else config.DEEPSEEK_MODEL,
                            seedance_api_url=sd_api_url,
                            seedance_model=sd_model,
                            base_style_prompt=saved_config.get('base_style_prompt', '') if saved_config else '',
                            tts_config=saved_config.get('tts_config', {}) if saved_config else {}
                        )
                        st.session_state.api_config_saved = True
                        st.success("✅ 视频模型配置已保存！")
                        st.session_state.show_api_config = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 保存失败：{str(e)}")
                else:
                    st.error("❌ 请填写API密钥")
    
    with api_tab3:
        with st.form("tts_form"):
            st.markdown("### 🎵 TTS配音配置")
            
            # TTS服务商选择
            tts_provider = st.selectbox(
                "TTS服务商",
                options=["aliyun", "xunfei", "azure"],
                index=0,
                format_func=lambda x: {"aliyun": "阿里云TTS", "xunfei": "讯飞TTS", "azure": "Azure TTS"}[x],
                help="选择TTS配音服务商"
            )
            
            st.divider()
            
            # 阿里云配置
            if tts_provider == "aliyun":
                st.markdown("#### 阿里云TTS配置")
                tts_appkey = st.text_input(
                    "AppKey",
                    value=saved_tts_config.get('appkey', ''),
                    type="password",
                    help="阿里云TTS AppKey"
                )
                tts_token = st.text_input(
                    "Token",
                    value=saved_tts_config.get('token', ''),
                    type="password",
                    help="阿里云TTS Token"
                )
            
            st.divider()
            
            # 音色配置
            st.markdown("#### 🎤 音色配置")
            
            # 获取可用音色
            from tts_service import get_tts_service
            tts_service = get_tts_service(tts_provider)
            all_voices = tts_service.get_available_voices()
            
            # 检查是否获取到音色
            if not all_voices:
                st.warning("⚠️ 未获取到音色列表")
                st.info("📌 请先在上方配置TTS服务商的API密钥，保存后会自动加载音色列表")
                
                # 不显示后续的音色选择
                default_voice = None
                voice_mapping = {}
            else:
                st.success(f"✅ 已加载 {len(all_voices)} 个音色")
                
                # 分类筛选
                categories = list(set(v.get('category', '其他') for v in all_voices))
                categories.sort()
                
                st.markdown("##### 筛选条件")
                col_filter1, col_filter2 = st.columns(2)
                
                with col_filter1:
                    selected_category = st.selectbox(
                        "音色分类",
                        options=["全部"] + categories,
                        help="按分类筛选音色"
                    )
                
                with col_filter2:
                    gender_filter = st.selectbox(
                        "性别筛选",
                        options=["全部", "男", "女"],
                        help="按性别筛选音色"
                    )
                
                # 搜索框
                search_keyword = st.text_input(
                    "🔍 搜索音色",
                    placeholder="输入音色名称、ID或风格关键词...",
                    help="支持搜索：音色名称、ID、风格描述"
                )
                
                # 应用筛选
                filtered_voices = all_voices
                
                if selected_category != "全部":
                    filtered_voices = [v for v in filtered_voices if v.get('category') == selected_category]
                
                if gender_filter != "全部":
                    filtered_voices = [v for v in filtered_voices if v.get('gender') == gender_filter]
                
                if search_keyword:
                    keyword = search_keyword.lower()
                    filtered_voices = [
                        v for v in filtered_voices
                        if keyword in v['id'].lower() or 
                           keyword in v['name'].lower() or 
                           keyword in v.get('style', '').lower()
                    ]
                
                # 显示筛选结果统计
                st.caption(f"找到 {len(filtered_voices)} 个音色")
                
                # 默认音色
                st.markdown("##### 默认音色（未配置角色使用）")
                
                if filtered_voices:
                    default_voice_options = [v['id'] for v in filtered_voices]
                    default_voice = st.selectbox(
                        "选择默认音色",
                        options=default_voice_options,
                        format_func=lambda x: next((f"{v['name']} ({v['gender']}) - {v['style']}" for v in filtered_voices if v['id'] == x), x),
                        index=0 if all_voices[0]['id'] in default_voice_options else 0,
                        help="未配置角色音色时使用的默认音色"
                    )
                else:
                    st.warning("没有找到符合条件的音色")
                    default_voice = all_voices[0]['id'] if all_voices else None
                
                # 角色音色映射
                st.markdown("##### 角色音色映射")
                st.caption("为每个角色分配不同的音色")
                
                voice_mapping = {}
                if st.session_state.shots:
                    # 提取所有角色
                    all_roles = set()
                    for shot in st.session_state.shots:
                        all_roles.update(shot.get('roles', []))
                    
                    if all_roles:
                        # 显示音色选择器
                        with st.expander("🎤 角色音色配置", expanded=True):
                            for role in sorted(all_roles):
                                col_role, col_voice, col_preview = st.columns([1, 3, 1])
                                with col_role:
                                    st.markdown(f"👤 **{role}**")
                                with col_voice:
                                    selected_voice = st.selectbox(
                                        f"voice_{role}",
                                        options=["使用默认"] + [v['id'] for v in all_voices],
                                        format_func=lambda x: x if x == "使用默认" else next((f"{v['name']} ({v['gender']}) - {v['style']}" for v in all_voices if v['id'] == x), x),
                                        label_visibility="collapsed",
                                        key=f"voice_select_{role}"
                                    )
                                    if selected_voice != "使用默认":
                                        voice_mapping[role] = selected_voice
                                with col_preview:
                                    if st.button("🔊 试听", key=f"preview_{role}"):
                                        st.info("试听功能需要接入真实TTS API")
            
            tts_submitted = st.form_submit_button("💾 保存TTS配置", type="primary", width='stretch')
            
            if tts_submitted:
                # 保存TTS配置
                tts_config = {
                    'provider': tts_provider,
                    'appkey': tts_appkey if tts_provider == 'aliyun' else '',
                    'token': tts_token if tts_provider == 'aliyun' else '',
                    'default_voice': default_voice,
                    'voice_mapping': voice_mapping
                }
                
                # 更新session_state
                st.session_state.tts_config = tts_config

                # 同步TTS密钥到.env
                _update_env_var("TTS_PROVIDER", tts_provider)
                _update_env_var("TTS_ALIYUN_APPKEY", tts_appkey)
                _update_env_var("TTS_ALIYUN_TOKEN", tts_token)
                config.reload_env()

                # 保存到api_config.json（非敏感配置）
                save_api_config(
                    deepseek_api_url=saved_config.get('deepseek_api_url', config.DEEPSEEK_API_URL) if saved_config else config.DEEPSEEK_API_URL,
                    deepseek_model=saved_config.get('deepseek_model', config.DEEPSEEK_MODEL) if saved_config else config.DEEPSEEK_MODEL,
                    seedance_api_url=saved_config.get('seedance_api_url', config.SEEDANCE_API_URL) if saved_config else config.SEEDANCE_API_URL,
                    seedance_model=saved_config.get('seedance_model', config.SEEDANCE_MODEL) if saved_config else config.SEEDANCE_MODEL,
                    base_style_prompt=saved_config.get('base_style_prompt', '') if saved_config else '',
                    tts_config=tts_config
                )
                
                st.success("✅ TTS配置已保存！")
                time.sleep(1)
                st.session_state.show_api_config = False
                st.rerun()
    
    # 弹窗底部关闭按钮
    st.divider()
    col_center, = st.columns([1])
    with col_center:
        if st.button("❌ 关闭配置", width='stretch', type="secondary"):
            st.session_state.show_api_config = False
            st.rerun()
    
    st.markdown("---")

# 步骤导航
steps = ["⚙️ 参数配置", "📝 输入剧本", "✏️ 编辑分镜", "🔗 关联资源", "🎬 生成视频", "✅ 检查导出"]
current_step = st.session_state.current_step

# 步骤条
step_container = st.container()
with step_container:
    cols = st.columns(len(steps))
    for i, (col, step_name) in enumerate(zip(cols, steps)):
        with col:
            if i < current_step:
                st.success(step_name, icon="✅")
            elif i == current_step:
                st.info(step_name, icon="▶️")
            else:
                st.write(step_name)


def _copy_to_pool_images(src_path: str, name: str) -> str:
    """将图片复制到 resource_pool/images/ 目录，返回目标路径"""
    images_dir = os.path.join(str(config.RESOURCE_POOL_DIR), "images")
    os.makedirs(images_dir, exist_ok=True)
    ext = os.path.splitext(src_path)[1] or ".png"
    dest = os.path.join(images_dir, f"{name}{ext}")
    if os.path.abspath(src_path) != os.path.abspath(dest):
        shutil.copy2(src_path, dest)
    return dest


# ==================== 步骤0: 参数配置 ====================
if current_step == 0:
    st.markdown("## ⚙️ 视频生成配置")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📊 基本参数")
        st.session_state.config['shot_count'] = st.number_input(
            "分镜数量", 
            min_value=1, 
            max_value=50, 
            value=st.session_state.config['shot_count'],
            help="将剧本拆分为多少个分镜"
        )
        
        st.session_state.config['shot_duration'] = st.number_input(
            "单分镜时长（秒）", 
            min_value=3, 
            max_value=10, 
            value=st.session_state.config['shot_duration'],
            help="每个分镜视频的时长"
        )
        
        st.session_state.config['resolution'] = st.selectbox(
            "分辨率",
            options=["480p", "720p", "1080p", "2K", "4K"],
            index=["480p", "720p", "1080p", "2K", "4K"].index(st.session_state.config['resolution']) if st.session_state.config['resolution'] in ["480p", "720p", "1080p", "2K", "4K"] else 2,
            help="视频输出分辨率"
        )
        
        st.session_state.config['fps'] = st.selectbox(
            "帧率",
            options=[24, 30, 60],
            index=[24, 30, 60].index(st.session_state.config['fps']),
            help="视频帧率（24fps=电影感，30fps=标准，60fps=流畅）"
        )
    
    with col2:
        st.markdown("### 🎨 画面设置")
        st.session_state.config['aspect_ratio'] = st.selectbox(
            "画面比例",
            options=["9:16", "16:9", "1:1"],
            index=["9:16", "16:9", "1:1"].index(st.session_state.config['aspect_ratio']),
            help="9:16=竖屏，16:9=横屏，1:1=方形"
        )
        
        st.session_state.config['style_preset'] = st.selectbox(
            "画风预设",
            options=["realistic", "anime", "cyberpunk", "watercolor", "oil_painting", "cartoon", "scifi", "fantasy"],
            index=["realistic", "anime", "cyberpunk", "watercolor", "oil_painting", "cartoon", "scifi", "fantasy"].index(st.session_state.config['style_preset']) if st.session_state.config['style_preset'] in ["realistic", "anime", "cyberpunk", "watercolor", "oil_painting", "cartoon", "scifi", "fantasy"] else 0,
            format_func=lambda x: {
                'realistic': '写实真人电影',
                'anime': '日系动漫',
                'cyberpunk': '赛博朋克',
                'watercolor': '水彩画',
                'oil_painting': '油画风格',
                'cartoon': '卡通动画',
                'scifi': '科幻未来',
                'fantasy': '奇幻魔幻'
            }[x],
            key="style_preset_select"
        )
    
    st.divider()
    
    col3, col4 = st.columns(2)
    with col3:
        st.markdown("### 🎵 音频配置")
        
        # 音频模式选择
        audio_mode = st.selectbox(
            "音频生成模式",
            options=["tts", "seedance_audio", "silent"],
            format_func=lambda x: {
                "tts": "🎤 TTS配音（推荐）- 清晰对话 + 背景音",
                "seedance_audio": "🎬 AI自动生成 - 背景音 + 模糊对话",
                "silent": "🔇 完全静音 - 仅视频无音频"
            }[x],
            index=0,
            help="选择音频生成方式：TTS配音质量最高，AI自动生成最简单，静音模式适合后期配音"
        )
        
        # 保存音频模式到配置
        st.session_state.config['audio_mode'] = audio_mode
        
        # 根据模式显示不同配置
        if audio_mode == "tts":
            st.success("✅ TTS配音模式：视频模型生成背景音，TTS生成清晰对话")
            st.caption("📌 需要在API配置中设置TTS音色")
        elif audio_mode == "seedance_audio":
            st.info("ℹ️ AI自动生成：Seedance自动识别场景生成背景音和对话")
            st.caption("📌 对话不清晰，但音画同步")
        else:
            st.warning("⚠️ 静音模式：生成的视频没有声音")
            st.caption("📌 适合后期手动添加配音")
        
        st.session_state.config['enable_subtitle'] = st.toggle(
            "启用字幕", 
            value=st.session_state.config['enable_subtitle'],
            help="是否添加字幕"
        )
    
    with col4:
        if st.session_state.config['enable_subtitle']:
            st.session_state.config['subtitle_lang'] = st.selectbox(
                "字幕语言",
                options=["zh", "en", "zh_jp"],
                index=["zh", "en", "zh_jp"].index(st.session_state.config['subtitle_lang']),
                format_func=lambda x: {'zh': '中文', 'en': 'English', 'zh_jp': '中日双语'}[x]
            )
        else:
            st.markdown("")  # 占位保持对齐

        st.markdown("### 📦 输出模式")
        st.session_state.config['export_mode'] = st.radio(
            "选择输出方式",
            options=["shots", "merged"],
            format_func=lambda x: "分镜视频（单独输出每个分镜）" if x == "shots" else "完整剪辑（合并所有分镜为一个视频）",
            horizontal=True,
            index=0 if st.session_state.config.get('export_mode', 'shots') == 'shots' else 1
        )

    st.divider()
    
    st.markdown("### 📝 提示词配置")
    
    # 自动生成按钮
    if st.button("🔄 根据预设配置生成模板", type="primary"):
        st.session_state.config['base_style_prompt'] = generate_style_prompt(
            st.session_state.config['style_preset'],
            st.session_state.config['resolution'],
            st.session_state.config['aspect_ratio']
        )
        st.success("✅ 已生成基础画风提示词模板，您可以在下方自定义修改！")
        st.rerun()
    
    st.session_state.config['base_style_prompt'] = st.text_area(
        "基础画风提示词",
        value=st.session_state.config['base_style_prompt'],
        height=100,
        help="全局画风描述，会添加到每个分镜提示词中。点击上方按钮可根据预设自动生成模板。"
    )
    
    st.session_state.config['video_prompt_template'] = st.text_area(
        "视频提示词模板（可选）",
        value=st.session_state.config.get('video_prompt_template', ''),
        height=80,
        help="视频生成的提示词模板"
    )
    
    st.session_state.config['action_prompt_template'] = st.text_area(
        "动作提示词模板（可选）",
        value=st.session_state.config.get('action_prompt_template', ''),
        height=80,
        help="动作描述的提示词模板"
    )
    
    st.divider()
    
    col5, col6 = st.columns([1, 1])
    with col5:
        if st.button("下一步 →", type="primary", width='stretch'):
            st.session_state.current_step = 1
            st.rerun()


# ==================== 步骤1: 输入剧本 ====================
elif current_step == 1:
    st.markdown("## 📝 输入剧本内容")
    
    st.session_state.script_content = st.text_area(
        "剧本内容",
        value=st.session_state.script_content,
        height=300,
        placeholder="请输入剧本内容...\n\n例如：\n男主A在海边度假酒店的豪华大床上清晨醒来，阳光透过落地窗洒进房间。\n他拿起手机，看到家人发来的紧急消息，神情变得凝重。",
        help="输入完整的剧本文本，系统会自动拆分为分镜"
    )
    
    # 显示当前配置
    st.markdown("### 📊 当前配置")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("分镜数量", st.session_state.config['shot_count'])
    with col2:
        st.metric("单镜时长", f"{st.session_state.config['shot_duration']}秒")
    with col3:
        st.metric("分辨率", st.session_state.config['resolution'])
    with col4:
        st.metric("画风", st.session_state.config['style_preset'])
    
    st.divider()
    
    col5, col6, col7 = st.columns([1, 1, 1])
    with col5:
        if st.button("← 上一步", width='stretch'):
            st.session_state.current_step = 0
            st.rerun()
    with col6:
        if st.button("🧪 加载示例分镜", width='stretch', help="跳过LLM调用，直接加载示例分镜数据测试完整流程"):
            sample_path = Path("./test/sample_shots.json")
            if sample_path.exists():
                with open(sample_path, 'r', encoding='utf-8') as f:
                    st.session_state.shots = json.load(f)
                # 创建新任务
                st.session_state.current_task_id = task_manager.create_task(
                    script_preview="[示例分镜]",
                    shot_count=len(st.session_state.shots)
                )
                # 清除旧的角色映射
                st.session_state.global_char_mapping = {}
                st.session_state.global_char_descs = {}
                st.session_state.global_voice_mapping = {}
                st.session_state.resource_mapping = {}
                # 保存分镜到任务目录
                with open(task_manager.shots_path(st.session_state.current_task_id), 'w', encoding='utf-8') as f:
                    json.dump(st.session_state.shots, f, ensure_ascii=False, indent=2)
                st.success(f"✅ 已加载 {len(st.session_state.shots)} 个示例分镜（零Token消耗）")
                st.session_state.current_step = 2
                st.rerun()
            else:
                st.error("示例分镜文件不存在: test/sample_shots.json")
    with col7:
        if st.button("生成分镜 →", type="primary", width='stretch'):
            if not st.session_state.script_content.strip():
                st.error("请先输入剧本内容！")
            else:
                # 检查剧本长度
                script_length = len(st.session_state.script_content)
                if script_length > 5000:
                    st.warning(f"⚠️ 剧本内容较长（{script_length}字），生成可能需要3-5分钟，请耐心等待")
                elif script_length > 2000:
                    st.info(f"📝 剧本长度适中（{script_length}字），生成约需要1-3分钟")
                
                with st.spinner("🎬 正在调用AI生成分镜，请稍候..."):
                    try:
                        # 显示进度信息
                        progress_text = st.empty()
                        progress_text.info("📡 正在连接AI服务...")

                        start_time = time.time()

                        # 创建新任务
                        st.session_state.current_task_id = task_manager.create_task(
                            script_preview=st.session_state.script_content[:200],
                            shot_count=st.session_state.config['shot_count']
                        )

                        shots = generate_shots_from_script(
                            st.session_state.script_content,
                            st.session_state.config['shot_count'],
                            episode_num=1,
                            user_config=st.session_state.config,
                            task_id=st.session_state.current_task_id
                        )

                        task_manager.update_task(st.session_state.current_task_id,
                                                 shot_count=len(shots),
                                                 status="shots_generated")

                        elapsed = time.time() - start_time
                        progress_text.success(f"✅ AI返回成功（耗时{elapsed:.1f}秒），正在解析分镜...")

                        st.session_state.shots = shots
                        # 清除旧的角色映射（新分镜可能有不同的角色）
                        st.session_state.global_char_mapping = {}
                        st.session_state.global_char_descs = {}
                        st.session_state.global_voice_mapping = {}
                        st.session_state.resource_mapping = {}
                        st.success(f"✅ 成功生成 {len(shots)} 个分镜！")
                        st.session_state.current_step = 2
                        st.rerun()
                    except requests.exceptions.Timeout:
                        st.error("❌ AI服务响应超时（超过5分钟）\n💡 建议：\n1. 减少剧本内容长度（建议2000字以内）\n2. 减少分镜数量（建议5-10个）\n3. 稍后重试")
                    except requests.exceptions.ConnectionError:
                        st.error("❌ 无法连接到AI服务，请检查网络连接")
                    except Exception as e:
                        st.error(f"❌ 分镜生成失败：{str(e)}")


# ==================== 步骤2: 编辑分镜 ====================
elif current_step == 2:
    st.markdown("## ✏️ 编辑分镜提示词")
    
    if not st.session_state.shots:
        st.warning("暂无分镜数据，请先返回上一步生成分镜")
    else:
        st.info(f"共 {len(st.session_state.shots)} 个分镜，可以编辑每个分镜的提示词")
        
        for i, shot in enumerate(st.session_state.shots):
            with st.expander(f"📽️ 分镜 {shot['shot_id']}", expanded=(i==0)):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    shot['shot_prompt'] = st.text_area(
                        "分镜提示词",
                        value=shot['shot_prompt'],
                        height=100,
                        key=f"prompt_{i}"
                    )
                    # 旁白编辑
                    narration = shot.get('narration', '')
                    shot['narration'] = st.text_area(
                        "旁白（可选）",
                        value=narration,
                        height=60,
                        placeholder="输入旁白文本，Seedance/TTS将为其生成语音...",
                        key=f"narration_{i}"
                    )
                    # 对话显示（只读）
                    dialogue = shot.get('dialogue', [])
                    if dialogue:
                        dialogue_text = "\n".join([f"{d['role']}: {d['text']}" for d in dialogue])
                        st.text_area(
                            "对话",
                            value=dialogue_text,
                            height=60,
                            key=f"dialogue_display_{i}",
                            disabled=True
                        )
                
                with col2:
                    st.markdown("**出场角色**")
                    roles = shot.get('roles', [])
                    for role in roles:
                        st.markdown(f"👤 {role}")
        
        st.divider()
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("← 上一步", width='stretch'):
                st.session_state.current_step = 1
                st.rerun()
        with col3:
            if st.button("下一步：关联资源 →", type="primary", width='stretch'):
                st.session_state.current_step = 3
                st.rerun()


# ==================== 步骤3: 关联资源 ====================
elif current_step == 3:
    st.markdown("## 🔗 关联资源池")
    
    # 初始化资源池（使用全局单例）
    char_pool = get_character_pool()
    scene_pool = get_scene_pool()
    prop_pool = get_prop_pool()

    # 获取所有资源
    all_characters = char_pool.get_all()
    all_scenes = scene_pool.get_all()
    all_props = prop_pool.get_all()
    
    if not all_characters and not all_scenes and not all_props:
        st.info("💡 资源池为空，您可以：")
        st.markdown("""
        1. **跳过资源关联** - 直接生成视频（AI会根据提示词自动生成）
        2. **添加资源** - 在下方添加角色、场景、物品供后续使用
        """)
        
        st.divider()
    
    # ========== 资源池管理（4列网格布局） ==========

    COLS_PER_ROW = 4
    MAX_ROWS = 3
    MAX_VISIBLE = COLS_PER_ROW * MAX_ROWS  # 12

    def _render_resource_card(item, pool, res_type):
        """渲染单个资源卡片"""
        img_path = item.get('image_path', '')
        # 图片
        if img_path and os.path.exists(img_path):
            st.image(img_path, width='stretch')
        else:
            icon_map = {"char": "🎭", "scene": "🎬", "prop": "🎒"}
            icon = icon_map.get(res_type, "📷")
            st.markdown(
                f"<div style='background:#f5f5f5;aspect-ratio:1;display:flex;"
                f"align-items:center;justify-content:center;border-radius:8px;"
                f"min-height:100px;'><span style='font-size:2.5em;'>{icon}</span></div>",
                unsafe_allow_html=True
            )
        # 名称
        st.markdown(
            f"<div style='text-align:center;font-weight:600;font-size:0.85em;"
            f"margin:6px 0 2px 0;word-break:break-all;'>{item['name']}</div>",
            unsafe_allow_html=True
        )
        # 标签（仅角色）
        tags = item.get('tags', [])
        if tags:
            st.markdown(
                f"<div style='text-align:center;font-size:0.7em;color:#999;'>"
                f"{', '.join(tags[:3])}</div>",
                unsafe_allow_html=True
            )
        # 操作按钮
        c1, c2 = st.columns(2)
        with c1:
            if img_path and os.path.exists(img_path):
                if st.button("🔍", key=f"prev_{res_type}_{item['id']}", width='stretch'):
                    st.session_state.show_image_dialog = img_path
                    st.rerun()
        with c2:
            if st.button("🗑️", key=f"del_{res_type}_{item['id']}", width='stretch'):
                pool.delete(item['id'])
                st.rerun()

    def _render_resource_grid(items, pool, res_type):
        """渲染资源网格：4列 × 最多3行，超出折叠"""
        if not items:
            return
        visible = items[:MAX_VISIBLE]
        hidden = items[MAX_VISIBLE:]
        for row_start in range(0, len(visible), COLS_PER_ROW):
            row_items = visible[row_start:row_start + COLS_PER_ROW]
            cols = st.columns(COLS_PER_ROW)
            for col_idx, item in enumerate(row_items):
                with cols[col_idx]:
                    with st.container(border=True):
                        _render_resource_card(item, pool, res_type)
        if hidden:
            with st.expander(f"📦 其他（{len(hidden)}个）"):
                for row_start in range(0, len(hidden), COLS_PER_ROW):
                    row_items = hidden[row_start:row_start + COLS_PER_ROW]
                    cols = st.columns(COLS_PER_ROW)
                    for col_idx, item in enumerate(row_items):
                        with cols[col_idx]:
                            with st.container(border=True):
                                _render_resource_card(item, pool, res_type)

    def _render_resource_section(icon, title, items, pool, res_type, show_key, form_key):
        """渲染一个完整的资源区域：标题栏 + 网格 + 添加按钮 + 添加表单"""
        # 标题栏
        col_h1, col_h2 = st.columns([3, 1])
        with col_h1:
            st.markdown(f"#### {icon} {title}（{len(items)}个）")
        with col_h2:
            if st.button(f"➕ 添加", width='stretch', key=f"add_btn_{res_type}"):
                st.session_state[show_key] = True
                st.rerun()

        # 资源网格
        _render_resource_grid(items, pool, res_type)

        # 空状态
        if not items:
            st.info(f"💡 暂无{title.replace('池', '')}，点击上方「➕ 添加」按钮添加")

        # 添加表单
        if st.session_state.get(show_key):
            st.divider()
            st.markdown(f"##### {icon} 添加{title.replace('池', '')}")
            _render_add_form(res_type, pool, show_key, form_key)

    def _render_add_form(res_type, pool, show_key, form_key):
        """渲染添加资源表单"""
        if res_type == "char":
            _render_add_character_form(pool, show_key, form_key)
        elif res_type == "scene":
            _render_add_scene_form(pool, show_key, form_key)
        elif res_type == "prop":
            _render_add_prop_form(pool, show_key, form_key)

    def _render_add_character_form(pool, show_key, form_key):
        """角色添加表单"""
        # 文件上传（表单外，响应式）
        uploaded_file = st.file_uploader(
            "📁 上传角色图片（点击或拖拽）",
            type=['jpg', 'jpeg', 'png'],
            key="char_uploader",
            help="选择角色的参考图片"
        )
        uploaded_path = ""
        if uploaded_file is not None:
            import tempfile
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, uploaded_file.name)
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.image(temp_path, width=150)
            st.caption(f"✅ 已选择: {uploaded_file.name}")
            uploaded_path = temp_path

        with st.form(form_key):
            col1, col2 = st.columns(2)
            with col1:
                char_name = st.text_input("角色名称 *", placeholder="例如：小垚")
                appearance_template = st.selectbox(
                    "外观模板（可选）",
                    ["自定义", "男性，25-30岁，短发，身材高大，五官立体",
                     "女性，20-25岁，长发，身材苗条，气质优雅",
                     "男性，30-40岁，成熟稳重，胡须，西装革履",
                     "女性，25-35岁，职业装，干练短发",
                     "男性，18-22岁，阳光帅气，运动装"],
                    index=0, help="选择预设模板或自定义"
                )
                if appearance_template != "自定义":
                    char_appearance = st.text_area("外观描述", value=appearance_template, label_visibility="collapsed")
                else:
                    char_appearance = st.text_area("外观描述", placeholder="例如：男性，25岁，短发，身材高大", label_visibility="collapsed")
            with col2:
                char_clothes = st.text_input("服装描述", placeholder="例如：休闲装、西装")
                char_character = st.text_input("性格描述", placeholder="例如：活泼开朗、沉稳冷静")
            char_image = st.text_input("图片路径 *", value=uploaded_path, placeholder="上传图片或手动输入路径")
            char_tags = st.text_input("标签（逗号分隔）", placeholder="例如：主角,现代")

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.form_submit_button("✅ 添加", type="primary"):
                    image_path = uploaded_path or char_image
                    if char_name and image_path:
                        try:
                            dest_path = _copy_to_pool_images(image_path, char_name)
                            pool.add(
                                name=char_name, appearance=char_appearance,
                                clothes=char_clothes, character=char_character,
                                image_path=dest_path,
                                tags=[t.strip() for t in char_tags.split(",") if t.strip()]
                            )
                            st.success(f"✅ 角色 '{char_name}' 添加成功！")
                            st.session_state[show_key] = False
                            st.rerun()
                        except ValueError as e:
                            st.error(f"❌ {e}")
                    else:
                        st.error("❌ 请填写角色名称和选择图片")
            with col_btn2:
                if st.form_submit_button("❌ 取消"):
                    st.session_state[show_key] = False
                    st.rerun()

    def _render_add_scene_form(pool, show_key, form_key):
        """场景添加表单"""
        uploaded_file = st.file_uploader(
            "📁 上传场景图片（点击或拖拽）",
            type=['jpg', 'jpeg', 'png'],
            key="scene_uploader",
            help="选择场景的参考图片"
        )
        uploaded_path = ""
        if uploaded_file is not None:
            import tempfile
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, uploaded_file.name)
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.image(temp_path, width=200)
            st.caption(f"✅ 已选择: {uploaded_file.name}")
            uploaded_path = temp_path

        with st.form(form_key):
            scene_name = st.text_input("场景名称 *", placeholder="例如：海边")
            scene_template = st.selectbox(
                "场景模板（可选）",
                ["自定义", "阳光明媚的海滩，蓝天白云，海浪拍打沙滩",
                 "繁华的城市街道，夜晚霓虹灯，车水马龙",
                 "安静的咖啡馆，温馨舒适，轻音乐",
                 "现代化的办公室，落地窗，城市景观",
                 "豪华酒店大堂，金碧辉煌，水晶吊灯",
                 "公园花园，春暖花开，鸟语花香"],
                index=0, help="选择预设模板或自定义"
            )
            if scene_template != "自定义":
                scene_desc = st.text_area("场景描述", value=scene_template, label_visibility="collapsed")
            else:
                scene_desc = st.text_area("场景描述", placeholder="例如：阳光明媚的海滩", label_visibility="collapsed")
            scene_image = st.text_input("图片路径 *", value=uploaded_path, placeholder="上传图片或手动输入路径")

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.form_submit_button("✅ 添加", type="primary"):
                    image_path = uploaded_path or scene_image
                    if scene_name and image_path:
                        try:
                            dest_path = _copy_to_pool_images(image_path, scene_name)
                            pool.add(name=scene_name, description=scene_desc, image_path=dest_path)
                            st.success(f"✅ 场景 '{scene_name}' 添加成功！")
                            st.session_state[show_key] = False
                            st.rerun()
                        except ValueError as e:
                            st.error(f"❌ {e}")
                    else:
                        st.error("❌ 请填写场景名称和选择图片")
            with col_btn2:
                if st.form_submit_button("❌ 取消"):
                    st.session_state[show_key] = False
                    st.rerun()

    def _render_add_prop_form(pool, show_key, form_key):
        """物品添加表单"""
        uploaded_file = st.file_uploader(
            "📁 上传物品图片（点击或拖拽）",
            type=['jpg', 'jpeg', 'png'],
            key="prop_uploader",
            help="选择物品的参考图片"
        )
        uploaded_path = ""
        if uploaded_file is not None:
            import tempfile
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, uploaded_file.name)
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.image(temp_path, width=150)
            st.caption(f"✅ 已选择: {uploaded_file.name}")
            uploaded_path = temp_path

        with st.form(form_key):
            prop_name = st.text_input("物品名称 *", placeholder="例如：手机")
            prop_template = st.selectbox(
                "物品模板（可选）",
                ["自定义", "智能手机，黑色，最新款，高清屏幕",
                 "豪华轿车，黑色，流线型设计",
                 "笔记本电脑，银色，轻薄便携",
                 "文件袋，牛皮纸，机密文件",
                 "手表，名牌，金属表带",
                 "包包，时尚，真皮材质"],
                index=0, help="选择预设模板或自定义"
            )
            if prop_template != "自定义":
                prop_desc = st.text_area("物品描述", value=prop_template, label_visibility="collapsed")
            else:
                prop_desc = st.text_area("物品描述", placeholder="例如：iPhone 15 Pro", label_visibility="collapsed")
            prop_image = st.text_input("图片路径 *", value=uploaded_path, placeholder="上传图片或手动输入路径")

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.form_submit_button("✅ 添加", type="primary"):
                    image_path = uploaded_path or prop_image
                    if prop_name and image_path:
                        try:
                            dest_path = _copy_to_pool_images(image_path, prop_name)
                            pool.add(name=prop_name, description=prop_desc, image_path=dest_path)
                            st.success(f"✅ 物品 '{prop_name}' 添加成功！")
                            st.session_state[show_key] = False
                            st.rerun()
                        except ValueError as e:
                            st.error(f"❌ {e}")
                    else:
                        st.error("❌ 请填写物品名称和选择图片")
            with col_btn2:
                if st.form_submit_button("❌ 取消"):
                    st.session_state[show_key] = False
                    st.rerun()

    # ---- 角色池 ----
    _render_resource_section(
        "🎭", "角色池", all_characters, char_pool, "char",
        "show_add_character", "add_char_form"
    )

    st.divider()

    # ---- 场景池 ----
    _render_resource_section(
        "🎬", "场景池", all_scenes, scene_pool, "scene",
        "show_add_scene", "add_scene_form"
    )

    st.divider()

    # ---- 物品池 ----
    _render_resource_section(
        "🎒", "物品池", all_props, prop_pool, "prop",
        "show_add_prop", "add_prop_form"
    )

    # 图片放大预览
    if st.session_state.get('show_image_dialog'):
        image_path = st.session_state.show_image_dialog
        if os.path.exists(image_path):
            st.divider()
            st.markdown("### 🔍 图片预览")
            st.image(image_path, width='stretch')
            if st.button("❌ 关闭预览", width='stretch'):
                st.session_state.show_image_dialog = None
                st.rerun()
        else:
            st.session_state.show_image_dialog = None

    st.divider()

    # ========== 收集所有分镜中的唯一角色名 ==========
    all_shot_roles = set()
    for shot in st.session_state.shots:
        all_shot_roles.update(shot.get('roles', []))
    all_shot_roles = sorted(all_shot_roles)

    # 初始化全局角色映射 session state
    if 'global_char_mapping' not in st.session_state:
        st.session_state.global_char_mapping = {}
    if 'global_char_descs' not in st.session_state:
        st.session_state.global_char_descs = {}

    # ========== 两个Tab：全局角色映射 + 分镜场景物品 ==========
    tab1, tab2 = st.tabs(["🎭 全局角色映射", "🎬 分镜场景/物品"])

    with tab1:
        if not all_shot_roles:
            st.info("未在分镜中检测到角色信息")
        else:
            st.info(f"从所有分镜中检测到 {len(all_shot_roles)} 个角色：{'、'.join(all_shot_roles)}")
            st.caption("每个角色只需要配置一次，所有分镜共享此映射")

            # 获取可用声线列表（TTS模式）
            audio_mode = st.session_state.config.get('audio_mode', 'tts')
            available_voices = None
            if audio_mode == 'tts':
                from tts_service import get_tts_service
                try:
                    tts_service = get_tts_service()
                    available_voices = tts_service.get_available_voices()
                except Exception:
                    available_voices = []
                if not available_voices:
                    available_voices = config.DEFAULT_VOICE_OPTIONS  # 未配置TTS密钥时用默认列表
                st.caption(f"🎤 已加载 {len(available_voices)} 个可用声线")

            # 初始化声线映射
            if 'global_voice_mapping' not in st.session_state:
                st.session_state.global_voice_mapping = {}

            for role_name in all_shot_roles:
                with st.container():
                    st.markdown(f"### 👤 {role_name}")
                    col_left, col_right = st.columns([1, 2])

                    with col_left:
                        # 检查角色库中是否有同名角色
                        matched = [c for c in all_characters if c['name'] == role_name]
                        if matched:
                            st.success("✅ 角色库中有同名角色")
                            img_path = matched[0].get('image_path', '')
                            if img_path and os.path.exists(img_path):
                                st.image(img_path, width=120)
                        else:
                            st.warning("角色库中未找到")

                        # 映射下拉框
                        pool_options = ["🤖 AI自动生成"] + [c['name'] for c in all_characters]
                        current_mapped = st.session_state.global_char_mapping.get(role_name)
                        default_idx = 0
                        if current_mapped and current_mapped in [c['name'] for c in all_characters]:
                            default_idx = [c['name'] for c in all_characters].index(current_mapped) + 1
                        elif matched:
                            default_idx = [c['name'] for c in all_characters].index(role_name) + 1

                        selected = st.selectbox(
                            "映射到角色库",
                            options=pool_options,
                            index=default_idx,
                            key=f"global_map_{role_name}"
                        )

                        if selected != "🤖 AI自动生成":
                            st.session_state.global_char_mapping[role_name] = selected
                        elif role_name in st.session_state.global_char_mapping:
                            del st.session_state.global_char_mapping[role_name]

                    with col_right:
                        mapped_char = st.session_state.global_char_mapping.get(role_name)
                        if mapped_char:
                            char_data = next((c for c in all_characters if c['name'] == mapped_char), None)
                            if char_data:
                                st.markdown(f"**📌 已映射到:** {mapped_char}")
                                st.markdown(f"- 外观: {char_data.get('appearance', '无')}")
                                st.markdown(f"- 服装: {char_data.get('clothes', '无')}")
                                st.markdown(f"- 性格: {char_data.get('character', '无')}")
                                st.caption("视频生成时将自动引用角色库中的外观描述和参考图")
                        else:
                            st.markdown("**🤖 AI自动生成角色**")
                            st.caption("为该角色编写外观描述，AI会根据描述生成一致的人物形象")

                            default_desc = st.session_state.global_char_descs.get(role_name, '')
                            desc = st.text_area(
                                f"{role_name} 外观描述",
                                value=default_desc,
                                placeholder=f"描述 {role_name} 的外观特征...\n例如：男性，25岁，短发，身材高大，穿着蓝色T恤",
                                height=80,
                                key=f"global_desc_{role_name}",
                                label_visibility="collapsed"
                            )
                            if desc:
                                st.session_state.global_char_descs[role_name] = desc
                            elif role_name in st.session_state.global_char_descs:
                                del st.session_state.global_char_descs[role_name]

                        # TTS声线选择
                        if available_voices:
                            st.markdown("**🎤 配音声线**")
                            voice_options = [v['id'] for v in available_voices]
                            def _make_voice_label(v):
                                name = v.get('name', v['id'])
                                gender = v.get('gender', '')
                                style = v.get('style', '')
                                return f"{name} ({gender}) - {style}" if style else f"{name} ({gender})"
                            voice_labels = {v['id']: _make_voice_label(v) for v in available_voices}
                            current_voice = st.session_state.global_voice_mapping.get(role_name)
                            voice_idx = voice_options.index(current_voice) if current_voice in voice_options else 0
                            selected_voice = st.selectbox(
                                f"声线_{role_name}",
                                options=voice_options,
                                index=voice_idx,
                                format_func=lambda x, vl=voice_labels: vl.get(x, x),
                                key=f"global_voice_{role_name}",
                                label_visibility="collapsed"
                            )
                            st.session_state.global_voice_mapping[role_name] = selected_voice

                    st.divider()

    with tab2:
        for i, shot in enumerate(st.session_state.shots):
            with st.expander(f"📽️ 分镜 {shot['shot_id']}{' - ' + shot.get('shot_prompt', '')[:50] + '...' if shot.get('shot_prompt') else ''}", expanded=(i == 0)):
                shot_prompt = shot.get('shot_prompt', '')
                roles_in_shot = shot.get('roles', [])

                if roles_in_shot:
                    st.caption(f"👤 出场角色: {', '.join(roles_in_shot)}")

                # 场景选择
                st.markdown("**🎬 场景**")
                matched_scenes = scene_pool.search_by_name(shot_prompt)
                if all_scenes:
                    scene_options = ["🤖 AI自动生成"] + [s['name'] for s in all_scenes]
                    scene_default = 0
                    if matched_scenes:
                        first_match = matched_scenes[0]['name']
                        if first_match in [s['name'] for s in all_scenes]:
                            scene_default = [s['name'] for s in all_scenes].index(first_match) + 1
                    selected_scene = st.selectbox(
                        "选择场景",
                        options=scene_options,
                        index=scene_default,
                        key=f"scene_{i}"
                    )
                    if selected_scene == "🤖 AI自动生成":
                        selected_scene = None
                else:
                    selected_scene = None

                if not selected_scene:
                    scene_desc = st.text_area(
                        "场景描述",
                        value=st.session_state.get(f"shot_{i}_scene_desc", ''),
                        placeholder="描述场景环境...\n例如：阳光明媚的海滩，蓝天白云",
                        height=60,
                        key=f"scene_desc_{i}"
                    )
                    st.session_state[f"shot_{i}_scene_desc"] = scene_desc
                else:
                    st.session_state[f"shot_{i}_scene_desc"] = ''

                # 物品选择
                st.markdown("**🎒 物品**")
                matched_props = prop_pool.search_by_name(shot_prompt)
                if all_props:
                    selected_props = st.multiselect(
                        "选择物品",
                        options=[p['name'] for p in all_props],
                        default=[p['name'] for p in matched_props],
                        key=f"props_{i}"
                    )
                else:
                    selected_props = []

                # 物品手动描述（未选择但匹配到的物品）
                if all_props and matched_props:
                    unselected = [p for p in matched_props if p['name'] not in selected_props]
                    if unselected:
                        for prop in unselected:
                            prop_desc = st.text_input(
                                f"'{prop['name']}' 描述",
                                value=st.session_state.get(f"prop_desc_{i}_{prop['name']}", ''),
                                placeholder=f"描述 {prop['name']} 的外观...",
                                key=f"prop_desc_{i}_{prop['name']}"
                            )
                            if f"shot_{i}_prop_descs" not in st.session_state:
                                st.session_state[f"shot_{i}_prop_descs"] = {}
                            st.session_state[f"shot_{i}_prop_descs"][prop['name']] = prop_desc
                    else:
                        st.session_state.pop(f"shot_{i}_prop_descs", None)

    st.divider()

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("← 上一步", width='stretch'):
            st.session_state.current_step = 2
            st.rerun()
    with col3:
        if st.button("下一步：生成视频 →", type="primary", width='stretch'):
            # 收集新结构的 resource_mapping
            resource_mapping = {
                'global_character_mapping': dict(st.session_state.global_char_mapping),
                'global_character_descs': dict(st.session_state.global_char_descs),
                'global_voice_mapping': dict(st.session_state.get('global_voice_mapping', {})),
                'shots': {}
            }

            for i, shot in enumerate(st.session_state.shots):
                shot_data = {
                    'scene': None,
                    'scene_desc': '',
                    'props': [],
                    'prop_descs': {}
                }

                # 场景
                scene_key = f"scene_{i}"
                if scene_key in st.session_state and st.session_state[scene_key] not in (None, "🤖 AI自动生成"):
                    shot_data['scene'] = st.session_state[scene_key]

                # 场景描述
                scene_desc_key = f"shot_{i}_scene_desc"
                if scene_desc_key in st.session_state:
                    shot_data['scene_desc'] = st.session_state[scene_desc_key]

                # 物品
                props_key = f"props_{i}"
                if props_key in st.session_state:
                    shot_data['props'] = st.session_state[props_key]

                # 物品描述
                prop_descs_key = f"shot_{i}_prop_descs"
                if prop_descs_key in st.session_state:
                    shot_data['prop_descs'] = st.session_state[prop_descs_key]

                resource_mapping['shots'][i] = shot_data

            st.session_state.resource_mapping = resource_mapping
            st.session_state.current_step = 4
            st.rerun()


# ==================== 步骤4: 生成视频 ====================
elif current_step == 4:
    st.markdown("## 🎬 生成视频")
    
    # 显示配置摘要
    st.markdown("### 📋 生成配置")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("分镜数", len(st.session_state.shots))
    with col2:
        st.metric("分辨率", st.session_state.config['resolution'])
    with col3:
        st.metric("帧率", f"{st.session_state.config['fps']} fps")
    with col4:
        audio_mode = st.session_state.config.get('audio_mode', 'tts')
        audio_status = {
            'tts': '🎤 TTS配音',
            'seedance_audio': '🎬 AI自动',
            'silent': '🔇 静音'
        }.get(audio_mode, '🎤 TTS配音')
        st.metric("配音模式", audio_status)
    
    st.divider()
    
    # 显示分镜列表
    st.markdown("### 📽️ 待生成分镜")
    for shot in st.session_state.shots:
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown(f"**分镜 {shot['shot_id']}**")
            roles = shot.get('roles', [])
            if roles:
                st.caption(f"角色: {', '.join(roles)}")
        with col2:
            st.caption(shot.get('shot_prompt', '')[:100] + "...")
    
    st.divider()

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("← 上一步", width='stretch'):
            st.session_state._generating = False
            st.session_state._generation_running = False
            st.session_state.current_step = 3
            st.rerun()
    with col2:
        if st.button("🎬 开始生成视频", type="primary", width='stretch',
                     disabled=st.session_state.get('_generating', False)):
            st.session_state._generating = True
            st.session_state._generation_running = False
            st.rerun()

    # 防重入：_generating=True 且 _generation_running=False（尚未执行）时才进入
    if st.session_state.get('_generating') and not st.session_state.get('_generation_running'):
        st.session_state._generation_running = True  # 立即上锁，后续rerun不会再次进入

        try:
            # 显示资源使用情况
            st.markdown("### 📊 资源使用统计")

            rm = st.session_state.resource_mapping
            global_chars = rm.get('global_character_mapping', {})
            global_descs = rm.get('global_character_descs', {})
            has_global_chars = bool(global_chars or global_descs)

            total_shots = len(st.session_state.shots)
            shots_with_resources = 0
            shots_without_resources = 0

            for i, shot in enumerate(st.session_state.shots):
                shot_m = rm.get('shots', {}).get(i, {})
                has_shot_resources = bool(
                    shot_m.get('scene') or shot_m.get('props')
                )
                if has_global_chars or has_shot_resources:
                    shots_with_resources += 1
                else:
                    shots_without_resources += 1

            col_r1, col_r2 = st.columns(2)
            with col_r1:
                st.success(f"✅ {shots_with_resources} 个分镜使用资源池资源")
            with col_r2:
                st.info(f"🤖 {shots_without_resources} 个分镜由AI自动生成")

            st.divider()

            # 进度UI
            st.markdown("### 🎬 生成进度")
            progress_bar = st.progress(0)
            status_container = st.empty()

            # 断点续跑预检
            output_dir = task_manager.get_task_dir(st.session_state.current_task_id)
            skipped_count = 0
            for shot in st.session_state.shots:
                video_path = f"{output_dir}/shot_{shot['shot_id']:03d}.mp4"
                if os.path.exists(video_path):
                    skipped_count += 1
            if skipped_count > 0:
                st.info(f"🔄 检测到 {skipped_count}/{total_shots} 个分镜已存在，将自动跳过（断点续跑）")

            def on_progress(current: int, total: int, status: str, shot_id: int):
                pct = min(current / total, 1.0)
                progress_bar.progress(pct)
                status_map = {
                    'submitting': f"📡 正在提交分镜 {shot_id}/{total}...",
                    'done': f"✅ 分镜 {shot_id} 完成",
                    'failed': f"❌ 分镜 {shot_id} 失败",
                    'tts_mixing': "🎤 正在混音TTS...",
                    'subtitles': "📝 正在烧录字幕...",
                    'merging': "🎬 正在合并视频...",
                }
                status_container.info(status_map.get(status, status))

            # 检测是否需要强制重做
            force_regenerate = st.session_state.get('_force_regenerate', False)
            st.session_state._force_regenerate = False

            batch_generate_videos(
                task_id=st.session_state.current_task_id,
                shots=st.session_state.shots,
                config=st.session_state.config,
                resource_mapping=st.session_state.resource_mapping,
                progress_callback=on_progress,
                force=force_regenerate
            )
            task_manager.update_task(st.session_state.current_task_id, status="videos_generated")
            progress_bar.progress(1.0)
            status_container.success("✅ 视频生成完成！")

            # 清除生成标志，跳到步骤5
            st.session_state._generating = False
            st.session_state._generation_running = False
            st.session_state.current_step = 5
            time.sleep(0.5)
            st.rerun()
        except Exception as e:
            st.session_state._generating = False
            st.session_state._generation_running = False
            st.error(f"❌ 视频生成失败：{str(e)}")


# ==================== 步骤5: 检查导出 ====================
elif current_step == 5:
    st.markdown("## ✅ 检查与导出")

    # 显示生成的视频
    st.markdown("### 🎥 生成的视频")

    output_dir = task_manager.get_task_dir(st.session_state.current_task_id) if st.session_state.current_task_id else ""

    if not st.session_state.current_task_id:
        st.info("尚未生成视频，请先完成前面的步骤")
    else:
        st.caption(f"📁 任务目录: {output_dir}")

        if os.path.exists(output_dir):
            video_files = sorted([f for f in os.listdir(output_dir) if f.endswith('.mp4')])

            if video_files:
                # 每行4个视频，统一大小
                cols_per_row = 4
                for row_start in range(0, len(video_files), cols_per_row):
                    row_files = video_files[row_start:row_start + cols_per_row]
                    cols = st.columns(cols_per_row)
                    for j, video_file in enumerate(row_files):
                        shot_id = int(video_file.replace('shot_', '').replace('.mp4', '').split('_')[0]) if video_file.startswith('shot_') else row_start + j + 1
                        with cols[j]:
                            video_path = os.path.join(output_dir, video_file)
                            st.video(video_path)
                            st.caption(f"📽️ 分镜 {shot_id}")
                            if st.button(f"🔄 重做", key=f"redo_{video_file}", width='stretch'):
                                os.remove(video_path)
                                for f in os.listdir(output_dir):
                                    if f.startswith(f"shot_{shot_id:03d}") and (f.endswith('.wav') or f.endswith('.mp4')):
                                        os.remove(os.path.join(output_dir, f))
                                shot = st.session_state.shots[shot_id - 1]
                                shot_resource_mapping = st.session_state.resource_mapping.get('shots', {}).get(shot_id - 1, {})
                                full_shot_mapping = {"global_character_mapping": st.session_state.resource_mapping.get('global_character_mapping', {}),
                                                     "global_character_descs": st.session_state.resource_mapping.get('global_character_descs', {}),
                                                     "global_voice_mapping": st.session_state.resource_mapping.get('global_voice_mapping', {}),
                                                     "shots": {shot_id - 1: shot_resource_mapping}}
                                with st.spinner(f"🔄 正在重新生成分镜{shot_id}..."):
                                    ok = generate_single_video(shot, st.session_state.current_task_id,
                                                               st.session_state.config, full_shot_mapping, force=True)
                                    if ok:
                                        st.success(f"✅ 分镜{shot_id} 重新生成完成")
                                    else:
                                        st.error(f"❌ 分镜{shot_id} 重做失败")
                                st.rerun()
            else:
                st.info("暂无生成的视频")
        else:
            st.warning("输出目录不存在")

    st.divider()

    # 批量重做：返回步骤4重新生成所有缺失的分镜
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("← 上一步", width='stretch'):
            st.session_state.current_step = 4
            st.rerun()
    with col2:
        if st.button("🎬 批量重做缺失分镜", width='stretch'):
            # 回到步骤4，force模式下会清理并重新生成
            st.session_state._force_regenerate = True
            st.session_state.current_step = 4
            st.rerun()
    with col3:
        if st.button("📦 导出视频", type="primary", width='stretch'):
            st.success(f"✅ 视频已导出到 {output_dir}")


# ==================== 侧边栏 ====================
with st.sidebar:
    st.markdown("### 🎯 快速操作")
    
    if st.button("🏠 返回首页", width='stretch'):
        st.session_state.current_step = 0
        st.rerun()

    st.divider()

    # 当前任务
    if st.session_state.current_task_id:
        st.markdown("### 📋 当前任务")
        st.caption(f"ID: {st.session_state.current_task_id}")
        if st.button("🆕 开始新任务", width='stretch', type="secondary"):
            st.session_state.current_task_id = None
            st.session_state.shots = []
            st.session_state.resource_mapping = {}
            st.session_state.generated_videos = []
            st.session_state.global_char_mapping = {}
            st.session_state.global_char_descs = {}
            st.session_state.global_voice_mapping = {}
            st.session_state.current_step = 0
            st.rerun()

    st.divider()

    # 历史任务
    st.markdown("### 📚 历史任务")
    tasks = task_manager.list_tasks()
    if tasks:
        for t in tasks[:10]:
            task_dir = task_manager.get_task_dir(t['task_id'])
            video_count = 0
            if os.path.exists(task_dir):
                video_count = len([f for f in os.listdir(task_dir) if f.endswith('.mp4')])
            delete_key = f"del_confirm_{t['task_id']}"
            if st.session_state.get(delete_key):
                st.caption(f"确认删除 {t['task_id']}？")
                col_y, col_n = st.columns(2)
                with col_y:
                    if st.button("✅ 确认", key=f"del_yes_{t['task_id']}"):
                        task_manager.delete_task(t['task_id'])
                        if st.session_state.current_task_id == t['task_id']:
                            st.session_state.current_task_id = None
                            st.session_state.shots = []
                            st.session_state.resource_mapping = {}
                            st.session_state.current_step = 0
                        st.session_state[delete_key] = False
                        st.rerun()
                with col_n:
                    if st.button("❌ 取消", key=f"del_no_{t['task_id']}"):
                        st.session_state[delete_key] = False
                        st.rerun()
            else:
                col_t, col_a = st.columns([5, 2])
                with col_t:
                    st.caption(f"{t['task_id']} — {t.get('shot_count', 0)}镜/{video_count}视频")
                with col_a:
                    ca1, ca2 = st.columns(2)
                    with ca1:
                        if st.button("📂", key=f"open_task_{t['task_id']}", help="查看此任务"):
                            st.session_state.current_task_id = t['task_id']
                            st.session_state.current_step = 5
                            st.rerun()
                    with ca2:
                        if st.button("🗑️", key=f"del_btn_{t['task_id']}", help="删除此任务"):
                            st.session_state[delete_key] = True
                            st.rerun()
    else:
        st.caption("暂无历史任务")

    st.divider()
    
    # API配置状态
    st.markdown("### 🔑 API配置状态")
    ds_key_status = "✅" if config.DEEPSEEK_API_KEY and config.DEEPSEEK_API_KEY != "your_api_key" else "❌"
    sd_key_status = "✅" if config.SEEDANCE_API_KEY and config.SEEDANCE_API_KEY != "your_api_key" else "❌"
    
    st.markdown(f"{ds_key_status} 分镜生成API")
    st.caption(f"模型: {config.DEEPSEEK_MODEL}")
    st.markdown(f"{sd_key_status} 视频生成API")
    st.caption(f"模型: {config.SEEDANCE_MODEL}")
    
    if st.button("⚙️ 修改API配置", width='stretch', type="secondary"):
        st.session_state.show_api_config = True
        st.rerun()
    
    st.divider()
    
    st.markdown("### 📊 资源统计")
    
    char_pool = get_character_pool()
    scene_pool = get_scene_pool()
    prop_pool = get_prop_pool()

    st.metric("角色数量", char_pool.count())
    st.metric("场景数量", scene_pool.count())
    st.metric("物品数量", prop_pool.count())
    
    st.divider()
    
    st.markdown("### ⚙️ 快速配置")

    if 'sidebar_show_add_char' not in st.session_state:
        st.session_state.sidebar_show_add_char = False

    if not st.session_state.sidebar_show_add_char:
        if st.button("➕ 添加角色", width='stretch'):
            st.session_state.sidebar_show_add_char = True
            st.rerun()
    else:
        # 文件上传（表单外，响应式）
        uploaded_file = st.file_uploader(
            "📁 上传角色图片",
            type=['jpg', 'jpeg', 'png'],
            key="sidebar_char_uploader",
            help="选择角色的参考图片"
        )
        uploaded_path = ""
        if uploaded_file is not None:
            import tempfile
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, uploaded_file.name)
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.image(temp_path, width='stretch')
            st.caption(f"✅ 已选择: {uploaded_file.name}")
            uploaded_path = temp_path

        with st.form("sidebar_add_char_form"):
            st.subheader("快速添加角色")
            char_name = st.text_input("角色名称 *", placeholder="例如：林风")
            appearance_template = st.selectbox(
                "外观模板（可选）",
                ["自定义", "男性，25-30岁，短发，身材高大，五官立体",
                 "女性，20-25岁，长发，身材苗条，气质优雅",
                 "男性，30-40岁，成熟稳重，胡须，西装革履",
                 "女性，25-35岁，职业装，干练短发",
                 "男性，18-22岁，阳光帅气，运动装"],
                index=0, help="选择预设模板或自定义"
            )
            if appearance_template != "自定义":
                char_appearance = st.text_area("外观描述", value=appearance_template, label_visibility="collapsed")
            else:
                char_appearance = st.text_area("外观描述", placeholder="例如：男性，25岁，短发，身材高大")
            char_clothes = st.text_input("服装描述", placeholder="例如：深灰色连帽卫衣、黑色长裤")
            char_character = st.text_input("性格描述", placeholder="例如：沉稳内敛，眼神锐利")
            char_image = st.text_input("图片路径 *", value=uploaded_path, placeholder="上传图片或手动输入路径")
            char_tags = st.text_input("标签（逗号分隔）", placeholder="例如：主角,现代,悬疑")

            c1, c2 = st.columns(2)
            with c1:
                submitted = st.form_submit_button("✅ 添加", type="primary", width='stretch')
            with c2:
                cancelled = st.form_submit_button("❌ 取消", width='stretch')

            if submitted:
                image_path = uploaded_path or char_image
                if char_name and image_path:
                    try:
                        dest_path = _copy_to_pool_images(image_path, char_name)
                        char_pool.add(
                            name=char_name,
                            appearance=char_appearance,
                            clothes=char_clothes,
                            character=char_character,
                            image_path=dest_path,
                            tags=[t.strip() for t in char_tags.split(",") if t.strip()]
                        )
                        st.success(f"✅ 角色 '{char_name}' 添加成功！")
                        st.session_state.sidebar_show_add_char = False
                        st.rerun()
                    except ValueError as e:
                        st.error(f"❌ {e}")
                else:
                    st.error("请填写角色名称和选择图片")

            if cancelled:
                st.session_state.sidebar_show_add_char = False
                st.rerun()
