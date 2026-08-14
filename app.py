"""
小哈 AI Agent - Gradio 网页界面
运行方式：python app.py
浏览器访问：http://127.0.0.1:7860
"""
import gradio as gr
import json

# 导入主程序中的持久化函数和工具
from say import (
    load_config,
    load_notebook,
    save_notebook,
    load_history,
    save_history,
)
from tools.llm_engine import agent_loop

# 导入工具模块
from tools import weather, joke, time_tool, calculator, translator
import tools.notebook as notebook_tool

# ======================== 初始化数据 ========================
user_name = load_config()
notebook = load_notebook()
history = load_history()

# ======================== 定义工具执行器（与主程序保持一致） ========================
tool_executors = {
    "weather": lambda arg: weather.run(f"天气 {arg}"),
    "joke": lambda arg: joke.run(),
    "time": lambda arg: time_tool.run(),
    "name": lambda arg: f"{user_name}你好！我叫小哈，是你的第一个AI Agent雏形！",
    "notebook": lambda arg: notebook_tool.run(notebook, f"记事本 {arg}"),
    "calculator": lambda arg: calculator.run(f"计算 {arg}"),
    "translator": lambda arg: translator.run(f"翻译 {arg}"),
}


# ======================== 聊天处理函数 ========================
def chat(message, chat_history):
    """
    Gradio 回调函数：处理用户输入，返回更新后的聊天记录
    chat_history 格式：[(用户消息, 机器人回复), ...]
    """
    global history, notebook

    # 1. 记录用户消息到内部历史
    history.append({"role": "user", "content": message})

    # 2. 调用 Agent 循环
    try:
        reply = agent_loop(message, history, tool_executors)
    except Exception as e:
        reply = f"内部处理错误：{e}"

    # 3. 记录 AI 回复到内部历史
    history.append({"role": "ai", "content": reply})

    # 4. 保存数据（保证重启后记忆不丢失）
    save_history(history)
    save_notebook(notebook)

    # 5. 更新 Gradio 聊天记录
    chat_history.append({"role": "user", "content": message})
    chat_history.append({"role": "assistant", "content": reply})
    return "", chat_history


def clear_chat():
    """清空当前对话历史（可选）"""
    global history
    history = []
    save_history(history)
    return []  # 返回空列表以清空聊天框


# ======================== 构建 Gradio 界面 ========================
with gr.Blocks(title="小哈 AI Agent", theme=gr.themes.Soft()) as demo:
    gr.Markdown(f"# 小哈 AI Agent 👋\n你好，**{user_name}**！我是你的智能助手，可以查天气、讲笑话、记笔记、算数学、做翻译。")

    chatbot = gr.Chatbot(label="对话记录", height=400)
    msg = gr.Textbox(label="输入你的问题", placeholder="例如：北京天气 / 计算 2+3*4 / 翻译 苹果 到英文")
    clear = gr.Button("清空对话")

    # 绑定事件：按回车或点击发送
    msg.submit(chat, inputs=[msg, chatbot], outputs=[msg, chatbot])
    clear.click(clear_chat, outputs=chatbot)

# ======================== 启动服务 ========================
if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False)