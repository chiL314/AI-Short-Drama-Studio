import json
import os
import requests
from typing import List, Dict
import config as cfg
from character_pool import get_character_pool
from utils.logger import get_logger

logger = get_logger(__name__)


def validate_shots(shots: List[Dict]) -> tuple:
    """校验分镜数据格式是否正确
    
    Args:
        shots: AI生成的分镜列表
        
    Returns:
        (is_valid, error_message): 
            - is_valid: 校验是否通过
            - error_message: 错误信息（如果通过则为空字符串）
    """
    if not shots:
        return False, "分镜列表为空"
    
    if not isinstance(shots, list):
        return False, f"分镜数据应该是数组格式，实际是 {type(shots).__name__}"
    
    required_fields = {"shot_id", "shot_prompt", "roles", "dialogue"}
    
    for i, shot in enumerate(shots):
        # 检查是否为字典
        if not isinstance(shot, dict):
            return False, f"第{i+1}个分镜格式错误：应该是JSON对象，实际是 {type(shot).__name__}"
        
        # 检查必需字段
        missing_fields = required_fields - set(shot.keys())
        if missing_fields:
            return False, f"第{i+1}个分镜缺少字段: {', '.join(missing_fields)}"
        
        # 检查 shot_id 类型
        if not isinstance(shot['shot_id'], int):
            return False, f"第{i+1}个分镜的 shot_id 必须是整数，实际是 {type(shot['shot_id']).__name__}"
        
        # 检查 shot_id 连续性
        if shot['shot_id'] != i + 1:
            return False, f"第{i+1}个分镜的 shot_id 应该是 {i+1}，实际是 {shot['shot_id']}"
        
        # 检查 shot_prompt
        if not isinstance(shot['shot_prompt'], str):
            return False, f"第{i+1}个分镜的 shot_prompt 必须是字符串"
        
        if not shot['shot_prompt'].strip():
            return False, f"第{i+1}个分镜的 shot_prompt 不能为空"
        
        # 检查 roles
        if not isinstance(shot['roles'], list):
            return False, f"第{i+1}个分镜的 roles 必须是数组"
        
        # 检查 roles 中的每个角色名（允许空数组，无角色场景也可以生成视频）
        for j, role in enumerate(shot['roles']):
            if not isinstance(role, str):
                return False, f"第{i+1}个分镜的第{j+1}个角色名必须是字符串"

            if not role.strip():
                return False, f"第{i+1}个分镜的第{j+1}个角色名不能为空"

        # 检查 dialogue（新增字段）
        dialogue = shot.get('dialogue', [])
        if not isinstance(dialogue, list):
            return False, f"第{i+1}个分镜的 dialogue 必须是数组"

        for d_entry in dialogue:
            if not isinstance(d_entry, dict):
                return False, f"第{i+1}个分镜 dialogue 中每项必须是对象"
            if 'role' not in d_entry or 'text' not in d_entry:
                return False, f"第{i+1}个分镜 dialogue 每项必须包含 role 和 text 字段"
            if not isinstance(d_entry['text'], str):
                return False, f"第{i+1}个分镜 dialogue text 必须是字符串"

        # 检查 narration（可选字段）
        narration = shot.get('narration', '')
        if not isinstance(narration, str):
            return False, f"第{i+1}个分镜的 narration 必须是字符串"

    return True, ""

