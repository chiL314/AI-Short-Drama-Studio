import json
import os
import requests
from typing import List, Dict
from config import *
from character_pool import get_character_pool


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
        
        if len(shot['roles']) == 0:
            return False, f"第{i+1}个分镜至少需要一个角色"
        
        # 检查 roles 中的每个角色名
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
    
    return True, ""

def generate_shots_from_script(script_content: str, shot_count: int, episode_num: int, config: Dict = None) -> List[Dict]:
    """
    从剧本生成标准分镜列表
    :param script_content: 完整剧本内容
    :param shot_count: 要拆分的分镜数量
    :param episode_num: 剧集编号
    :param config: 用户配置（包含base_style_prompt）
    :return: 标准分镜列表
    """
    # 使用用户配置的提示词，如果没有则使用默认值
    if config is None:
        config = {}
    base_style_prompt = config.get('base_style_prompt', BASE_STYLE_PROMPT)
    # 从角色池检索本集出场的所有角色
    char_pool = get_character_pool(RESOURCE_POOL_DIR)
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

    # 给DeepSeek的系统提示词（强制约束，解决场景漂移问题）
    system_prompt = f"""
    你是专业的AI短剧分镜师，严格遵守以下所有规则：

    【绝对强制规则】
    1. 所有分镜必须严格保持场景、人物穿搭、道具的前后一致性
    2. 上一个分镜出现的物品、场景、人物穿着，下一个分镜必须完全继承
    3. 绝对不允许凭空出现或消失任何物品、人物
    4. 每个分镜严格对应{SHOT_DURATION}秒视频时长，动作不要太复杂
    5. 严格忠于原文，不添加任何额外剧情，只补充镜头语言

    【输出要求】
    1. 严格输出纯JSON数组，不要任何多余文字、解释、序号
    2. 每个分镜包含4个字段：
       "shot_id": 分镜编号(从1开始)
       "shot_prompt": 纯视频提示词(只写画面、动作、表情、光影、镜头)
       "roles": 本镜头出场的角色名数组(如["男主A", "女主B"])
       "dialogue": 本镜头对话数组，格式 [{{"role": "角色名", "text": "对话内容"}}]
       如果没有对话，dialogue 为空数组 []
    3. 绝对不允许输出任何JSON以外的内容
    4. dialogue中每条对话必须简短精炼（10字以内），符合短视频节奏

    【全局画风】
    {base_style_prompt}

    【本集出场角色人设（严格遵守）】
    {roles_str}
    """

    # 调用DeepSeek V4 API
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请将以下剧本拆分为{shot_count}个分镜：\n{script_content}"}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        DEEPSEEK_API_URL, 
        json=payload, 
        headers=headers,
        timeout=300  # 5分钟超时（处理长剧本需要更多时间）
    )
    response.raise_for_status()
    result = response.json()

    # 解析分镜列表 - 处理不同的返回格式
    content = result["choices"][0]["message"]["content"]
    
    # 如果 content 是字符串，先解析成 JSON
    if isinstance(content, str):
        try:
            parsed_content = json.loads(content)
        except json.JSONDecodeError as e:
            error_msg = f"AI返回的JSON格式错误：{str(e)}\n原始内容：{content[:200]}..."
            print(f"❌ {error_msg}")
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
    print("🔍 正在校验分镜数据格式...")
    is_valid, error_msg = validate_shots(shots)
    
    if not is_valid:
        error_msg = f"分镜数据校验失败：{error_msg}"
        print(f"❌ {error_msg}")
        print("💡 建议：请重新生成分镜，或检查AI模型返回格式")
        raise ValueError(error_msg)
    
    print(f"✅ 分镜数据校验通过（共{len(shots)}个分镜）")

    # 确保目录存在
    os.makedirs("./shots", exist_ok=True)

    # 保存分镜到本地JSON文件（支持人工审核修改）
    output_path = f"./shots/episode_{episode_num:03d}_shots.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(shots, f, ensure_ascii=False, indent=2)

    print(f"✅ 分镜生成完成，已保存到：{output_path}")
    print(f"💡 请打开文件人工审核修改，确认无误后再运行视频生成")

    return shots