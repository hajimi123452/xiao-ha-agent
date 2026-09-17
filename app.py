"""
小哈 AI Agent · Gradio 网页界面
================================
运行方式：python app.py
浏览器访问：http://127.0.0.1:7860

界面结构
--------
┌──────────────────────────────────────────────┐
│ 顶部品牌区：头像 / 标题 / 当前用户            │
├───────────────────────────┬──────────────────┤
│ 对话区                    │ 侧边栏           │
│  · 示例问题（一键提问）   │  · 知识库上传    │
│  · 对话记录（气泡样式）   │  · 图片理解      │
│  · 语音回复播放器         │  · 语音输入      │
│  · 输入框 / 发送 / 清空   │  · 用户设置      │
└───────────────────────────┴──────────────────┘
"""

import base64
import os
import queue
import threading
import time
from html import escape

import gradio as gr
from dotenv import load_dotenv
from langchain_core.caches import InMemoryCache
from langchain_core.globals import set_llm_cache
from langchain_core.messages import AIMessage, HumanMessage

set_llm_cache(InMemoryCache())
load_dotenv()

# 导入主程序中的持久化函数
from say import (  # noqa: E402
    load_config,
    load_notebook,
    save_notebook,
    load_history,
    save_history,
    safe_load_json,
    safe_dump_json,
)

# 导入 LangChain 工具和 Agent
from tools.langchain_tools import build_tools, run_agent, llm  # noqa: E402
from tools.rag_engine import add_documents_to_kb, initialize_knowledge_base  # noqa: E402
from tools.stt_tool import speech_to_text  # noqa: E402
from tools.tts_tool import text_to_speech  # noqa: E402
from tools.vision_tool import image_understanding  # noqa: E402

# ======================== 常量与初始化 ========================
CONFIG_PATH = "config.json"
ASSISTANT_NAME = "小哈"
BRAND_EMOJI = "🐾"
HISTORY_PATH = "chat_history.json"
NOTEBOOK_PATH = "notebook.json"
STATUS_IDLE = "✅ 就绪 · 随时可以开始对话"

CAPABILITIES = [
    "🌤️ 查天气",
    "🕒 问时间",
    "😂 讲笑话",
    "🧮 算数学",
    "🌐 联网搜索",
    "📚 知识库问答",
    "🖼️ 图片理解",
    "🎤 语音输入",
    "🔊 语音播报",
]

EXAMPLES = [
    "帮我查一下北京现在的天气",
    "计算 (128 + 372) * 3 / 5",
    "翻译 今天天气真不错 到英文",
    "记事本记一下 周五下午三点开会",
    "来个笑话放松一下",
    "现在几点了？",
]


def _avatar_svg(emoji, bg_from, bg_to):
    """生成内嵌 SVG 头像（不依赖任何图片文件）。"""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0%" stop-color="{bg_from}"/><stop offset="100%" stop-color="{bg_to}"/>'
        "</linearGradient></defs>"
        '<rect width="96" height="96" rx="48" fill="url(#g)"/>'
        f'<text x="48" y="62" font-size="46" text-anchor="middle">{emoji}</text>'
        "</svg>"
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


AVATARS = (
    _avatar_svg("🙋", "#6366f1", "#8b5cf6"),   # 用户头像
    _avatar_svg(BRAND_EMOJI, "#0ea5e9", "#6366f1"),  # 小哈头像
)


def load_user_name(config_path=CONFIG_PATH):
    """读取用户称呼。

    网页版不能像命令行那样 input() 阻塞等待输入，
    所以没有配置时直接使用默认称呼，之后可在侧边栏「用户设置」里修改。
    """
    config = safe_load_json(config_path, {})
    name = str(config.get("user_name", "") or "").strip()
    return name or "朋友"


def save_user_name(name, config_path=CONFIG_PATH):
    name = (name or "").strip()
    if not name:
        return "称呼不能为空哦"
    config = safe_load_json(config_path, {})
    config["user_name"] = name
    safe_dump_json(config, config_path)
    return f"已记住：以后就叫你「{name}」啦 ✅"


