import os
import json
import time
import requests
from typing import List, Dict
from config import *
from character_pool import get_character_pool
from utils.image_utils import image_to_base64
from tts_service import get_tts_service
from audio_processor import AudioProcessor, SubtitleGenerator


def create_output_dir(episode_num: int):
    """创建输出文件夹"""
    os.makedirs(f"./output/episode_{episode_num:03d}", exist_ok=True)
    os.makedirs("./shots", exist_ok=True)


def get_reference_images(shot_roles: List[str], character_mapping: Dict = None) -> List[str]:
    """获取当前分镜所有出场角色的参考图（从角色池获取本地路径）
    
    Args:
        shot_roles: 分镜中的角色名列表
        character_mapping: 角色映射字典 {分镜角色名: 资源池角色名}
    """
    ref_images = []
    char_pool = get_character_pool(RESOURCE_POOL_DIR)
    
    for role_name in shot_roles:
        # 如果有映射，使用映射后的角色名
        actual_role_name = character_mapping.get(role_name, role_name) if character_mapping else role_name
        
        image_path = char_pool.get_image_path(actual_role_name)
        
        if not image_path:
            print(f"⚠️ 角色 {actual_role_name} 未配置图片路径")
            continue
        
        if not os.path.exists(image_path):
            print(f"⚠️ 角色 {actual_role_name} 图片不存在: {image_path}")
            continue
        
        try:
            # 转换本地图片为base64
            base64_image = image_to_base64(image_path)
            ref_images.append(base64_image)
            if actual_role_name != role_name:
                print(f"📸 已加载角色图片: {role_name} -> {actual_role_name} -> {image_path}")
            else:
                print(f"📸 已加载角色图片: {role_name} -> {image_path}")
        except Exception as e:
            print(f"❌ 加载角色图片失败 {role_name}: {e}")
    
    return ref_images


