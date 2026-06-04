import os
import json
import time
import requests
import concurrent.futures
from typing import List, Dict, Callable, Optional
import config as cfg
from character_pool import get_character_pool
from utils.image_utils import image_to_base64
from utils.logger import get_logger
from tts_service import get_tts_service
from audio_processor import AudioProcessor, SubtitleGenerator

logger = get_logger(__name__)


def create_output_dir(episode_num: int):
    """创建输出文件夹"""
    os.makedirs(f"./output/episode_{episode_num:03d}", exist_ok=True)
    os.makedirs("./shots", exist_ok=True)


def generate_single_video(shot: Dict, task_id: str, config: Dict = None, resource_mapping: Dict = None, force: bool = False) -> bool:
    """生成单个分镜视频（含TTS配音），供批量生成和单镜重做复用

    Args:
        shot: 分镜数据
        task_id: 任务ID
        config: 用户配置
        resource_mapping: 资源映射数据 {global_character_mapping, global_character_descs, global_voice_mapping, shots}
        force: 强制重新生成，跳过断点续跑检查
    """
    shot_id = shot["shot_id"]
    video_path = f"./output/{task_id}/shot_{shot_id:03d}.mp4"
    os.makedirs(f"./output/{task_id}", exist_ok=True)

    # 检查是否已经生成过（断点续跑）
    if not force and os.path.exists(video_path):
        logger.info("分镜%d 已存在，跳过", shot_id)
        return True

    # 使用统一的 prompt/payload 构建逻辑
    shot_payload = _build_shot_payload(shot, task_id, config, resource_mapping)
    if shot_payload is None:
        # DRY RUN 模式 —— _build_shot_payload 已完成所有日志输出
        return True

    # 提交 + 轮询 + 下载
    headers = {
        "Authorization": f"Bearer {cfg.SEEDANCE_API_KEY}",
        "Content-Type": "application/json"
    }

    remote_task_id = None
    for retry in range(cfg.MAX_RETRY):
        try:
            logger.info("正在生成分镜%d（第%d次尝试）", shot_id, retry + 1)
            response = requests.post(cfg.SEEDANCE_API_URL, json=shot_payload, headers=headers, timeout=60)
            logger.info("HTTP %d: %s", response.status_code, response.text[:200])
            response.raise_for_status()
            result = response.json()
            remote_task_id = result.get("task_id") or result.get("id")
            if remote_task_id:
                break
            logger.error("分镜%d 提交未返回task_id: %s", shot_id, result)
        except Exception as e:
            logger.error("分镜%d 生成失败（第%d次）: %s", shot_id, retry + 1, e)
            if retry < cfg.MAX_RETRY - 1:
                logger.info("等待 %d 秒后重试...", cfg.API_INTERVAL)
                time.sleep(cfg.API_INTERVAL)

    if not remote_task_id:
        logger.error("分镜%d 提交失败，已重试 %d 次", shot_id, cfg.MAX_RETRY)
        return False

    logger.info("任务ID: %s，开始轮询结果...", remote_task_id)
    video_url = poll_task_result(remote_task_id, headers)
    if not video_url:
        logger.error("分镜%d 轮询超时或失败", shot_id)
        return False

    download_video(video_url, video_path)
    logger.info("分镜%d 生成并保存完成", shot_id)

    # ---------- TTS 配音后处理（单镜重做时也需要重新配音）----------
    audio_mode = config.get('audio_mode', 'tts') if config else 'tts'
    if audio_mode == 'tts' and not cfg.DRY_RUN:
        dialogue = shot.get("dialogue", [])
        narration = shot.get("narration", "")
        if dialogue or narration:
            global_voice_mapping = resource_mapping.get('global_voice_mapping', {}) if resource_mapping else {}
            tts_service = get_tts_service()
            shot_audio_files = []
            output_dir = f"./output/{task_id}"

            for d_entry in dialogue:
                role = d_entry.get('role', '')
                text = d_entry.get('text', '').strip()
                if not text:
                    continue
                voice_id = global_voice_mapping.get(role, 'xiaoyun')
                logger.info("为角色 %s 生成TTS: %s... (声线: %s)", role, text[:30], voice_id)
                audio_file = tts_service.synthesize(
                    text=text,
                    voice_id=voice_id,
                    output_path=f"{output_dir}/tts_shot_{shot_id:03d}_{role}.wav"
                )
                if audio_file:
                    shot_audio_files.append((role, audio_file))

            if narration:
                narrator_voice = global_voice_mapping.get('旁白', 'xiaoyun')
                logger.info("生成旁白TTS: %s... (声线: %s)", narration[:30], narrator_voice)
                narration_audio = tts_service.synthesize(
                    text=narration,
                    voice_id=narrator_voice,
                    output_path=f"{output_dir}/tts_shot_{shot_id:03d}_旁白.wav"
                )
                if narration_audio:
                    shot_audio_files.append(('旁白', narration_audio))

            if shot_audio_files:
                merged_audio = f"{output_dir}/tts_shot_{shot_id:03d}.wav"
                if len(shot_audio_files) > 1:
                    shot_duration = config.get('shot_duration', cfg.SHOT_DURATION)
                    AudioProcessor.mix_audio_with_timing(
                        [(af, role) for role, af in shot_audio_files],
                        merged_audio,
                        total_duration=shot_duration
                    )
                else:
                    merged_audio = shot_audio_files[0][1]

                output_video = f"{output_dir}/shot_{shot_id:03d}_with_tts.mp4"
                try:
                    AudioProcessor.mix_audio_to_video(
                        video_path=video_path,
                        tts_audio_path=merged_audio,
                        output_path=output_video,
                        bg_volume=0.3,
                        tts_volume=1.0
                    )
                    if os.path.exists(output_video):
                        os.replace(output_video, video_path)
                        logger.info("分镜%d TTS配音+背景音混合完成", shot_id)
                except Exception as e:
                    logger.error("分镜%d TTS配音失败: %s", shot_id, e)

    return True