# ======================== 启动时加载持久化数据 ========================
user_name = load_user_name()
notebook = load_notebook()
history = load_history()
initialize_knowledge_base()


# ======================== 工具函数 ========================
def polish(text):
    """把模型返回的纯文本整理成更适合网页阅读的 Markdown。"""
    if not text:
        return "（这次我没有生成内容，换个说法再问我一次试试～）"
    lines = [line.rstrip() for line in str(text).replace("\r\n", "\n").split("\n")]
    out, buf = [], []

    def flush():
        if buf:
            out.append(" ".join(buf).strip())
            buf.clear()

    for line in lines:
        if not line.strip():
            flush()
            out.append("")
        elif line.lstrip().startswith(("#", "-", "*", ">", "|", "```", "1.", "2.", "3.")):
            flush()
            out.append(line)
        else:
            buf.append(line.strip())
    flush()

    cleaned = "\n".join(out).strip()
    while "\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n", "\n\n")
    return cleaned


def history_to_chatbot(records):
    """把持久化的历史记录转换成 Chatbot 需要的消息格式。"""
    messages = []
    for item in records or []:
        try:
            role = item.get("role")
            content = item.get("content", "")
        except AttributeError:
            continue
        messages.append(
            {"role": "user" if role == "user" else "assistant", "content": content}
        )
    return messages


def conversation_stats(records):
    """统计对话轮次，用于顶部信息条。"""
    turns = sum(1 for item in (records or []) if item.get("role") == "user")
    return f"💬 已对话 {turns} 轮"


def build_header(name, records):
    """渲染顶部品牌区（跟随用户称呼与对话轮次更新）。"""
    chips = "".join(f'<span class="xh-chip">{c}</span>' for c in CAPABILITIES)
    return f"""
<div class="xh-header-inner">
  <div class="xh-brand">
    <div class="xh-logo">{BRAND_EMOJI}</div>
    <div>
      <div class="xh-title-row">
        <h1 class="xh-title">{ASSISTANT_NAME}</h1>
        <span class="xh-badge">AI Agent</span>
      </div>
      <p class="xh-subtitle">
        你好，<strong>{escape(name)}</strong>！我是你的智能助手，
        能查天气、算数学、做翻译、记笔记、搜资料、看图片、开口说话。
      </p>
      <div id="xh-capabilities">{chips}</div>
    </div>
  </div>
  <div class="xh-user-chip">🙋 {escape(name)} · {conversation_stats(records)}</div>
</div>
"""


def build_tips():
    return (
        "<strong>小贴士</strong><br>"
        "· 输入框里按 <code>Enter</code> 直接发送<br>"
        "· 按 <code>Ctrl / ⌘ + Enter</code> 也能发送<br>"
        "· 说话啰嗦一点也没关系，我能自己挑工具<br>"
        "· 上传文档后问我文档里的问题，我会先查知识库"
    )


