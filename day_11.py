import streamlit as st
import requests
import json
import os
import hashlib
import re
from datetime import datetime

# ========== 配置 ==========
API_KEY = "sk-3bf05148163f4db5ae8ba43e885e21c8"
url = "https://api.deepseek.com/v1/chat/completions"
headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# ========== 工具定义 ==========
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的实时天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称，如：北京、上海"}
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_news",
            "description": "查询最新新闻",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "新闻主题（可选）"}
                },
                "required": []
            }
        }
    }
]


# ========== 工具实现 ==========
from pypinyin import pinyin, Style


def get_weather(city):
    # 将中文城市名转换为拼音（自动处理多音字）
    city_pinyin_list = pinyin(city, style=Style.NORMAL)
    city_en = ''.join([item[0] for item in city_pinyin_list])

    # 特殊处理：wttr.in 对某些城市的拼音识别不一致
    # 如果转换结果不准确，可以在这里添加特例
    special_cases = {
        "重庆": "Chongqing",
        "西安": "Xian",
    }
    if city in special_cases:
        city_en = special_cases[city]

    try:
        resp = requests.get(f"https://wttr.in/{city_en}?format=j1", timeout=10)
        data = resp.json()
        current = data["current_condition"][0]
        temp = current["temp_C"]
        weather = current["weatherDesc"][0]["value"]
        return f"{city} {weather}，{temp}°C"
    except Exception as e:
        return f"获取 {city} 天气失败：{str(e)}"


def get_news(topic):
    # 模拟新闻数据（可替换为真实API）
    news_data = {
        "科技": "AI智能体技术持续突破，多工具协同成为新趋势",
        "体育": "2026年世界杯预选赛进入关键阶段",
        "财经": "人民币汇率保持稳定，专家看好下半年走势"
    }
    if topic and topic in news_data:
        return news_data[topic]
    return "、".join(list(news_data.values()))


# ========== 用户管理（长期记忆的核心）==========
def get_user_id():
    """根据设备信息生成用户唯一ID（固定，不随刷新改变）"""
    if "user_id" not in st.session_state:
        # 尝试从本地存储读取固定ID
        user_dir = "users"
        os.makedirs(user_dir, exist_ok=True)
        id_file = f"{user_dir}/device_id.txt"

        if os.path.exists(id_file):
            with open(id_file, 'r', encoding='utf-8') as f:
                st.session_state.user_id = f.read().strip()
        else:
            # 首次访问，生成一个固定ID并保存
            import uuid
            new_id = uuid.uuid4().hex[:8]
            with open(id_file, 'w', encoding='utf-8') as f:
                f.write(new_id)
            st.session_state.user_id = new_id

    return st.session_state.user_id


def get_user_dir():
    """获取用户专属目录"""
    user_id = get_user_id()
    user_dir = f"users/{user_id}"
    os.makedirs(user_dir, exist_ok=True)
    return user_dir