def poll_task_result(task_id: str, headers: dict, max_wait: int = 600) -> str:
    """轮询任务结果，返回视频URL"""
    query_url = f"{cfg.SEEDANCE_API_URL.rstrip('/')}/{task_id}"

    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(query_url, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()

            status = result.get("status", "") or ""
            status_lower = status.lower()
            elapsed = int(time.time() - start_time)

            # 更全面的终端状态匹配
            terminal_success = ["succeeded", "completed", "success", "done", "finished", "ready"]
            terminal_fail = ["failed", "error", "cancelled", "canceled"]

            if status_lower in terminal_success:
                video_url = (
                    result.get("video_url") or
                    result.get("content", {}).get("video_url") or
                    result.get("output", {}).get("video_url") or
                    result.get("data", {}).get("video_url")
                )

                if video_url:
                    logger.info("获取到视频URL（耗时%ds）", elapsed)
                    return video_url
                else:
                    logger.warning("任务状态为%s但未找到视频URL，响应keys: %s", status, list(result.keys()))
                    return None

            elif status_lower in terminal_fail:
                error_msg = result.get("error") or result.get("message") or result.get("error_msg", "未知错误")
                logger.error("任务失败（耗时%ds）: %s", elapsed, error_msg)
                return None
            else:
                logger.info("任务状态: %s（已等待%ds/%ds），继续等待...", status, elapsed, max_wait)
                time.sleep(5)

        except Exception as e:
            elapsed = int(time.time() - start_time)
            logger.warning("轮询失败（已等待%ds）: %s", elapsed, e)
            time.sleep(5)

    logger.error("轮询超时（%d秒），最终状态: %s", max_wait,
                  result.get("status", "未知") if 'result' in locals() else "无法获取")
    return None


def download_video(video_url: str, save_path: str) -> None:
    """下载视频文件"""
    logger.info("正在下载视频到: %s", save_path)
    response = requests.get(video_url, stream=True, timeout=120)
    response.raise_for_status()

    with open(save_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    logger.info("视频已保存: %s", save_path)


def _build_shot_payload(shot: Dict, task_id: str, config: Dict = None, resource_mapping: Dict = None) -> Optional[Dict]:
    """为单个分镜构建Seedance API payload。DRY_RUN模式下打印payload并返回None。"""
    shot_id = shot["shot_id"]
    shot_prompt = shot["shot_prompt"]
    shot_roles = shot["roles"]
    dialogue = shot.get("dialogue", [])
    narration = shot.get("narration", "")

    global_char_mapping = {}
    global_char_descs = {}
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

    # 加载所有映射角色的参考图（不限于当前分镜的shot_roles，保证跨分镜一致性）
    ref_images = []
    char_pool = get_character_pool(cfg.RESOURCE_POOL_DIR)
    all_mapped_roles = set()
    if global_char_mapping:
        all_mapped_roles = set(global_char_mapping.keys())
    if global_char_descs:
        all_mapped_roles.update(global_char_descs.keys())
    # 合并shot_roles中未映射但有角色库匹配的角色
    all_mapped_roles.update(shot_roles)

    for role_name in all_mapped_roles:
        mapped_name = global_char_mapping.get(role_name, role_name) if global_char_mapping else role_name
        # 先尝试角色池
        image_path = char_pool.get_image_path(mapped_name)
        # 如果角色池没有，尝试角色名直接作为资源池名称
        if not image_path:
            image_path = char_pool.get_image_path(role_name)
        if image_path and os.path.exists(image_path):
            try:
                ref_images.append(image_to_base64(image_path))
                if mapped_name != role_name:
                    logger.info("已加载角色图片: %s -> %s -> %s", role_name, mapped_name, image_path)
                else:
                    logger.info("已加载角色图片: %s -> %s", role_name, image_path)
            except Exception as e:
                logger.error("加载角色图片失败 %s: %s", role_name, e)

    if config is None:
        config = {}

    base_style_prompt = config.get('base_style_prompt', cfg.BASE_STYLE_PROMPT)
    resolution = config.get('resolution', '1080p')
    aspect_ratio = config.get('aspect_ratio', '9:16')
    shot_duration = config.get('shot_duration', cfg.SHOT_DURATION)

    full_prompt = base_style_prompt + shot_prompt

    # 注入角色描述（始终注入所有映射角色的外观描述，不检查role_name是否在prompt中）
    char_descs_injected = []
    if global_char_mapping:
        for role_name, mapped_char_name in global_char_mapping.items():
            if not mapped_char_name:
                continue
            role_prompt = char_pool.build_role_prompt(mapped_char_name)
            if role_prompt:
                # 如果prompt中提到了这个角色名，直接替换
                if role_name in shot_prompt:
                    full_prompt = full_prompt.replace(role_name, f"{role_name}（{role_prompt}）", 1)
                else:
                    # 否则追加到末尾，确保模型知道这个角色该长什么样
                    char_descs_injected.append(f"{role_name}外观：{role_prompt}")

    if global_char_descs:
        for role_name, desc in global_char_descs.items():
            if not desc:
                continue
            if role_name in shot_prompt:
                full_prompt = full_prompt.replace(role_name, f"{role_name}（{desc}）", 1)
            elif role_name not in global_char_mapping:  # 避免重复
                char_descs_injected.append(f"{role_name}外观：{desc}")

    if char_descs_injected:
        full_prompt += "\n\n角色外观参考：\n" + "\n".join(char_descs_injected)
        full_prompt += "\n注意：请严格按照上述外观描述生成对应角色，保持所有分镜中角色的面部、体型、服装一致。"

    # 注入场景描述（仅文本，不加入ref_images以免干扰人脸一致性）
    if scene_name:
        from scene_pool import get_scene_pool
        scene_pool = get_scene_pool(cfg.RESOURCE_POOL_DIR)
        scene_data = scene_pool.get_by_name(scene_name)
        if scene_data:
            scene_desc_from_pool = scene_data.get('description', '')
            if scene_desc_from_pool and scene_name not in shot_prompt:
                full_prompt += f"\n场景参考：{scene_desc_from_pool}"
            # 场景图片仅用于记录日志，不加入ref_images（ref_images仅用于人脸一致性）
            scene_image_path = scene_data.get('image_path', '')
            if scene_image_path and os.path.exists(scene_image_path):
                logger.info("场景参考图已记录（不加入ref_images）: %s", scene_name)
    elif scene_desc:
        full_prompt += f"\n场景：{scene_desc}"

    # 注入物品描述（仅文本，不加入ref_images）
    if prop_names:
        from prop_pool import get_prop_pool
        prop_pool = get_prop_pool(cfg.RESOURCE_POOL_DIR)
        prop_descs_from_pool = []
        for prop_name in prop_names:
            prop_data = prop_pool.get_by_name(prop_name)
            if prop_data:
                prop_desc = prop_data.get('description', '')
                if prop_desc and prop_name not in shot_prompt:
                    prop_descs_from_pool.append(prop_desc)
        if prop_descs_from_pool:
            full_prompt += f"\n物品参考：{', '.join(prop_descs_from_pool)}"
    elif prop_descs:
        desc_list = [desc for desc in prop_descs.values() if desc]
        if desc_list:
            full_prompt += f"\n物品：{', '.join(desc_list)}"

    # 音频模式
    audio_mode = config.get('audio_mode', 'tts') if config else 'tts'
    if audio_mode == "tts":
        generate_audio = True
        full_prompt += "\n注意：视频只需要生成环境音和背景音乐，不需要生成人物对话声音。"
    elif audio_mode == "seedance_audio":
        generate_audio = True
        audio_parts = []
        if dialogue:
            dialogue_lines = [f"{d['role']}：\"{d['text']}\"" for d in dialogue]
            audio_parts.append("对话：" + "；".join(dialogue_lines))
        if narration:
            audio_parts.append(f"旁白：\"{narration}\"")
        if audio_parts:
            full_prompt += f"\n音频要求：视频必须包含以下音频内容，同时生成符合场景环境的背景音和背景音乐。\n" + "\n".join(audio_parts)
    else:
        generate_audio = False

    # 跨分镜一致性提示（当有角色映射或场景指定时）
    consistency_notes = []
    if global_char_mapping or global_char_descs:
        consistency_notes.append("角色一致性：所有参考图中的人物外貌、服装、体型必须严格保持一致")
    if scene_name or scene_desc:
        consistency_notes.append("场景一致性：严格按照指定的场景环境和场景参考图生成背景，不要自由发挥")
    if consistency_notes:
        full_prompt += "\n\n关键要求：\n" + "\n".join(consistency_notes)

    payload = {
        "model": cfg.SEEDANCE_MODEL,
        "content": [{"type": "text", "text": full_prompt}],
        "reference_images": ref_images if ref_images else [],
        "face_consistency": "high",
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "duration": shot_duration,
        "generate_audio": generate_audio
    }

    if cfg.DRY_RUN:
        logger.info("=" * 60)
        logger.info("DRY RUN - 分镜%d", shot_id)
        logger.info("=" * 60)
        logger.info("配置: %s / %s / %ds / audio=%s", resolution, aspect_ratio, shot_duration, generate_audio)
        logger.info("角色: %s", shot_roles)
        if global_char_mapping:
            logger.info("角色映射: %s", global_char_mapping)
        if ref_images:
            logger.info("参考图: %d 张", len(ref_images))
        logger.info("完整提示词:\n%s", full_prompt)
        safe_payload = {k: v for k, v in payload.items() if k != 'reference_images'}
        safe_payload['reference_images_count'] = len(payload.get('reference_images', []))
        logger.info("API Payload (不含图片):\n%s", json.dumps(safe_payload, ensure_ascii=False, indent=2))
        logger.info("=" * 60)
        return None

    return payload


def _poll_and_download(remote_task_id: str, headers: dict, video_path: str, shot_id: int) -> bool:
    """轮询任务结果并下载视频。返回True/False。"""
    video_url = poll_task_result(remote_task_id, headers)
    if not video_url:
        logger.error("分镜%d 轮询超时或失败", shot_id)
        return False

    download_video(video_url, video_path)
    logger.info("分镜%d 生成并保存完成", shot_id)
    return True


def batch_generate_videos(task_id: str, shots: List[Dict] = None, config: Dict = None,
                         resource_mapping: Dict = None, progress_callback: Optional[Callable] = None,
                         force: bool = False) -> None:
    """批量生成所有分镜视频

    Args:
        task_id: 任务ID
        shots: 分镜列表（从外部传入，不再从磁盘读取）
        config: 用户配置
        resource_mapping: 资源映射数据
        progress_callback: 进度回调 (current: int, total: int, status: str, shot_id: int)
        force: 强制重新生成所有分镜，跳过断点续跑检查
    """
    output_dir = f"./output/{task_id}"
    os.makedirs(output_dir, exist_ok=True)

    if shots is None:
        shot_path = f"{output_dir}/shots.json"
        if not os.path.exists(shot_path):
            logger.error("分镜文件不存在: %s", shot_path)
            return
        with open(shot_path, "r", encoding="utf-8") as f:
            shots = json.load(f)

    total = len(shots)
    logger.info("开始批量生成任务 %s，共%d个分镜", task_id, total)

    # 强制模式：清理输出目录中的旧视频和残留文件
    if force and os.path.exists(output_dir):
        import glob
        old_files = glob.glob(f"{output_dir}/*.mp4") + glob.glob(f"{output_dir}/*.wav")
        for f in old_files:
            os.remove(f)
            logger.info("已清理旧文件: %s", f)

    if config:
        logger.info("使用配置: 分辨率=%s, 画面比例=%s, 基础提示词=%s...",
                    config.get('resolution', '1080p'),
                    config.get('aspect_ratio', '9:16'),
                    config.get('base_style_prompt', '默认')[:50])

    if resource_mapping:
        global_chars = resource_mapping.get('global_character_mapping', {})
        global_descs = resource_mapping.get('global_character_descs', {})
        logger.info("使用资源映射: 角色映射=%s, 自定义描述=%s",
                    global_chars, list(global_descs.keys()))

    audio_mode = config.get('audio_mode', 'tts') if config else 'tts'

    # 收集所有待生成的任务（保留 shot 引用用于后续TTS）
    generate_tasks = []       # (shot_id, idx, video_file, shot, full_shot_mapping)
    skip_shots = {}           # shot_id -> shot (用于TTS阶段获取已跳过镜头的对话/旁白)
    for i, shot in enumerate(shots):
        shot_id = shot['shot_id']
        video_file = f"{output_dir}/shot_{shot_id:03d}.mp4"

        if not force and os.path.exists(video_file):
            logger.info("分镜%d 已存在，跳过", shot_id)
            skip_shots[shot_id] = shot
            continue

        shot_resource_mapping = resource_mapping.get('shots', {}).get(i, {}) if resource_mapping else {}
        full_shot_mapping = {"global_character_mapping": resource_mapping.get('global_character_mapping', {}),
                             "global_character_descs": resource_mapping.get('global_character_descs', {}),
                             "shots": {i: shot_resource_mapping}} if resource_mapping else None

        generate_tasks.append((shot_id, i, video_file, shot, full_shot_mapping))

    skip_count = len(skip_shots)
    pending_count = len(generate_tasks)
    if skip_count > 0:
        logger.info("断点续跑: %d个已完成，%d个待生成", skip_count, pending_count)

    success_count = skip_count
    video_files = [f"{output_dir}/shot_{sid:03d}.mp4" for sid in skip_shots]
    tts_audio_files = []

    if pending_count > 0:
        logger.info("并发生成%d个视频（分阶段：串行提交→并发轮询）...", pending_count)

        # Phase 1: 串行提交所有任务（间隔1秒防止限流）
        headers = {"Authorization": f"Bearer {cfg.SEEDANCE_API_KEY}",
                   "Content-Type": "application/json"}
        submissions = []  # [(shot_id, video_file, shot, remote_task_id)]

        for shot_id, idx, video_file, shot, full_shot_mapping in generate_tasks:
            if progress_callback:
                progress_callback(len(submissions), pending_count, "submitting", shot_id)

            # 构建payload（与generate_single_video内部逻辑对齐）
            shot_payload = _build_shot_payload(shot, task_id, config, full_shot_mapping)
            if shot_payload is None:
                logger.info("DRY RUN - 分镜%d 跳过提交", shot_id)
                submissions.append((shot_id, video_file, shot, None))
                continue

            # 串行提交到API，带重试
            remote_task_id = None
            for retry in range(cfg.MAX_RETRY):
                try:
                    logger.info("提交分镜%d到Seedance（第%d次尝试）", shot_id, retry + 1)
                    response = requests.post(cfg.SEEDANCE_API_URL, json=shot_payload, headers=headers, timeout=60)
                    logger.info("HTTP %d: %s", response.status_code, response.text[:200])
                    response.raise_for_status()
                    result = response.json()
                    remote_task_id = result.get("task_id") or result.get("id")
                    if remote_task_id:
                        break
                    else:
                        logger.error("分镜%d 提交未返回task_id: %s", shot_id, result)
                except Exception as e:
                    logger.error("分镜%d 提交失败（第%d次）: %s", shot_id, retry + 1, e)
                    if retry < cfg.MAX_RETRY - 1:
                        time.sleep(cfg.API_INTERVAL)

            submissions.append((shot_id, video_file, shot, remote_task_id))
            # 间隔1秒防止API限流
            if len(generate_tasks) > 1:
                time.sleep(1)

        # Phase 2: 并发轮询所有已提交的任务
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(pending_count, 5)) as executor:
            future_map = {}
            for shot_id, video_file, shot, remote_task_id in submissions:
                if remote_task_id is None:
                    # DRY RUN 或提交失败的镜头
                    if cfg.DRY_RUN:
                        success_count += 1
                        video_files.append(video_file)
                        logger.info("DRY RUN - 分镜%d 完成", shot_id)
                    else:
                        logger.error("分镜%d 提交失败，跳过", shot_id)
                    continue

                future = executor.submit(_poll_and_download, remote_task_id, headers, video_file, shot_id)
                future_map[future] = (shot_id, video_file, shot)

            for future in concurrent.futures.as_completed(future_map):
                shot_id, video_file, shot = future_map[future]
                try:
                    ok = future.result()
                    if ok:
                        success_count += 1
                        video_files.append(video_file)
                        logger.info("分镜%d 完成（%d/%d）", shot_id, success_count, total)
                        if progress_callback:
                            progress_callback(success_count, total, "done", shot_id)
                    else:
                        logger.error("分镜%d 失败", shot_id)
                        if progress_callback:
                            progress_callback(success_count, total, "failed", shot_id)
                except Exception as e:
                    logger.error("分镜%d 异常: %s", shot_id, e)
                    if progress_callback:
                        progress_callback(success_count, total, "failed", shot_id)

    # Phase 3: TTS配音（在所有视频生成完成后统一处理）
    if audio_mode == 'tts' and not cfg.DRY_RUN:
        all_shots = {}  # shot_id -> shot
        for _, _, _, shot, _ in generate_tasks:
            all_shots[shot['shot_id']] = shot
        all_shots.update(skip_shots)

        for shot_id, shot in all_shots.items():
            video_file = f"{output_dir}/shot_{shot_id:03d}.mp4"
            if not os.path.exists(video_file):
                continue

            dialogue = shot.get('dialogue', [])
            narration = shot.get('narration', '')
            if not dialogue and not narration:
                continue

            # 检查是否已有TTS音频（断点续跑）
            tts_file = f"{output_dir}/tts_shot_{shot_id:03d}.wav"
            if os.path.exists(tts_file):
                tts_audio_files.append({
                    'shot_id': shot_id,
                    'audio_file': tts_file,
                    'dialogue': dialogue
                })
                continue

            global_voice_mapping = resource_mapping.get('global_voice_mapping', {}) if resource_mapping else {}
            tts_service = get_tts_service()
            shot_audio_files = []

            for d_entry in dialogue:
                role = d_entry.get('role', '')
                text = d_entry.get('text', '').strip()
                if not text:
                    continue
                voice_id = global_voice_mapping.get(role, 'xiaoyun')
                logger.info("为角色 %s 生成TTS: %s... (声线: %s)", role, text[:30], voice_id)
                audio_file = tts_service.synthesize(
                    text=text,
                    voice_id=voice_id,
                    output_path=f"{output_dir}/tts_shot_{shot_id:03d}_{role}.wav"
                )
                if audio_file:
                    shot_audio_files.append((role, audio_file))

            if narration:
                narrator_voice = global_voice_mapping.get('旁白', 'xiaoyun')
                logger.info("生成旁白TTS: %s... (声线: %s)", narration[:30], narrator_voice)
                narration_audio = tts_service.synthesize(
                    text=narration,
                    voice_id=narrator_voice,
                    output_path=f"{output_dir}/tts_shot_{shot_id:03d}_旁白.wav"
                )
                if narration_audio:
                    shot_audio_files.append(('旁白', narration_audio))

            if shot_audio_files:
                merged_audio = f"{output_dir}/tts_shot_{shot_id:03d}.wav"
                if len(shot_audio_files) > 1:
                    shot_duration = config.get('shot_duration', cfg.SHOT_DURATION)
                    AudioProcessor.mix_audio_with_timing(
                        [(af, role) for role, af in shot_audio_files],
                        merged_audio,
                        total_duration=shot_duration
                    )
                else:
                    merged_audio = shot_audio_files[0][1]

                tts_audio_files.append({
                    'shot_id': shot_id,
                    'audio_file': merged_audio,
                    'dialogue': dialogue
                })
                logger.info("分镜%d TTS配音完成（%d段对话）", shot_id, len(shot_audio_files))
    elif audio_mode == 'tts' and cfg.DRY_RUN:
        all_shots = {}
        for _, _, _, shot, _ in generate_tasks:
            all_shots[shot['shot_id']] = shot
        all_shots.update(skip_shots)
        for shot_id, shot in all_shots.items():
            dialogue = shot.get('dialogue', [])
            narration = shot.get('narration', '')
            if dialogue or narration:
                logger.info("DRY RUN TTS - 分镜%d: %s", shot_id,
                            [(d.get('role'), d.get('text', '')[:20]) for d in dialogue])

    logger.info("视频文件保存在：%s", output_dir)

    # 后处理：TTS配音和字幕烧录
    if config and success_count > 0:
        enable_subtitle = config.get('enable_subtitle', False)

        # TTS配音处理
        if audio_mode == 'tts' and tts_audio_files:
            logger.info("开始TTS配音处理...")
            if progress_callback:
                progress_callback(total, total, "tts_mixing", 0)

            for tts_info in tts_audio_files:
                shot_id = tts_info['shot_id']
                tts_audio = tts_info['audio_file']
                video_file = f"{output_dir}/shot_{shot_id:03d}.mp4"

                if os.path.exists(video_file) and os.path.exists(tts_audio):
                    output_video = f"{output_dir}/shot_{shot_id:03d}_with_tts.mp4"
                    try:
                        AudioProcessor.mix_audio_to_video(
                            video_path=video_file,
                            tts_audio_path=tts_audio,
                            output_path=output_video,
                            bg_volume=0.3,
                            tts_volume=1.0
                        )
                        if os.path.exists(output_video):
                            os.replace(output_video, video_file)
                            logger.info("分镜%d TTS配音+背景音混合完成", shot_id)
                    except Exception as e:
                        logger.error("分镜%d TTS配音失败: %s", shot_id, e)

        # 字幕处理
        if enable_subtitle:
            logger.info("开始字幕烧录处理...")
            if progress_callback:
                progress_callback(total, total, "subtitles", 0)

            srt_file = f"{output_dir}/subtitles.srt"
            try:
                SubtitleGenerator.generate_srt(
                    shots=shots,
                    output_path=srt_file,
                    language=config.get('subtitle_lang', 'zh'),
                    shot_duration=config.get('shot_duration', cfg.SHOT_DURATION)
                )

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
                            if os.path.exists(output_video):
                                os.replace(output_video, video_file)
                                logger.info("分镜%d 字幕烧录完成", shot_id)
                        except Exception as e:
                            logger.error("分镜%d 字幕烧录失败: %s", shot_id, e)

                logger.info("字幕处理完成")
            except Exception as e:
                logger.error("字幕处理失败: %s", e)

        # 视频合并
        if config.get('export_mode') == 'merged' and len(video_files) > 1:
            logger.info("开始合并视频...")
            if progress_callback:
                progress_callback(total, total, "merging", 0)

            merged_video = f"{output_dir}/merged.mp4"
            try:
                AudioProcessor.merge_videos(
                    video_files=video_files,
                    output_path=merged_video
                )
                logger.info("视频合并完成: %s", merged_video)
            except Exception as e:
                logger.error("视频合并失败: %s", e)