def run_agent_live(message, timeout_per_tick=0.4):
    """在线程里跑 Agent，边跑边汇报状态，避免界面看起来卡死。

    注意：这里传入的是「本轮之前」的历史，当前这句话由 run_agent 的
    user_input 参数单独传入，避免同一条消息在上下文里出现两次。

    产出：(status_text, reply_or_None, elapsed_seconds, finished)
    """
    snap_notebook = list(notebook)
    snap_history = list(history)

    result: dict = {}
    box: "queue.Queue" = queue.Queue()

    def worker():
        try:
            result["reply"] = run_agent(
                user_input=message,
                history=snap_history,
                user_name=user_name,
                notebook=snap_notebook,
                llm=llm,
                tools=build_tools(user_name, snap_notebook),
                verbose=False,
                max_steps=8,
            )
        except Exception as exc:  # noqa: BLE001 - 兜底，绝不让页面崩掉
            import traceback

            traceback.print_exc()
            result["reply"] = f"内部处理错误：{exc}"
            result["error"] = str(exc)
        finally:
            box.put(True)

    thread = threading.Thread(target=worker, daemon=True)
    started = time.time()
    thread.start()

    yield f"🤔 {ASSISTANT_NAME}正在思考…", None, 0.0, False

    while True:
        try:
            box.get(timeout=timeout_per_tick)
            break
        except queue.Empty:
            elapsed = time.time() - started
            yield f"🔎 正在理解你的问题…（{elapsed:.0f}s）", None, elapsed, False

    elapsed = time.time() - started
    reply = polish(result.get("reply", ""))

    # 记事本等工具可能在运行中修改了 notebook，这里同步回全局并落盘
    if snap_notebook != notebook:
        notebook.clear()
        notebook.extend(snap_notebook)
        save_notebook(notebook)

    status = f"✅ 回答完成 · 用时 {elapsed:.1f} 秒"
    yield status, reply, elapsed, True


# ======================== 事件处理函数 ========================
def respond(message, chat_history, audio_enabled):
    """聊天主流程：思考 → 流式吐字 → 语音播报。"""
    message = (message or "").strip()
    if not message:
        yield "", chat_history, None, "💡 先输入一句话再发送吧"
        return

    chat_history = list(chat_history or [])
    chat_history.append({"role": "user", "content": message})
    chat_history.append({"role": "assistant", "content": ""})

    # 1) 思考中：先让用户看到"正在处理"
    yield "", chat_history, None, f"🤔 {ASSISTANT_NAME}正在思考…"

    reply = ""
    status = STATUS_IDLE
    for status, reply, _elapsed, finished in run_agent_live(message):
        if finished:
            break
        yield "", chat_history, None, status

    # 2) 流式吐字（保留打字机手感，但比逐字符快很多）
    if reply:
        chat_history[-1] = {"role": "assistant", "content": "…"}
        step = 3
        for i in range(0, len(reply), step):
            chat_history[-1] = {"role": "assistant", "content": reply[: i + step]}
            yield "", chat_history, None, status
            time.sleep(0.012)
        chat_history[-1] = {"role": "assistant", "content": reply}
        yield "", chat_history, None, status

    # 3) 落盘对话历史（保证刷新/重启后还有记忆）
    history.append({"role": "user", "content": message})
    history.append({"role": "ai", "content": reply})
    save_history(history)

    # 4) 语音播报（可开关）
    if audio_enabled:
        yield "", chat_history, None, "🔊 正在合成语音…"
        audio_path = text_to_speech(reply, output_path="reply.mp3")
    else:
        audio_path = None

    yield "", chat_history, audio_path, status


def clear_chat():
    """清空对话：界面 + 持久化记忆一起清空，避免"删了还记得"。"""
    global history
    history = []
    save_history(history)
    return [], None, STATUS_IDLE


def upload_file(files):
    if not files:
        return "请先选择要上传的文档（支持 .txt / .md / .pdf）"
    paths = []
    for item in files if isinstance(files, (list, tuple)) else [files]:
        path = getattr(item, "name", None) or (item if isinstance(item, str) else None)
        if path:
            paths.append(path)
    if not paths:
        return "读取文件路径失败，请重新选择文件"
    names = "、".join(os.path.basename(p) for p in paths)
    try:
        result = add_documents_to_kb(paths)
    except Exception as exc:  # noqa: BLE001
        return f"上传失败：{exc}"
    return f"{result}\n文件：{names}"


def describe_image(image_path, question):
    if not image_path:
        return "请先上传一张图片"
    prompt = (question or "").strip() or None
    try:
        if prompt:
            return image_understanding.invoke({"image_path": image_path, "question": prompt})
        return image_understanding.invoke({"image_path": image_path})
    except Exception as exc:  # noqa: BLE001
        return f"图片理解失败：{exc}"


