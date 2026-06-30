import requests
import json
import streamlit as st

# ========== 配置 ==========
API_KEY = "sk-3bf05148163f4db5ae8ba43e885e21c8"
url = "https://api.deepseek.com/v1/chat/completions"
headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# ========== 工具定义 ==========
tools = [{
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
}]


# ========== 真实天气查询 ==========
def get_weather(city):
    city_map = {
        "北京": "Beijing", "上海": "Shanghai", "广州": "Guangzhou",
        "深圳": "Shenzhen", "杭州": "Hangzhou", "成都": "Chengdu",
        "武汉": "Wuhan", "重庆": "Chongqing", "南京": "Nanjing",
        "西安": "Xian", "天津": "Tianjin", "苏州": "Suzhou"
    }
    city_en = city_map.get(city)
    if not city_en:
        return f"暂不支持 {city}"

    try:
        resp = requests.get(f"https://wttr.in/{city_en}?format=j1", timeout=10)
        data = resp.json()
        current = data["current_condition"][0]
        temp = current["temp_C"]
        weather = current["weatherDesc"][0]["value"]
        humidity = current.get("humidity", "未知")
        return f"{city} {weather}，{temp}°C，湿度{humidity}%"
    except:
        return f"获取 {city} 天气失败"


# ========== Agent 核心函数 ==========
def run_agent(user_input, messages):
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
        return messages, f"❌ API错误：{result['error']}"

    assistant_msg = result["choices"][0]["message"]
    messages.append(assistant_msg)

    tool_calls = assistant_msg.get("tool_calls", [])
    if not tool_calls:
        return messages, assistant_msg.get("content", "模型没有返回内容")

    # 执行工具
    for tc in tool_calls:
        func_name = tc["function"]["name"]
        args = json.loads(tc["function"]["arguments"])

        if func_name == "get_weather":
            city = args.get("city")
            result_text = get_weather(city)
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result_text
            })

    # 第二次调用模型，生成最终回答
    final_data = {
        "model": "deepseek-chat",
        "messages": messages
    }
    final_resp = requests.post(url, headers=headers, json=final_data)
    final_result = final_resp.json()
    final_msg = final_result["choices"][0]["message"]
    messages.append(final_msg)

    return messages, final_msg.get("content", "")


# ========== Streamlit 界面 ==========
st.set_page_config(page_title="天气助手 Agent", page_icon="🌤️")
st.title("🌤️ AI 天气助手")

st.markdown("""
👋 我可以帮你查询实时天气！
试试输入：**北京今天天气怎么样？** 或者 **上海和杭州哪个更暖和？**
""")

# 初始化对话历史
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": "你是天气助手，可以查询实时天气，回答时参考历史对话。"}]
    st.session_state.chat_history = []

# 显示历史消息
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 输入框
user_input = st.chat_input("输入你的问题...")

if user_input:
    # 显示用户消息
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    # 运行 Agent
    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            messages, response = run_agent(user_input, st.session_state.messages)
            st.session_state.messages = messages
            st.markdown(response)
    st.session_state.chat_history.append({"role": "assistant", "content": response})