def generate_single_video(shot: Dict, episode_num: int, config: Dict = None, resource_mapping: Dict = None) -> bool:
    """生成单个分镜视频

    Args:
        shot: 分镜数据
        episode_num: 剧集编号
        config: 用户配置
        resource_mapping: 资源映射数据 {global_character_mapping, global_character_descs, shots}
    """
    shot_id = shot["shot_id"]
    shot_prompt = shot["shot_prompt"]
    shot_roles = shot["roles"]

    # 检查是否已经生成过（断点续跑）
    video_path = f"./output/episode_{episode_num:03d}/shot_{shot_id:03d}.mp4"
    if os.path.exists(video_path):
        print(f"⏭️  分镜{shot_id}已存在，跳过")
        return True

    # 解析新结构的 resource_mapping
    global_char_mapping = {}   # {role_name: pool_char_name}
    global_char_descs = {}      # {role_name: custom_description}
    scene_name = None
    scene_desc = ''
    prop_names = []
    prop_descs = {}

    if resource_mapping:
        global_char_mapping = resource_mapping.get('global_character_mapping', {})
        global_char_descs = resource_mapping.get('global_character_descs', {})
        shot_index = shot_id - 1
        shot_mapping = resource_mapping.get('shots', {}).get(shot_index, {})
        if shot_mapping:
            scene_name = shot_mapping.get('scene')
            scene_desc = shot_mapping.get('scene_desc', '')
            prop_names = shot_mapping.get('props', [])
            prop_descs = shot_mapping.get('prop_descs', {})

    # 获取所有出场角色的参考图（使用映射）
    ref_images = get_reference_images(shot_roles, global_char_mapping)

    if global_char_mapping:
        print(f"👥 分镜{shot_id}角色映射: {global_char_mapping}")
    if global_char_descs:
        print(f"📝 分镜{shot_id}角色自定义描述: {list(global_char_descs.keys())}")

    # 使用配置中的参数
    if config is None:
        config = {}

    base_style_prompt = config.get('base_style_prompt', BASE_STYLE_PROMPT)
    resolution = config.get('resolution', '1080p')
    aspect_ratio = config.get('aspect_ratio', '9:16')

    # 拼接完整提示词
    full_prompt = base_style_prompt + shot_prompt

    # --- 注入角色描述到视频提示词 ---
    if global_char_mapping:
        char_pool = get_character_pool(RESOURCE_POOL_DIR)
        for role_name, mapped_char_name in global_char_mapping.items():
            if mapped_char_name and role_name in shot_prompt:
                role_prompt = char_pool.build_role_prompt(mapped_char_name)
                if role_prompt:
                    full_prompt = full_prompt.replace(role_name, f"{role_name}（{role_prompt}）", 1)
                    print(f"👤 注入角色库描述: {role_name} -> {mapped_char_name}")
    elif global_char_descs:
        for role_name, desc in global_char_descs.items():
            if desc and role_name in shot_prompt:
                full_prompt = full_prompt.replace(role_name, f"{role_name}（{desc}）", 1)
                print(f"👤 使用自定义角色描述: {role_name}")
    
    # 获取场景参考图和描述（如果有）
    if scene_name:
        from scene_pool import get_scene_pool
        scene_pool = get_scene_pool(RESOURCE_POOL_DIR)
        scene_data = scene_pool.get_by_name(scene_name)
        if scene_data:
            # 只有当shot_prompt中没有明确场景描述时，才添加场景描述
            # 避免与LLM生成的shot_prompt重复
            scene_desc_from_pool = scene_data.get('description', '')
            if scene_desc_from_pool and scene_name not in shot_prompt:
                full_prompt += f"\n场景参考：{scene_desc_from_pool}"
                print(f"🎬 使用场景: {scene_name}")
            
            # 加载场景参考图（参考图比文本描述更重要）
            scene_image_path = scene_data.get('image_path', '')
            if scene_image_path and os.path.exists(scene_image_path):
                try:
                    scene_base64 = image_to_base64(scene_image_path)
                    ref_images.append(scene_base64)
                    print(f"📸 已加载场景参考图: {scene_name} -> {scene_image_path}")
                except Exception as e:
                    print(f"❌ 加载场景图片失败 {scene_name}: {e}")
    elif scene_desc:
        # 使用手动场景描述
        full_prompt += f"\n场景：{scene_desc}"
        print(f"🎬 使用手动场景描述: {scene_desc[:30]}...")
    
    # 如果有物品映射，添加物品描述和参考图
    if prop_names:
        from prop_pool import get_prop_pool
        prop_pool = get_prop_pool(RESOURCE_POOL_DIR)
        prop_descs_from_pool = []
        for prop_name in prop_names:
            prop_data = prop_pool.get_by_name(prop_name)
            if prop_data:
                # 只有当shot_prompt中没有明确物品描述时，才添加物品描述
                # 避免与LLM生成的shot_prompt重复
                prop_desc = prop_data.get('description', '')
                if prop_desc and prop_name not in shot_prompt:
                    prop_descs_from_pool.append(prop_desc)
                
                # 加载物品参考图（参考图比文本描述更重要）
                prop_image_path = prop_data.get('image_path', '')
                if prop_image_path and os.path.exists(prop_image_path):
                    try:
                        prop_base64 = image_to_base64(prop_image_path)
                        ref_images.append(prop_base64)
                        print(f"📸 已加载物品参考图: {prop_name} -> {prop_image_path}")
                    except Exception as e:
                        print(f"❌ 加载物品图片失败 {prop_name}: {e}")
        
        # 只有在不重复的情况下才添加物品描述
        if prop_descs_from_pool:
            full_prompt += f"\n物品参考：{', '.join(prop_descs_from_pool)}"
            print(f"🎒 使用物品: {', '.join(prop_names)}")
    elif prop_descs:
        # 使用手动物品描述
        desc_list = [desc for desc in prop_descs.values() if desc]
        if desc_list:
            full_prompt += f"\n物品：{', '.join(desc_list)}"
            print(f"🎒 使用手动物品描述: {len(desc_list)}个")

    # 获取音频模式配置
    audio_mode = config.get('audio_mode', 'tts') if config else 'tts'
    
    # 根据音频模式设置 generate_audio 参数
    if audio_mode == "tts":
        # TTS模式：视频模型只生成背景音
        generate_audio = True
        # 在提示词中添加说明，告诉视频模型不要生成对话
        full_prompt += "\n注意：视频只需要生成环境音和背景音乐，不需要生成人物对话声音。"
    elif audio_mode == "seedance_audio":
        # AI自动生成模式：视频模型生成完整音频（背景音+对话）
        generate_audio = True
    else:  # silent
        # 静音模式：不生成任何音频
        generate_audio = False
    
    # 调用即梦Seedance API
    payload = {
        "model": SEEDANCE_MODEL,
        "content": [
            {
                "type": "text",
                "text": full_prompt
            }
        ],
        "reference_images": ref_images if ref_images else [],
        "face_consistency": "high",
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "duration": SHOT_DURATION,
        "generate_audio": generate_audio
    }

    headers = {
        "Authorization": f"Bearer {SEEDANCE_API_KEY}",
        "Content-Type": "application/json"
    }

    # 失败重试机制
    for retry in range(MAX_RETRY):
        try:
            print(f"🎬 正在生成分镜{shot_id}（第{retry + 1}次尝试）")
            response = requests.post(SEEDANCE_API_URL, json=payload, headers=headers, timeout=60)
            
            # 打印详细响应信息用于调试
            print(f"📡 HTTP {response.status_code}: {response.text[:200]}")
            
            response.raise_for_status()
            
            result = response.json()
            
            # 火山引擎API通常返回任务ID，需要轮询结果
            task_id = result.get("task_id") or result.get("id")
            if not task_id:
                print(f"❌ 分镜{shot_id}未返回任务ID: {result}")
                return False
            
            print(f"🔄 任务ID: {task_id}，开始轮询结果...")
            
            # 轮询获取视频结果
            video_url = poll_task_result(task_id, headers)
            if not video_url:
                print(f"❌ 分镜{shot_id}轮询超时或失败")
                return False
            
            # 下载视频
            download_video(video_url, video_path)
            print(f"✅ 分镜{shot_id}生成并保存完成")
            return True

        except Exception as e:
            print(f"❌ 分镜{shot_id}生成失败：{e}")
            if retry < MAX_RETRY - 1:
                print(f"⏳ 等待{API_INTERVAL}秒后重试...")
                time.sleep(API_INTERVAL)

    print(f"❌ 分镜{shot_id}生成失败，已重试{MAX_RETRY}次")
    return False