def load_user_memory():
    """加载当前用户的记忆"""
    user_dir = get_user_dir()
    memory_file = f"{user_dir}/memory.json"
    if os.path.exists(memory_file):
        with open(memory_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_user_memory(messages):
    """保存当前用户的记忆"""
    user_dir = get_user_dir()
    memory_file = f"{user_dir}/memory.json"
    with open(memory_file, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)


def extract_cities_from_history(history):
    """
    从历史对话中提取所有城市名（不依赖固定列表）
    """
    cities = []
    for msg in history:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            # 匹配形如 "XX天气" 或 "XX呢" 的中文词组
            matches = re.findall(r'([\u4e00-\u9fa5]{2,4})(?:天气|呢|怎么样|如何|情况)', content)
            cities.extend(matches)
    # 去重并保持顺序
    seen = set()
    result = []
    for city in cities:
        if city not in seen:
            seen.add(city)
            result.append(city)
    return result

def get_user_stats():
    """获取用户统计信息"""
    user_dir = get_user_dir()
    stats_file = f"{user_dir}/stats.json"
    if os.path.exists(stats_file):
        with open(stats_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"session_count": 0, "last_visit": None}


def update_user_stats():
    """更新用户统计信息"""
    user_dir = get_user_dir()
    stats_file = f"{user_dir}/stats.json"
    stats = get_user_stats()
    stats["session_count"] += 1
    stats["last_visit"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


# ========== Agent 核心 ==========

def run_agent(user_input, messages):

    # 加载完整历史
    full_history = load_user_memory()

    # 提取历史中的城市，注入上下文提示
    cities = extract_cities_from_history(full_history)
    if cities:
        context = f"（提示：用户之前问过 {', '.join(cities)}。如果当前问题涉及城市对比，请引用这些信息。）"
        # 把上下文提示追加到消息中
        messages.append({"role": "system", "content": context})

    # 如果有历史记录，用历史作为基础
    if full_history:
        # 从当前 messages 中提取用户消息（排除系统提示）
        user_msgs = [m for m in messages if m.get("role") == "user"]
        # 用完整历史作为基础
        base_messages = full_history.copy()
        # 追加当前用户消息（去重）
        for m in user_msgs:
            if m not in base_messages:
                base_messages.append(m)
        messages = base_messages

    messages.append({"role": "user", "content": user_input})

    data = {
        "model": "deepseek-chat",
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto"
    }
    resp = requests.post(url, headers=headers, json=data)
    result = resp.json()

    if "error" in result:
        return messages, f"❌ API错误：{result['error'].get('message', '未知错误')}"

    assistant_msg = result["choices"][0]["message"]
    messages.append(assistant_msg)

    tool_calls = assistant_msg.get("tool_calls", [])
    if not tool_calls:
        save_user_memory(messages)
        return messages, assistant_msg.get("content", "模型没有返回内容")

    for tc in tool_calls:
        func_name = tc["function"]["name"]
        args = json.loads(tc["function"]["arguments"])

        if func_name == "get_weather":
            city = args.get("city")
            result_text = get_weather(city)
        elif func_name == "get_news":
            topic = args.get("topic", "")
            result_text = get_news(topic)
        else:
            result_text = f"未知工具：{func_name}"

        messages.append({
            "role": "tool",
            "tool_call_id": tc["id"],
            "content": result_text
        })

    final_data = {
        "model": "deepseek-chat",
        "messages": messages
    }
    final_resp = requests.post(url, headers=headers, json=final_data)
    final_result = final_resp.json()
    final_msg = final_result["choices"][0]["message"]
    messages.append(final_msg)

    save_user_memory(messages)


    return messages, final_msg.get("content", "")


# ========== Streamlit 界面 ==========
st.set_page_config(page_title="智能体助手 - 带记忆", page_icon="🧠")
st.title("🧠 智能体助手（带长期记忆）")

# 用户识别显示
user_id = get_user_id()
stats = get_user_stats()
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    st.caption(f"👤 用户ID：{user_id}")
with col2:
    st.caption(f"📊 会话次数：{stats['session_count']}")
with col3:
    if stats.get('last_visit'):
        st.caption(f"🕐 上次访问：{stats['last_visit']}")

st.markdown("---")

# 初始化会话状态
# ===== 页面初始化：加载历史记录 =====
if "messages" not in st.session_state:
    # 从文件加载历史
    history = load_user_memory()
    if history:
        # 把历史加载到 messages 中
        st.session_state.messages = history.copy()
        # 同时构建 chat_history 用于界面显示
        st.session_state.chat_history = []
        for msg in history:
            if msg.get("role") in ["user", "assistant"]:
                st.session_state.chat_history.append(msg)
    else:
        st.session_state.messages = [
            {"role": "system", "content": "你是一个智能助手，可以查询天气和新闻。记住用户的偏好和历史对话。"}
        ]
        st.session_state.chat_history = []

    update_user_stats()

# ===== 显示聊天历史（每次刷新页面都会执行）=====
# 注意：这段代码不在 if 里面，每次刷新都会运行


# 对话历史显示
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 输入框
user_input = st.chat_input("输入你的问题...")

if user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            messages, response = run_agent(user_input, st.session_state.messages)
            st.session_state.messages = messages
            st.markdown(response)
    st.session_state.chat_history.append({"role": "assistant", "content": response})

# 侧边栏功能
with st.sidebar:
    st.header("⚙️ 设置")

    # 查看记忆内容
    if st.button("📖 查看我的记忆"):
        memory = load_user_memory()
        if memory:
            st.json(memory)
        else:
            st.info("暂无记忆数据")

    # 清空记忆
    if st.button("🗑️ 清空记忆"):
        st.session_state.messages = [{"role": "system", "content": "你是一个智能助手，可以查询天气和新闻。"}]
        st.session_state.chat_history = []
        save_user_memory(st.session_state.messages)
        st.success("✅ 记忆已清空")
        st.rerun()

    st.divider()
    st.caption("💡 提示：你的对话历史会保存在本地，关闭浏览器后重新打开仍然可以继续对话。")