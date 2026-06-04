"""
音频处理和字幕生成模块
使用FFmpeg进行音频合并、字幕烧录等操作
"""
import os
import json
import subprocess
from typing import List, Dict, Optional, Tuple
from utils.logger import get_logger

logger = get_logger(__name__)


class AudioProcessor:
    """音频处理器"""
    
    @staticmethod
    def get_ffmpeg_path():
        """获取FFmpeg可执行文件路径"""
        # 优先使用项目自带的FFmpeg
        project_ffmpeg = os.path.join(os.path.dirname(__file__), "ffmpeg", "bin", "ffmpeg.exe")
        if os.path.exists(project_ffmpeg):
            return project_ffmpeg
        # 如果项目内没有，尝试使用系统PATH中的
        return "ffmpeg"
    
    @staticmethod
    def check_ffmpeg() -> bool:
        """检查FFmpeg是否安装"""
        try:
            ffmpeg_path = AudioProcessor.get_ffmpeg_path()
            result = subprocess.run(
                [ffmpeg_path, '-version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def mix_audio_to_video(
        video_path: str,
        tts_audio_path: str,
        output_path: str,
        bg_volume: float = 0.3,
        tts_volume: float = 1.0
    ) -> str:
        """将TTS对话音轨与原视频背景音混合后写回视频

        保留原视频的背景音（降低音量），叠加TTS对话。

        Args:
            video_path: 原视频路径
            tts_audio_path: TTS对话音频路径
            output_path: 输出视频路径
            bg_volume: 背景音量（0.0-1.0，默认0.3）
            tts_volume: TTS对话音量（0.0-1.0，默认1.0）

        Returns:
            输出视频路径
        """
        if not AudioProcessor.check_ffmpeg():
            raise RuntimeError("未找到FFmpeg，请先安装FFmpeg")

        ffmpeg_path = AudioProcessor.get_ffmpeg_path()
        cmd = [
            ffmpeg_path, '-y',
            '-i', video_path,
            '-i', tts_audio_path,
            '-filter_complex',
            f'[0:a]volume={bg_volume}[bg];[1:a]volume={tts_volume}[tts];[bg][tts]amix=inputs=2:duration=first:dropout_transition=3[out]',
            '-map', '0:v:0',
            '-map', '[out]',
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-shortest',
            output_path
        ]

        logger.info("混音写入视频: %s (背景音=%s, TTS=%s)", os.path.basename(video_path), bg_volume, tts_volume)

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
            if result.returncode == 0:
                logger.info("混音写入成功: %s", output_path)
                return output_path
            else:
                error_msg = result.stderr.decode('utf-8')
                raise RuntimeError(f"FFmpeg混音写入失败: {error_msg}")
        except Exception as e:
            logger.error("混音写入失败: %s", e)
            raise

    @staticmethod
    def merge_videos(
        video_files: List[str],
        output_path: str
    ) -> str:
        """合并多个视频文件
        
        Args:
            video_files: 视频文件列表
            output_path: 输出文件路径
            
        Returns:
            输出文件路径
        """
        if not AudioProcessor.check_ffmpeg():
            raise RuntimeError("未找到FFmpeg，请先安装FFmpeg")

        # 编码一致性检查
        codec_infos = {}
        for vf in video_files:
            codec_infos[vf] = AudioProcessor.get_video_codec_info(vf)

        keys = ('codec', 'width', 'height', 'fps')
        all_match = True

        first_info = None
        for vf, info in codec_infos.items():
            if first_info is None:
                first_info = info
            else:
                for k in keys:
                    if info.get(k) != first_info.get(k):
                        all_match = False
                        break
            if not all_match:
                break

        if all_match and first_info:
            logger.info("视频编码一致 (codec=%s, %dx%d, %.2ffps)，使用 stream copy 模式",
                        first_info['codec'], first_info['width'], first_info['height'], first_info['fps'])
        else:
            logger.warning("视频编码不一致，使用重编码模式:\n  %s",
                           '\n  '.join(f"{os.path.basename(vf)}: {info}" for vf, info in codec_infos.items()))

        # 创建临时文件列表
        list_file = "./output/temp_merge_list.txt"
        with open(list_file, 'w', encoding='utf-8') as f:
            for video in video_files:
                abs_path = os.path.abspath(video)
                f.write(f"file '{abs_path}'\n")

        ffmpeg_path = AudioProcessor.get_ffmpeg_path()
        if all_match and first_info:
            cmd = [
                ffmpeg_path, '-y',
                '-f', 'concat', '-safe', '0',
                '-i', list_file,
                '-c', 'copy',
                output_path
            ]
        else:
            cmd = [
                ffmpeg_path, '-y',
                '-f', 'concat', '-safe', '0',
                '-i', list_file,
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
                '-c:a', 'aac', '-b:a', '192k',
                output_path
            ]

        logger.info("合并 %d 个视频", len(video_files))

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
            if os.path.exists(list_file):
                os.remove(list_file)
            if result.returncode == 0:
                logger.info("视频合并成功: %s", output_path)
                return output_path
            else:
                error_msg = result.stderr.decode('utf-8')
                raise RuntimeError(f"FFmpeg视频合并失败: {error_msg}")
        except Exception as e:
            logger.error("视频合并失败: %s", e)
            if os.path.exists(list_file):
                os.remove(list_file)
            raise

    @staticmethod
    def mix_audio_with_timing(
        audio_entries: List[Tuple[str, str]],
        output_path: str,
        total_duration: float = 5.0
    ) -> str:
        """将多段对话音频按时间轴混音（adelay + amix）

        Args:
            audio_entries: [(audio_file_path, label), ...] 按出场顺序排列
            output_path: 输出文件路径
            total_duration: 分镜总时长（秒）

        Returns:
            输出文件路径
        """
        if not audio_entries:
            raise ValueError("音频列表为空")
        if len(audio_entries) == 1:
            import shutil
            shutil.copy(audio_entries[0][0], output_path)
            return output_path

        if not AudioProcessor.check_ffmpeg():
            raise RuntimeError("未找到FFmpeg")

        n = len(audio_entries)
        slice_dur = total_duration / n
        ffmpeg_path = AudioProcessor.get_ffmpeg_path()

        cmd = [ffmpeg_path, '-y']
        for af, _ in audio_entries:
            cmd.extend(['-i', af])

        filter_parts = []
        for i in range(n):
            delay_ms = int(i * slice_dur * 1000)
            filter_parts.append(f'[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]')
        filter_parts.append(
            f'{"".join(f"[a{i}]" for i in range(n))}amix=inputs={n}:duration=longest:dropout_transition=3[out]'
        )

        cmd.extend(['-filter_complex', ';'.join(filter_parts), '-map', '[out]', output_path])

        logger.info("时间轴混音: %d 段, 总时长 %.1fs, 每段 %.1fs", n, total_duration, slice_dur)

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
            if result.returncode == 0:
                logger.info("时间轴混音成功: %s", output_path)
                return output_path
            else:
                error_msg = result.stderr.decode('utf-8')
                raise RuntimeError(f"FFmpeg时间轴混音失败: {error_msg}")
        except Exception as e:
            logger.error("时间轴混音失败: %s", e)
            raise

    @staticmethod
    def get_video_codec_info(video_path: str) -> Dict:
        """使用 ffprobe 获取视频编码信息"""
        ffprobe_path = AudioProcessor.get_ffmpeg_path().replace('ffmpeg', 'ffprobe')
        if not os.path.exists(ffprobe_path):
            ffprobe_path = 'ffprobe'

        cmd = [
            ffprobe_path, '-v', 'quiet',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_name,width,height,r_frame_rate',
            '-of', 'json',
            video_path
        ]

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
            if result.returncode == 0:
                info = json.loads(result.stdout.decode('utf-8'))
                stream = (info.get('streams') or [{}])[0]
                fps_str = stream.get('r_frame_rate', '0/1')
                num, den = fps_str.split('/') if '/' in fps_str else (fps_str, '1')
                fps = round(int(num) / int(den), 2) if int(den) != 0 else 0
                return {
                    'codec': stream.get('codec_name', 'unknown'),
                    'width': stream.get('width', 0),
                    'height': stream.get('height', 0),
                    'fps': fps,
                }
        except Exception as e:
            logger.warning("获取视频编码信息失败 %s: %s", video_path, e)

        return {'codec': 'unknown', 'width': 0, 'height': 0, 'fps': 0}

    @staticmethod
    def get_audio_duration(audio_path: str) -> float:
        """获取音频文件时长（秒），失败返回0"""
        ffprobe_path = AudioProcessor.get_ffmpeg_path().replace('ffmpeg', 'ffprobe')
        if not os.path.exists(ffprobe_path):
            ffprobe_path = 'ffprobe'
        try:
            result = subprocess.run(
                [ffprobe_path, '-v', 'quiet', '-show_entries', 'format=duration',
                 '-of', 'json', audio_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10
            )
            if result.returncode == 0:
                info = json.loads(result.stdout.decode('utf-8'))
                return float(info.get('format', {}).get('duration', 0))
        except Exception:
            pass
        return 0.0


class SubtitleGenerator:
    """字幕生成器"""

    @staticmethod
    def generate_shot_srt(
        entries: List[Tuple[str, float]],
        output_path: str,
        shot_duration: float = 5.0
    ) -> str:
        """为单个分镜生成SRT字幕，按实际音频时长排列时间轴

        Args:
            entries: [(text, audio_duration_seconds), ...] 按播放顺序
            output_path: 输出路径
            shot_duration: 分镜总时长（秒）
        """
        if not entries:
            return ""

        n = len(entries)
        slot_dur = shot_duration / n

        with open(output_path, 'w', encoding='utf-8') as f:
            for idx, (text, audio_dur) in enumerate(entries):
                if audio_dur <= 0:
                    audio_dur = slot_dur * 0.8
                start = idx * slot_dur
                end = min(start + audio_dur, start + slot_dur)
                f.write(f"{idx + 1}\n"
                        f"{SubtitleGenerator._format_timestamp(start)} --> "
                        f"{SubtitleGenerator._format_timestamp(end)}\n"
                        f"{text}\n\n")

        return output_path

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """将秒数转换为SRT时间戳格式 (HH:MM:SS,mmm)"""
        total_ms = int(seconds * 1000)
        hours = total_ms // 3600000
        minutes = (total_ms % 3600000) // 60000
        secs = (total_ms % 60000) // 1000
        millis = total_ms % 1000
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    @staticmethod
    def burn_subtitle(
        video_path: str,
        subtitle_path: str,
        output_path: str,
        font_size: int = 24,
        font_color: str = 'white'
    ) -> str:
        """将字幕烧录到视频
        
        Args:
            video_path: 视频文件路径
            subtitle_path: SRT字幕文件路径
            output_path: 输出文件路径
            font_size: 字体大小
            font_color: 字体颜色
            
        Returns:
            输出视频路径
        """
        if not AudioProcessor.check_ffmpeg():
            raise RuntimeError("未找到FFmpeg，请先安装FFmpeg")
        
        # 转换字幕文件路径为绝对路径（避免FFmpeg找不到）
        abs_subtitle = os.path.abspath(subtitle_path)
        # Windows: FFmpeg 将 \ 视为转义符，必须转为 /
        abs_subtitle = abs_subtitle.replace('\\', '/')
        # 转义路径中的特殊字符（: 在FFmpeg filter中有特殊含义）
        escaped_subtitle = abs_subtitle.replace(':', '\\:').replace("'", "'\\\\\\''")
        
        # 构建FFmpeg命令
        filter_complex = f"subtitles='{escaped_subtitle}':force_style='FontSize={font_size},PrimaryColour={font_color}'"
        
        ffmpeg_path = AudioProcessor.get_ffmpeg_path()
        cmd = [
            ffmpeg_path, '-y',
            '-i', video_path,
            '-vf', filter_complex,
            '-c:a', 'copy',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            output_path
        ]
        
        logger.info("烧录字幕: %s", os.path.basename(video_path))

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
            if result.returncode == 0:
                logger.info("字幕烧录成功: %s", output_path)
                return output_path
            else:
                error_msg = result.stderr.decode('utf-8')
                raise RuntimeError(f"FFmpeg字幕烧录失败: {error_msg}")
        except Exception as e:
            logger.error("字幕烧录失败: %s", e)
            raise