def transcribe_audio(audio_path):
    if not audio_path:
        return "", "请先录音，或者上传一段音频文件"
    try:
        text = speech_to_text(audio_path)
    except Exception as exc:  # noqa: BLE001
        return "", f"语音识别失败：{exc}"
    return text, "识别完成，可以直接发送 🎤"


def update_name(new_name):
    global user_name
    message = save_user_name(new_name)
    if (new_name or "").strip():
        user_name = new_name.strip()
    return message, build_header(user_name, history)


def fill_example(text):
    """把示例问题填入输入框，用户确认后再发送。"""
    return gr.update(value=text)


# ======================== 构建 Gradio 界面 ========================
THEME = gr.themes.Soft(
    primary_hue=gr.themes.colors.indigo,
    secondary_hue=gr.themes.colors.violet,
    neutral_hue=gr.themes.colors.slate,
    radius_size=gr.themes.sizes.radius_lg,
    font=[gr.themes.GoogleFont("Inter"), "PingFang SC", "Microsoft YaHei", "sans-serif"],
    font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "ui-monospace", "monospace"],
)

CSS_PATH = os.path.join("frontend", "styles.css")
JS_PATH = os.path.join("frontend", "app.js")

with gr.Blocks(title=f"{ASSISTANT_NAME} AI Agent", fill_width=True) as demo:
    header = gr.HTML(build_header(user_name, history), elem_id="xh-header")

    with gr.Row(elem_id="xh-main"):
        # ------------------------------ 左：对话主区 ------------------------------
        with gr.Column(scale=7, elem_id="xh-chat-col"):
            with gr.Accordion("💡 试试这样问我（点击即可填入输入框）", open=False, elem_id="xh-examples"):
                example_buttons = []
                with gr.Row():
                    for text in EXAMPLES:
                        example_buttons.append(
                            gr.Button(text, size="sm", variant="secondary", min_width=120)
                        )

            chatbot = gr.Chatbot(
                value=history_to_chatbot(history),
                elem_id="xh-chatbot",
                height=430,
                show_label=False,
                layout="bubble",
                placeholder=(
                    f"<div style='text-align:center;padding:36px 12px'>"
                    f"<div style='font-size:44px'>{BRAND_EMOJI}</div>"
                    f"<div style='font-size:17px;font-weight:700;margin-top:10px'>"
                    f"你好，我是{ASSISTANT_NAME}</div>"
                    f"<div style='margin-top:6px;font-size:14px'>"
                    f"问天气、算数学、做翻译、记笔记、查资料、看图片，都可以交给我</div></div>"
                ),
                buttons=["copy"],
                group_consecutive_messages=False,
                render_markdown=True,
                avatar_images=AVATARS,
                # 关闭 Gradio 自带的强制滚动，改由 frontend/app.js 智能判断：
                # 用户往上翻历史时绝不打断，只有贴着底部时才跟随新消息
                autoscroll=False,
            )

            audio_output = gr.Audio(
                label="🔊 语音回复（浏览器可能会拦截自动播放，点一下播放即可）",
                type="filepath",
                autoplay=True,
                elem_id="xh-audio",
                show_label=True,
            )

            with gr.Row(elem_id="xh-input"):
                msg = gr.Textbox(
                    value="",
                    placeholder="说点什么吧～ 例如：帮我查一下上海天气 / 计算 12*8+5 / 记事本记一下 明天交作业",
                    show_label=False,
                    lines=2,
                    max_lines=6,
                    autofocus=True,
                    container=True,
                    submit_btn="发送 ➤",
                    stop_btn="⏹ 停止",
                )

            with gr.Row():
                clear_btn = gr.Button(
                    "🧹 清空对话（同时清空记忆）",
                    variant="secondary",
                    elem_id="xh-clear",
                    size="sm",
                )

            status = gr.Textbox(
                value=STATUS_IDLE,
                show_label=False,
                interactive=False,
                elem_id="xh-status",
            )

        # ------------------------------ 右：功能侧边栏 ------------------------------
        with gr.Column(scale=4, elem_id="xh-side-col"):
            with gr.Column(elem_id="xh-side"):
                gr.Markdown("### ⚙️ 功能面板")

                with gr.Accordion("📄 知识库上传", open=True):
                    gr.HTML(
                        '<div class="xh-hint">上传文档后，我回答问题时会优先查阅知识库内容。</div>'
                    )
                    file_input = gr.File(
                        label="选择文档",
                        file_count="multiple",
                        file_types=[".txt", ".md", ".pdf"],
                        height=130,
                    )
                    upload_button = gr.Button("上传并加入知识库", variant="primary")
                    upload_status = gr.Textbox(
                        label="上传状态", interactive=False, lines=2, show_label=True
                    )

                with gr.Accordion("🖼️ 图片理解", open=False):
                    gr.HTML(
                        '<div class="xh-hint">上传图片，再补充一句你想问的问题（可留空，默认描述图片）。</div>'
                    )
                    image_input = gr.Image(type="filepath", label="上传图片", height=150)
                    image_question = gr.Textbox(
                        label="想了解什么？（选填）",
                        placeholder="例如：图里有几个人？",
                        lines=1,
                    )
                    image_button = gr.Button("开始描述图片", variant="primary")
                    image_output = gr.Textbox(
                        label="图片描述",
                        lines=5,
                        interactive=False,
                        show_label=True,
                        buttons=["copy"],
                    )

                with gr.Accordion("🎤 语音输入", open=False):
                    gr.HTML(
                        '<div class="xh-hint">点红色按钮录音，识别结果会填入输入框，确认后再发送。</div>'
                    )
                    audio_input = gr.Audio(
                        sources=["microphone", "upload"],
                        type="filepath",
                        label="录音 / 上传音频",
                    )
                    transcribe_button = gr.Button("识别语音", variant="primary")
                    transcribed_text = gr.Textbox(
                        label="识别结果（可直接编辑后发送）", lines=2
                    )

                with gr.Accordion("🙋 用户设置", open=False):
                    name_input = gr.Textbox(
                        label="怎么称呼你？", value=user_name, lines=1
                    )
                    with gr.Row():
                        name_save = gr.Button("保存称呼", variant="primary")
                        audio_toggle = gr.Checkbox(
                            value=True, label="回答后语音播报", container=True
                        )
                    name_status = gr.Textbox(
                        label="设置状态", interactive=False, lines=1, show_label=False
                    )

            gr.HTML(build_tips(), elem_id="xh-tips")

    # ============================ 事件绑定 ============================
    outputs = [msg, chatbot, audio_output, status]

    msg.submit(respond, [msg, chatbot, audio_toggle], outputs)

    clear_btn.click(clear_chat, None, [chatbot, audio_output, status])

    for btn, example in zip(example_buttons, EXAMPLES):
        btn.click(lambda text=example: fill_example(text), None, msg)

    upload_button.click(upload_file, file_input, upload_status)
    image_button.click(describe_image, [image_input, image_question], image_output)
    transcribe_button.click(transcribe_audio, audio_input, [transcribed_text, status])
    name_save.click(update_name, name_input, [name_status, header])

    demo.load(lambda: (build_header(user_name, history),), None, header)


# ======================== 启动服务 ========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    launch_kwargs = dict(
        server_name=os.environ.get("HOST", "0.0.0.0"),
        server_port=port,
        share=False,
        theme=THEME,
        show_error=True,
    )
    if os.path.exists(CSS_PATH):
        launch_kwargs["css_paths"] = [CSS_PATH]
    if os.path.exists(JS_PATH):
        launch_kwargs["js"] = open(JS_PATH, "r", encoding="utf-8").read()

    print(f"🐾 {ASSISTANT_NAME} AI Agent 启动中…  http://127.0.0.1:{port}")
    demo.launch(**launch_kwargs)
