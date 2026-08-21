"""
小哈 AI Agent - Gradio 网页界面
运行方式：python app.py
浏览器访问：http://127.0.0.1:7860
"""
import gradio as gr
import os

# 导入主程序中的持久化函数
from say import (
    load_config,
    load_notebook,
    save_notebook,
    load_history,
    save_history,
)

# 导入 LangChain 工具和 Agent
from tools.langchain_tools import build_tools, run_agent, llm

# ======================== 初始化数据 ========================
user_name = load_config()
notebook = load_notebook()
history = load_history()

# ======================== 聊天处理函数 ========================
def chat(message, chat_history):
    """
    Gradio 回调函数：处理用户输入，返回更新后的聊天记录
    chat_history 格式：新版 Gradio 使用字典列表，每个元素为 {"role": "user"/"assistant", "content": "..."}
    """
    global history, notebook

    # 1. 记录用户消息到内部历史
    history.append({"role": "user", "content": message})

    # 2. 构建本次对话的工具列表
    tools = build_tools(user_name, notebook)

    # 3. 调用 JSON 决策 Agent
    try:
        reply = run_agent(
            user_input=message,
            user_name=user_name,
            notebook=notebook,
            llm=llm,
            tools=tools,
            verbose=False,
            max_steps=8
        )
    except Exception as e:
        reply = f"内部处理错误：{e}"

    # 4. 记录 AI 回复到内部历史
    history.append({"role": "ai", "content": reply})

    # 5. 保存数据（保证重启后记忆不丢失）
    save_history(history)
    save_notebook(notebook)

    # 6. 更新 Gradio 聊天记录（新版 Gradio 使用字典格式）
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
    gr.Markdown(
        f"# 小哈 AI Agent 👋\n你好，**{user_name}**！我是你的智能助手，可以查天气、讲笑话、记笔记、算数学、做翻译。"
    )

    chatbot = gr.Chatbot(label="对话记录", height=400)
    msg = gr.Textbox(label="输入你的问题", placeholder="例如：北京天气 / 计算 2+3*4 / 翻译 苹果 到英文")
    clear = gr.Button("清空对话")

    # 绑定事件：按回车或点击发送
    msg.submit(chat, inputs=[msg, chatbot], outputs=[msg, chatbot])
    clear.click(clear_chat, outputs=chatbot)

# ======================== 启动服务 ========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port, share=False)