def _inject_character_profiles(script_content: str, shots: List[Dict]) -> List[Dict]:
    """从剧本中提取角色外观描述，并注入到每个分镜的shot_prompt中。
    仅在角色库无匹配时调用，保证无参考图情况下跨分镜角色一致性。
    """
    all_roles = set()
    for shot in shots:
        all_roles.update(shot.get('roles', []))

    # 过滤掉群体描述名和无意义的角色名
    skip_patterns = ['主播', '团队', '路人', '观众', '成员', '人们', '人群', '众人', '同学', '学生', '员工', '同事', '朋友', '群众', '顾客', '乘客']
    specific_roles = [r for r in all_roles if r.strip() and not any(p in r for p in skip_patterns)]

    if not specific_roles:
        return shots

    logger.info("未检测到角色库匹配，自动提取%d个角色外观...", len(specific_roles))

    profile_prompt = """根据剧本内容，为以下角色生成简洁的外观描述（20字以内），包含：发型、发色、服装、体型。
输出纯JSON对象，key为角色名，value为外观描述。不要输出任何其他内容。

角色列表：""" + json.dumps(specific_roles, ensure_ascii=False) + "\n\n剧本：\n" + script_content[:2000]

    try:
        headers = {
            "Authorization": f"Bearer {cfg.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": cfg.DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": "你是专业角色设定师，输出简洁准确的JSON格式角色外观描述。"},
                {"role": "user", "content": profile_prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 500
        }
        response = requests.post(cfg.DEEPSEEK_API_URL, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            first_newline = content.find("\n")
            if first_newline != -1:
                content = content[first_newline + 1:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
        profiles = json.loads(content)
    except Exception as e:
        logger.warning("角色外观提取失败（不影响分镜生成）: %s", e)
        return shots

    if not isinstance(profiles, dict):
        return shots

    logger.info("已提取角色外观: %s", {k: v[:20] for k, v in profiles.items()})

    # 注入到每个分镜的shot_prompt
    for shot in shots:
        shot_roles = shot.get('roles', [])
        role_descs = []
        for role in shot_roles:
            if role in profiles:
                role_descs.append(f"{role}外观：{profiles[role]}")
        if role_descs:
            shot['shot_prompt'] += "\n角色外观：" + "；".join(role_descs)

    return shots


def generate_shots_from_script(script_content: str, shot_count: int, episode_num: int = 1, user_config: Dict = None, task_id: str = None) -> List[Dict]:
    """
    从剧本生成标准分镜列表
    :param script_content: 完整剧本内容
    :param shot_count: 要拆分的分镜数量
    :param episode_num: 剧集编号（已弃用，建议使用 task_id）
    :param user_config: 用户配置（包含base_style_prompt）
    :param task_id: 任务ID，分镜会保存到 ./output/{task_id}/shots.json
    :return: 标准分镜列表
    """
    if user_config is None:
        user_config = {}
    base_style_prompt = user_config.get('base_style_prompt', cfg.BASE_STYLE_PROMPT)
    char_pool = get_character_pool(cfg.RESOURCE_POOL_DIR)
    hit_roles = char_pool.search_by_name(script_content)
    
    # 构建角色信息字符串
    roles_str = json.dumps([
        {
            "name": r['name'],
            "appearance": r['appearance'],
            "clothes": r['clothes'],
            "character": r['character']
        }
        for r in hit_roles
    ], ensure_ascii=False, indent=2)

    # 给DeepSeek的系统提示词
    # 注意：base_style_prompt 和 roles_str 包含 {} 字符，不能用 f-string 直接注入
    # 使用 .format() 替代，只对 SHOT_DURATION 做替换
    system_prompt = """
    你是专业的AI短剧分镜师，严格遵守以下所有规则：

    【绝对强制规则】
    1. 所有分镜必须严格保持场景、物品的前后一致性（纯风景/空镜无需遵守）
    2. 上一个分镜出现的物品、场景，下一个分镜必须完全继承
    3. 绝对不允许凭空出现或消失任何物品
    4. 每个分镜严格对应{shot_duration}秒视频时长，动作不要太复杂
    5. 严格忠于原文，不添加任何额外剧情，只补充镜头语言
    6. 每个出场角色的外貌特征必须在所有分镜中保持一致，在shot_prompt中明确描述角色的发型、发色、服装、体型等关键视觉特征

    【roles 字段说明（重要）】
    roles 用于标识画面中的人物，分三种情况：
    1. 有具体主角：使用剧本中的人物名，如 ["男主A", "女主B"]
    2. 有群体/背景人物但无具体主角：使用群体描述名，如 ["校园主播们", "团队成员", "围观路人", "观众"]
    3. 纯空镜/风景/物品/数据面板，完全无人：使用空数组 []
    请根据画面内容智能判断，不要在有人的场景给空数组。

    【输出要求】
    1. 严格输出纯JSON数组，不要任何多余文字、解释、序号
    2. 每个分镜包含5个字段：
       "shot_id": 分镜编号(从1开始)
       "shot_prompt": 视频提示词(包含画面、动作、表情、光影、镜头，以及每个出场角色的外观描述：发型、发色、服装、体型等)
       "roles": 本镜头出场角色名数组（参见上方roles字段说明）
       "dialogue": 本镜头对话数组，格式 [{{"role": "角色名", "text": "对话内容"}}]
       如果没有对话，dialogue 为空数组 []
       "narration": 本镜头旁白文本(纯字符串，从剧本中提取原句)
       如果没有旁白，narration 为空字符串 ""
    3. 绝对不允许输出任何JSON以外的内容
    4. dialogue中每条对话必须简短精炼（10字以内），符合短视频节奏
    5. 对于有主角的分镜，shot_prompt中必须包含该主角的外貌描述，同一角色在不同分镜中的外貌描述必须完全一致

    【全局画风】
    {base_style_prompt}

    【本集出场角色人设（仅供有具体主角时参考，群体角色可忽略）】
    {roles_str}
    """.format(
        shot_duration=cfg.SHOT_DURATION,
        base_style_prompt=base_style_prompt,
        roles_str=roles_str,
    )

    # 调用 LLM API
    payload = {
        "model": cfg.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请将以下剧本拆分为{shot_count}个分镜：\n{script_content}"}
        ],
        "temperature": 0.1
    }

    headers = {
        "Authorization": f"Bearer {cfg.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    response = None
    last_error = None
    for attempt in range(3):
        try:
            response = requests.post(
                cfg.DEEPSEEK_API_URL,
                json=payload,
                headers=headers,
                timeout=300
            )
            response.raise_for_status()
            break
        except Exception as e:
            last_error = e
            logger.warning("DeepSeek API请求失败（第%d次）: %s", attempt + 1, e)
            if attempt < 2:
                import time
                time.sleep(3)

    if response is None or not response.ok:
        error_detail = response.text[:500]
        logger.error("API请求失败 HTTP %d: %s", response.status_code, error_detail)
        raise ValueError(
            f"API请求失败 (HTTP {response.status_code})\n"
            f"URL: {cfg.DEEPSEEK_API_URL}\n"
            f"Model: {cfg.DEEPSEEK_MODEL}\n"
            f"详情: {error_detail}"
        )
    result = response.json()

    # 解析分镜列表 - 处理不同的返回格式
    content = result["choices"][0]["message"]["content"]
    
    # 如果 content 是字符串，先解析成 JSON
    if isinstance(content, str):
        # 去除 markdown 代码块标记（```json ... ```）
        content = content.strip()
        if content.startswith("```"):
            # 去掉开头的 ```json 或 ```
            first_newline = content.find("\n")
            if first_newline != -1:
                content = content[first_newline + 1:]
            # 去掉结尾的 ```
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
        try:
            parsed_content = json.loads(content)
        except json.JSONDecodeError as e:
            error_msg = f"AI返回的JSON格式错误：{str(e)}\n原始内容：{content[:200]}..."
            logger.error(error_msg)
            raise ValueError(error_msg)
    else:
        parsed_content = content
    
    # 如果解析结果是列表，直接使用；如果是字典，尝试获取 "shots" 键
    if isinstance(parsed_content, list):
        shots = parsed_content
    elif isinstance(parsed_content, dict):
        shots = parsed_content.get("shots", parsed_content)
    else:
        raise ValueError(f"无法解析的分镜格式: {type(parsed_content)}")
    
    # 校验分镜数据
    logger.info("正在校验分镜数据格式...")
    is_valid, error_msg = validate_shots(shots)

    if not is_valid:
        error_msg = f"分镜数据校验失败：{error_msg}"
        logger.error(error_msg)
        logger.info("建议：请重新生成分镜，或检查AI模型返回格式")
        raise ValueError(error_msg)

    logger.info("分镜数据校验通过（共%d个分镜）", len(shots))

    # 如果没有角色库匹配，自动提取角色外观描述并注入到每个分镜
    if not hit_roles:
        shots = _inject_character_profiles(script_content, shots)

    # 保存分镜到本地JSON文件（支持人工审核修改）
    if task_id:
        os.makedirs(f"./output/{task_id}", exist_ok=True)
        output_path = f"./output/{task_id}/shots.json"
    else:
        os.makedirs("./shots", exist_ok=True)
        output_path = f"./shots/episode_{episode_num:03d}_shots.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(shots, f, ensure_ascii=False, indent=2)

    logger.info("分镜生成完成，已保存到：%s", output_path)

    return shots