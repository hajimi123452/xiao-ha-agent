"""
小哈 AI Agent 小最终版
功能：聊天、记事本、笑话、时间查询、用户配置记忆
持久化：chat_history.json / notebook.json / config.json
特性：全面异常处理，任何情况下都不会崩溃退出
"""

import datetime
import random
import json
import os
import requests

from tools.llm_engine import agent_loop
from dotenv import load_dotenv

from tools import weather
from tools import joke
from tools import time_tool
from tools import calculator, translator
import tools.notebook as notebook_tool

load_dotenv()  # 加载 .env
# ======================== 文件 I/O 安全封装 ========================
def safe_load_json(filepath, default):
    """安全读取 JSON 文件，失败时返回默认值"""
    try:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, PermissionError, OSError) as e:
        print(f"[警告] 读取 {filepath} 失败: {e}")
    return default


def safe_dump_json(data, filepath):
    """安全保存 JSON 文件，失败时打印警告"""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except (PermissionError, OSError) as e:
        print(f"[警告] 保存 {filepath} 失败: {e}")


# ======================== 配置管理 ========================
def load_config(config_path="config.json"):
    """加载用户配置，若无则询问并创建"""
    config = safe_load_json(config_path, {})
    user_name = config.get("user_name", "")

    if not user_name:
        try:
            user_name = input("你好，我是小哈，请问怎么称呼你？ ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n好的，我就叫你“朋友”吧。")
            user_name = "朋友"
        config["user_name"] = user_name
        safe_dump_json(config, config_path)
        print(f"已记住你的名字：{user_name}")
    return user_name


def load_notebook(notebook_path="notebook.json"):
    data = safe_load_json(notebook_path, [])
    if not isinstance(data, list):
        print("[警告] 记事本格式损坏，已重置")
        return []
    return data

def save_notebook(notebook, notebook_path="notebook.json"):
    safe_dump_json(notebook, notebook_path)


# ======================== 历史记录（角色消息） ========================
def load_history(history_path="chat_history.json"):
    """加载聊天历史，格式 [{"role":"user/ai","content":"..."}]"""
    data = safe_load_json(history_path, [])
    if not isinstance(data, list):
        print("[警告] 聊天历史格式损坏，已重置")
        return []
    # 过滤掉结构不正确的条目
    clean = []
    for item in data:
        if isinstance(item, dict) and "role" in item and "content" in item:
            clean.append(item)
    return clean


def save_history(history, history_path="chat_history.json"):
    safe_dump_json(history, history_path)



def format_history(history):
    """格式化打印历史记录"""
    if not history:
        return "还没有记录。"
    lines = ["--- 聊天记录 ---"]
    for msg in history:
        role = "你" if msg["role"] == "user" else "小哈"
        lines.append(f"{role}：{msg['content']}")
    lines.append("----------------")
    return "\n".join(lines)


def handle_multi_city_weather(user_input):
    """检测多城市天气查询，直接调用天气工具，返回合并结果或 None"""
    if "天气" not in user_input:
        return None

    connectors = ["和", "跟", "以及", "还有", "与"]
    if not any(conn in user_input for conn in connectors):
        return None

    # 清理常见干扰词
    text = user_input
    for word in ["帮我", "请", "查", "一下", "天气", "的"]:
        text = text.replace(word, "")

    # 按连接词分割
    parts = [text]
    for conn in connectors:
        new_parts = []
        for p in parts:
            new_parts.extend(p.split(conn))
        parts = [p.strip() for p in new_parts if p.strip()]

    # 过滤掉空字符串，得到城市列表
    cities = [p for p in parts if p]
    if len(cities) < 2:
        return None

    # 分别查询每个城市的天气
    results = []
    for city in cities:
        result = weather.run(f"天气 {city}")
        results.append(result)

    return "\n".join(results)
# ======================== 主程序 ========================
def main():
    # 1. 加载配置
    user_name = load_config()

    # 2. 加载持久化数据
    notebook = load_notebook()
    history = load_history()

    print(f"我是小哈AI助手，{user_name}，有什么可以帮你？")

    # 3. 主循环
    while True:
        try:
            # 获取用户输入（防范 Ctrl+C / Ctrl+D）
            try:
                user_input = input("你问吧（输入0退出）：").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见，等你回来！")
                break

            if user_input == "0":
                print("再见，等你回来！")
                break

            if user_input.lower() == "history":
                print(format_history(history))
                continue

            HELP_KEYWORDS = ["帮助", "你能做什么", "功能", "怎么用", "help"]
            if any(kw in user_input for kw in HELP_KEYWORDS):
                reply_content = (
                    "我是小哈，你的智能助手～\n"
                    "我能帮你：\n"
                    "🌤 查天气（例如：北京天气）\n"
                    "🕒 看时间（例如：现在几点了）\n"
                    "😂 讲笑话（例如：来个笑话）\n"
                    "📒 记笔记（例如：记事本记一下 明天开会）\n"
                    "🔍 找笔记（例如：记事本找 天气）\n"
                    "有需要就直接告诉我吧！"
                )
                print(reply_content)  # 加上这一行
                history.append({"role": "ai", "content": reply_content})
                continue


            # 多城市天气直接处理
            multi_weather_reply = handle_multi_city_weather(user_input)
            if multi_weather_reply is not None:
                print(multi_weather_reply)
                history.append({"role": "user", "content": user_input})
                history.append({"role": "ai", "content": multi_weather_reply})
                continue


            # 记录用户消息
            history.append({"role": "user", "content": user_input})

            # 定义工具执行器（可以放在主循环外面，只定义一次）
            tool_executors = {
                "weather": lambda arg: weather.run(f"天气 {arg}"),
                "joke": lambda arg: joke.run(),
                "time": lambda arg: time_tool.run(),
                "name": lambda arg: f"{user_name}你好！我叫小哈，是你的第一个AI Agent雏形！",
                "notebook": lambda arg: notebook_tool.run(notebook, f"记事本 {arg}"),
                "calculator": lambda arg: calculator.run(f"计算 {arg}"),
                "translator": lambda arg: translator.run(f"翻译 {arg}")
            }

            # 生成回答（直接调用 agent_loop）
            try:
                reply_content = agent_loop(user_input, history, tool_executors)
            except Exception as e:
                reply_content = f"内部处理错误：{e}"
            # 输出回答
            print(reply_content)

            # 记录 AI 消息
            history.append({"role": "ai", "content": reply_content})

        except Exception as e:
            print(f"[错误] 发生未预料的异常：{e}")
            # 让循环继续，绝不死机

    # 4. 退出时保存所有数据
    try:
        save_history(history)
        save_notebook(notebook)
    except Exception as e:
        print(f"[警告] 退出时保存数据失败：{e}")


if __name__ == "__main__":
    main()