def poll_task_result(task_id: str, headers: dict, max_wait: int = 300) -> str:
    """轮询任务结果，返回视频URL"""
    # 火山引擎查询任务的API端点
    query_url = f"https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}"
    
    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(query_url, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            status = result.get("status", "").lower()
            
            if status in ["succeeded", "completed", "success"]:
                # 提取视频URL（火山引擎的实际返回结构）
                video_url = (
                    result.get("video_url") or 
                    result.get("content", {}).get("video_url") or
                    result.get("output", {}).get("video_url")
                )
                
                if video_url:
                    print(f"✅ 获取到视频URL")
                    return video_url
                else:
                    print(f"⚠️ 任务完成但未找到视频URL: {result}")
                    return None
                    
            elif status in ["failed", "error"]:
                error_msg = result.get("error", "未知错误")
                print(f"❌ 任务失败: {error_msg}")
                return None
            else:
                # 任务仍在进行中
                print(f"⏳ 任务状态: {status}，继续等待...")
                time.sleep(5)
                
        except Exception as e:
            print(f"⚠️ 轮询失败: {e}")
            time.sleep(5)
    
    print(f"❌ 轮询超时（{max_wait}秒）")
    return None


def download_video(video_url: str, save_path: str) -> None:
    """下载视频文件"""
    print(f"⬇️  正在下载视频到: {save_path}")
    response = requests.get(video_url, stream=True, timeout=120)
    response.raise_for_status()
    
    with open(save_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    print(f"💾 视频已保存: {save_path}")


def batch_generate_videos(episode_num: int, shots: List[Dict] = None, config: Dict = None, resource_mapping: Dict = None) -> None:
    """批量生成所有分镜视频

    Args:
        episode_num: 剧集编号
        shots: 分镜列表（从外部传入，不再从磁盘读取）
        config: 用户配置
        resource_mapping: 资源映射数据 {global_character_mapping, global_character_descs, shots}
    """
    create_output_dir(episode_num)

    # 如果没有传入 shots，从磁盘读取（兼容旧调用）
    if shots is None:
        shot_path = f"./shots/episode_{episode_num:03d}_shots.json"
        if not os.path.exists(shot_path):
            print(f"❌ 分镜文件不存在: {shot_path}")
            return
        with open(shot_path, "r", encoding="utf-8") as f:
            shots = json.load(f)

    print(f"🚀 开始批量生成第{episode_num}集，共{len(shots)}个分镜")
    
    # 显示使用的配置
    if config:
        print(f"📊 使用配置:")
        print(f"  - 分辨率: {config.get('resolution', '1080p')}")
        print(f"  - 画面比例: {config.get('aspect_ratio', '9:16')}")
        print(f"  - 基础提示词: {config.get('base_style_prompt', '默认')[:50]}...")
    
    # 显示资源映射信息
    if resource_mapping:
        global_chars = resource_mapping.get('global_character_mapping', {})
        global_descs = resource_mapping.get('global_character_descs', {})
        print(f"📦 使用资源映射:")
        if global_chars:
            print(f"  全局角色映射: {global_chars}")
        if global_descs:
            print(f"  自定义角色描述: {list(global_descs.keys())}")
        shots_mapping = resource_mapping.get('shots', {})
        for shot_idx, sm in shots_mapping.items():
            scene = sm.get('scene')
            props = sm.get('props', [])
            if scene or props:
                print(f"  分镜{shot_idx + 1}:")
                if scene:
                    print(f"    🎬 场景: {scene}")
                if props:
                    print(f"    🎒 物品: {', '.join(props)}")

    success_count = 0
    video_files = []
    tts_audio_files = []  # 存储TTS音频文件
    
    # 判断是否启用TTS（兼容两种配置方式）
    enable_tts = config.get('enable_tts', False) if config else False
    audio_mode = config.get('audio_mode', 'tts') if config else 'tts'
    # 如果使用旧的enable_tts配置，转换为audio_mode
    if enable_tts and audio_mode != 'silent':
        audio_mode = 'tts'
    
    for i, shot in enumerate(shots):
        # 获取当前分镜的资源映射
        shot_resource_mapping = resource_mapping.get('shots', {}).get(i, {}) if resource_mapping else {}
        # 合并全局角色映射
        full_shot_mapping = {"global_character_mapping": resource_mapping.get('global_character_mapping', {}),
                             "global_character_descs": resource_mapping.get('global_character_descs', {}),
                             "shots": {i: shot_resource_mapping}} if resource_mapping else None

        if generate_single_video(shot, episode_num, config, full_shot_mapping):
            success_count += 1
            video_file = f"./output/episode_{episode_num:03d}/shot_{shot['shot_id']:03d}.mp4"
            video_files.append(video_file)
            
            # TTS配音：按角色对话+声线映射生成音频
            if audio_mode == 'tts':
                dialogue = shot.get('dialogue', [])
                if dialogue:
                    global_voice_mapping = resource_mapping.get('global_voice_mapping', {}) if resource_mapping else {}
                    tts_service = get_tts_service()
                    shot_audio_files = []

                    for d_entry in dialogue:
                        role = d_entry.get('role', '')
                        text = d_entry.get('text', '').strip()
                        if not text:
                            continue

                        voice_id = global_voice_mapping.get(role, 'xiaoyun')
                        print(f"🎤 为角色 {role} 生成TTS: {text[:30]}... (声线: {voice_id})")

                        audio_file = tts_service.synthesize(
                            text=text,
                            voice_id=voice_id,
                            output_path=f"./output/episode_{episode_num:03d}/tts_shot_{shot['shot_id']:03d}_{role}.wav"
                        )

                        if audio_file:
                            shot_audio_files.append(audio_file)

                    if shot_audio_files:
                        merged_audio = f"./output/episode_{episode_num:03d}/tts_shot_{shot['shot_id']:03d}.wav"
                        if len(shot_audio_files) > 1:
                            AudioProcessor.concat_audio_sequential(shot_audio_files, merged_audio)
                        else:
                            merged_audio = shot_audio_files[0]

                        tts_audio_files.append({
                            'shot_id': shot['shot_id'],
                            'audio_file': merged_audio,
                            'dialogue': dialogue
                        })
                        print(f"✅ 分镜{shot['shot_id']} TTS配音完成（{len(shot_audio_files)}段对话）")
        
        time.sleep(API_INTERVAL)

    print(f"\n🎉 批量生成完成！成功：{success_count}/{len(shots)}")
    print(f"📁 视频文件保存在：./output/episode_{episode_num:03d}/")
    
    # 后处理：TTS配音和字幕烧录
    if config and success_count > 0:
        enable_subtitle = config.get('enable_subtitle', False)
        output_dir = f"./output/episode_{episode_num:03d}"
        
        # TTS配音处理
        if audio_mode == 'tts' and tts_audio_files:
            print("\n🎤 开始TTS配音处理...")
            
            for tts_info in tts_audio_files:
                shot_id = tts_info['shot_id']
                tts_audio = tts_info['audio_file']
                video_file = f"{output_dir}/shot_{shot_id:03d}.mp4"
                
                if os.path.exists(video_file) and os.path.exists(tts_audio):
                    # 替换视频音频为TTS音频
                    output_video = f"{output_dir}/shot_{shot_id:03d}_with_tts.mp4"
                    try:
                        AudioProcessor.replace_video_audio(
                            video_path=video_file,
                            new_audio_path=tts_audio,
                            output_path=output_video
                        )
                        
                        # 替换原文件
                        if os.path.exists(output_video):
                            os.replace(output_video, video_file)
                            print(f"✅ 分镜{shot_id} TTS配音完成")
                    except Exception as e:
                        print(f"❌ 分镜{shot_id} TTS配音失败: {e}")
        
        # 字幕处理
        if enable_subtitle:
            print("\n📝 开始字幕烧录处理...")
            
            # 生成SRT字幕文件
            srt_file = f"{output_dir}/episode_{episode_num:03d}_subtitles.srt"
            try:
                SubtitleGenerator.generate_srt(
                    shots=shots,
                    output_path=srt_file,
                    language=config.get('subtitle_lang', 'zh')
                )
                
                # 烧录字幕到每个分镜视频
                for shot in shots:
                    shot_id = shot['shot_id']
                    video_file = f"{output_dir}/shot_{shot_id:03d}.mp4"
                    output_video = f"{output_dir}/shot_{shot_id:03d}_with_subtitle.mp4"
                    
                    if os.path.exists(video_file):
                        try:
                            SubtitleGenerator.burn_subtitle(
                                video_path=video_file,
                                subtitle_path=srt_file,
                                output_path=output_video,
                                font_size=24,
                                font_color='white'
                            )
                            
                            # 替换原文件
                            if os.path.exists(output_video):
                                os.replace(output_video, video_file)
                                print(f"✅ 分镜{shot_id} 字幕烧录完成")
                        except Exception as e:
                            print(f"❌ 分镜{shot_id} 字幕烧录失败: {e}")
                
                print(f"✅ 字幕处理完成")
            except Exception as e:
                print(f"❌ 字幕处理失败: {e}")
        
        # 视频合并（如果需要）
        if config.get('export_mode') == 'merged' and len(video_files) > 1:
            print("\n🎬 开始合并视频...")
            merged_video = f"{output_dir}/episode_{episode_num:03d}_merged.mp4"
            
            try:
                AudioProcessor.merge_videos(
                    video_files=video_files,
                    output_path=merged_video
                )
                print(f"✅ 视频合并完成: {merged_video}")
            except Exception as e:
                print(f"❌ 视频合并失败: {e}")
