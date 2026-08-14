import json
import requests
import os
import re
from dotenv import load_dotenv

load_dotenv()
DEBUG = False

def agent_loop(user_input, history, tool_executors, max_steps=10):
    api_key = os.getenv("LLM_API_KEY")
    url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL")

    from tools import weather, joke, time_tool, notebook,calculator, translator

    tool_descriptions = [
        weather.DESCRIPTION,
        joke.DESCRIPTION,
        time_tool.DESCRIPTION,
        notebook.DESCRIPTION,
        calculator.DESCRIPTION,
        translator.DESCRIPTION,
    ]
    tools_text = "\n".join(tool_descriptions)

    system_prompt = (
            "你是一个助手，必须一步一步地完成任务，每次只输出一个 JSON 对象。\n"
        "可用工具：\n" + tools_text + "\n\n"
    "规则：\n"
    "- 如果需要调用工具，输出：{\"thought\": \"...\", \"action\": {\"tool\": \"...\", \"arg\": \"...\"}, \"final_answer\": null}\n"
    "- 如果任务全部完成，输出：{\"thought\": \"\", \"action\": null, \"final_answer\": \"你的回复\"}\n"
    "- 如果用户要求查询多个城市的天气，你必须分别查询每个城市，每次只查一个。\n"
    "- 当用户要求查看、列出、搜索记事本内容时，你必须调用 notebook 工具（arg 为 \"看看\" 或 \"找 关键词\"）。严禁自己编造或总结记事本内容，所有数据必须来自工具执行结果。\n"
    "- 永远只输出一个 JSON 对象，不要输出计划列表或多行 JSON。\n"
    )
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        recent = history[-20:] if len(history) > 20 else history
        for msg in recent:
            role = "assistant" if msg["role"] == "ai" else msg["role"]
            messages.append({"role": role, "content": msg["content"]})
    messages.append({"role": "user", "content": user_input})

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    task_messages = []
    step = 0
    retry_json = 0

    while step < max_steps:
        step += 1

        MAX_MSG = 22  # 保留 system prompt + 最近 22 条消息
        if len(messages) > MAX_MSG:
            # 保留 system prompt (第一条)，然后保留最后 MAX_MSG-1 条
            messages = [messages[0]] + messages[-(MAX_MSG - 1):]

        payload = {"model": model, "messages": messages, "temperature": 0}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            raw_content = resp.json()["choices"][0]["message"]["content"].strip()

            if DEBUG:
                print("DEBUG 模型原始输出:", repr(raw_content))

            content = raw_content.strip()
            # 去除 Markdown 代码块
            if content.startswith("```"):
                content = content.split("\n", 1)[-1]  # 去掉第一行 ```
                if content.endswith("```"):
                    content = content[:-3].strip()
                content = content.strip()

            # 先尝试直接解析整个内容（支持多行 JSON）
            decision = None
            try:
                decision = json.loads(content)
            except json.JSONDecodeError:
                # 如果失败，尝试逐行拼接直到能解析成功
                lines = content.split("\n")
                json_str = ""
                for line in lines:
                    json_str += line
                    try:
                        decision = json.loads(json_str)
                        break
                    except json.JSONDecodeError:
                        continue
                if decision is None:
                    # 最后兜底：正则提取第一个 {...}
                    matches = re.findall(r'\{.*?\}', content, re.DOTALL)
                    if matches:
                        try:
                            decision = json.loads(matches[0])
                        except json.JSONDecodeError:
                            pass

            # 如果上面还没解析出来，进入纯文本 / 扁平 JSON 等兜底处理
            if decision is None:
                # 处理纯文本 "weather\n惠州"
                lines = content.split('\n')
                if len(lines) >= 2 and lines[0].strip() in tool_executors:
                    tool_name = lines[0].strip()
                    arg = lines[1].strip() if len(lines) > 1 else ""
                    observation = tool_executors[tool_name](arg)
                    messages.append({"role": "assistant", "content": content})
                    messages.append({"role": "user", "content": f"工具执行结果：{observation}"})
                    task_messages.append({"role": "user", "content": f"工具结果：{observation}"})
                    continue

                # 尝试扁平 JSON 直接执行
                executed = False
                try:
                    flat = json.loads(content)
                    if isinstance(flat, dict):
                        for t_name in tool_executors:
                            if t_name in flat:
                                arg = flat[t_name]
                                observation = tool_executors[t_name](arg)
                                messages.append({"role": "assistant", "content": content})
                                messages.append({"role": "user", "content": f"工具执行结果：{observation}"})
                                thought = flat.get("thought", "")
                                if thought:
                                    task_messages.append({"role": "assistant", "content": thought})
                                task_messages.append({"role": "user", "content": f"工具结果：{observation}"})
                                executed = True
                                break
                        if not executed and "final_answer" in flat:
                            final_text = flat["final_answer"]
                            task_messages.append({"role": "assistant", "content": final_text})
                            return generate_final_reply(task_messages)
                except:
                    pass

                if not executed:
                    # 正则提取最后一个 JSON 块（兜底）
                    matches = re.findall(r'\{.*?\}', content, re.DOTALL)
                    if matches:
                        try:
                            decision = json.loads(matches[-1])
                        except json.JSONDecodeError:
                            decision = None
                    else:
                        decision = None
                else:
                    continue

            # 注意：如果 decision 已在上面的新解析逻辑中被赋值，会直接跳到这里

            if decision is None:
                # 如果解析不出 JSON，且内容不是工具命令，则视为普通文本回复
                # 直接返回给用户，不再重试或显示错误
                return raw_content

            # 最终答案
            if decision.get("final_answer"):
                final_text = decision["final_answer"]
                task_messages.append({"role": "assistant", "content": final_text})
                # 调用润色生成器，返回生动回复
                return generate_final_reply(task_messages)

            if not decision.get("action") and not decision.get("final_answer"):
                if not decision.get("action") and not decision.get("final_answer"):
                    # 模型给了 JSON 但没动作也没答案，可能是想偷懒自己编内容
                    if retry_json < 1:
                        retry_json += 1
                        messages.append({
                            "role": "user",
                            "content": "你必须调用相应的工具来获取真实数据，不能自己编造或总结。请输出一个包含 action 的 JSON，或者如果任务确实无法完成，请给出 final_answer。"
                        })
                        continue
                    else:
                        return "抱歉，我没能获取到记事本内容，请再试一次。"

            action = decision.get("action")
            if not action:
                # 没有 action 也没有 final_answer，再给一次机会
                if retry_json < 1:
                    retry_json += 1
                    messages.append({"role": "user", "content": "请决定：要么给出下一步 action，要么直接给出 final_answer 结束任务。必须输出 JSON。"})
                    continue
                else:
                    return "抱歉，我没想好怎么处理这个请求，可以换种方式描述吗？"

            tool_name = action.get("tool")
            arg = action.get("arg", "")
            if tool_name not in tool_executors:
                observation = f"未知工具：{tool_name}"
            else:
                try:
                    observation = tool_executors[tool_name](arg)
                except Exception as e:
                    observation = f"工具执行失败：{e}"

            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": f"工具执行结果：{observation}"})

            # 如果查看/搜索记事本，直接返回原始结果，避免被润色概括
            if tool_name == "notebook" and ("看看" in arg or "找" in arg):
                return observation

            thought = decision.get("thought", "")
            if thought:
                task_messages.append({"role": "assistant", "content": thought})
            task_messages.append({"role": "user", "content": f"工具结果：{observation}"})

        except requests.RequestException as e:
            return f"Agent 网络请求出错：{e}"
        except Exception as e:
            return f"Agent 循环出错：{e}"

    return "抱歉，我思考了太久，没能完成你的任务。"


def generate_final_reply(messages, style="可爱"):
    """根据对话历史生成自然语言回复"""
    api_key = os.getenv("LLM_API_KEY")
    url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL")

    system_prompt = (
    f"你是小哈，一个{style}的AI助手。"
    "请根据以下对话历史和工具执行结果，用亲切、活泼的语气回复用户。"
    "【必须遵守】如果工具结果中包含列表或多条记录，你必须将它们**逐条、完整、原样**地列出来，绝对不可以概括、总结或删减任何一条。"
    "你可以适当使用颜文字和语气词，但数据部分必须完整复制。"
    )

    full_messages = [{"role": "system", "content": system_prompt}] + messages

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": full_messages,
        "temperature": 0.9,
        "max_tokens": 500
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        # 如果润色失败，返回最后一条 assistant 内容（即原始的 final_answer）
        for msg in reversed(messages):
            if msg["role"] == "assistant":
                return msg["content"]
        return f"小哈组织语言时出了点问题，但任务已完成。"
