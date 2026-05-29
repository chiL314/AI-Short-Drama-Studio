"""
任务管理器 —— 每次视频生成任务独立文件夹
目录结构:
  ./output/
    .task_counter       # 自增计数器
    task_001/           # 任务1
      meta.json         # 任务元数据
      shots.json        # 分镜数据
      shot_001.mp4      # 分镜视频
      merged.mp4        # 合并视频
    task_002/           # 任务2
      ...
"""
import json
import os
from datetime import datetime

OUTPUT_DIR = "./output"


def _ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _read_counter() -> int:
    _ensure_output_dir()
    counter_file = os.path.join(OUTPUT_DIR, ".task_counter")
    if os.path.exists(counter_file):
        with open(counter_file, 'r') as f:
            return int(f.read().strip())
    return 0


def _write_counter(n: int):
    _ensure_output_dir()
    counter_file = os.path.join(OUTPUT_DIR, ".task_counter")
    with open(counter_file, 'w') as f:
        f.write(str(n))


def create_task(script_preview: str = "", shot_count: int = 0) -> str:
    """创建新任务目录，返回 task_id（如 task_001）"""
    n = _read_counter() + 1
    _write_counter(n)
    task_id = f"task_{n:03d}"
    task_dir = os.path.join(OUTPUT_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    meta = {
        "task_id": task_id,
        "created_at": datetime.now().isoformat(),
        "script_preview": script_preview[:200],
        "shot_count": shot_count,
        "status": "created",
    }
    with open(os.path.join(task_dir, "meta.json"), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return task_id


def update_task(task_id: str, **kwargs):
    """更新任务元数据"""
    meta_path = os.path.join(OUTPUT_DIR, task_id, "meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        meta.update(kwargs)
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)


def list_tasks() -> list:
    """列出所有任务，最新在前"""
    _ensure_output_dir()
    tasks = []
    if not os.path.exists(OUTPUT_DIR):
        return tasks
    for name in sorted(os.listdir(OUTPUT_DIR), reverse=True):
        if not name.startswith("task_"):
            continue
        meta_path = os.path.join(OUTPUT_DIR, name, "meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                tasks.append(json.load(f))
    return tasks


def get_task_dir(task_id: str) -> str:
    """获取任务目录路径"""
    return os.path.join(OUTPUT_DIR, task_id)


def shots_path(task_id: str) -> str:
    """获取任务的分镜文件路径"""
    return os.path.join(OUTPUT_DIR, task_id, "shots.json")


def video_path(task_id: str, shot_id: int) -> str:
    """获取分镜视频路径"""
    return os.path.join(OUTPUT_DIR, task_id, f"shot_{shot_id:03d}.mp4")


def merged_path(task_id: str) -> str:
    """获取合并视频路径"""
    return os.path.join(OUTPUT_DIR, task_id, "merged.mp4")
