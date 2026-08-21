# tools/langchain_tools.py
import os
import json
import re
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_core.messages import AIMessage, HumanMessage

# 导入原有工具模块
from tools import weather, joke, time_tool, calculator, translator, notebook

load_dotenv()

# ========== 初始化 LLM ==========
base_url = os.getenv("LLM_BASE_URL", "").replace("/chat/completions", "")
llm = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "glm-4-flash"),
    api_key=os.getenv("LLM_API_KEY"),
    base_url=base_url,
    temperature=0,
)

# ========== 封装工具（无参数工具添加 dummy 默认参数） ==========
@tool
def weather_tool(city: str) -> str:
    """查询某个城市的实时天气。参数 city 是城市名称，例如：北京、上海。"""
    return weather.run(f"天气 {city}")

@tool
def joke_tool(dummy: str = "") -> str:
    """讲一个随机笑话。无需参数。"""
    return joke.run()

@tool
def time_tool_func(dummy: str = "") -> str:
    """获取当前日期和时间。无需参数。"""
    return time_tool.run()

@tool
def calculator_tool(expression: str) -> str:
    """计算数学表达式。参数 expression 是一个数学表达式字符串，例如 "2+3*4"。"""
    return calculator.run(f"计算 {expression}")

@tool
def translator_tool(text: str) -> str:
    """翻译文本。参数 text 的格式为 "翻译 <词语或句子> 到<中文/英文>"，例如 "翻译 苹果 到英文"。"""
    return translator.run(f"翻译 {text}")

def make_notebook_tool(notebook_list: list):
    @tool
    def notebook_tool(command: str) -> str:
        """操作记事本。参数 command 可以是：
        - "记一下 <内容>"：添加一条记录
        - "看看"：列出所有记录
        - "找 <关键词>"：搜索包含关键词的记录
        """
        return notebook.run(notebook_list, f"记事本 {command}")
    return notebook_tool

# ========== 构建工具列表 ==========
def build_tools(user_name: str, notebook_list: list):
    @tool
    def name_tool(dummy: str = "") -> str:
        """回答你的名字相关问题。无需参数。"""
        return f"{user_name}你好！我叫小哈，是你的AI助手。"

    return [
        weather_tool,
        joke_tool,
        time_tool_func,
        calculator_tool,
        translator_tool,
        make_notebook_tool(notebook_list),
        name_tool,
    ]

# ========== JSON 决策 Agent 循环 ==========
def run_agent(user_input, user_name, notebook, llm, tools, max_steps=8, verbose=False):
    """
    使用 JSON 决策的 Agent 循环，避免 ReAct 格式解析问题。
    """
    tool_descriptions = "\n".join([f"{t.name}: {t.description}" for t in tools])
    tool_names = ", ".join([t.name for t in tools])

    system_prompt = (
        "你是一个助手，可以调用工具来回答问题。你必须严格按照以下 JSON 格式回复，不要输出任何其他内容。\n\n"
        "如果你需要调用工具，输出：\n"
        '{{"tool": "工具名称", "arg": "工具参数"}}\n\n'
        "如果任务完成，输出：\n"
        '{{"final_answer": "你的最终回复"}}\n\n'
        "可用工具：\n" + tool_descriptions + "\n\n"
        f"注意：工具名称必须是 [{tool_names}] 之一。如果不需要工具，直接输出 final_answer。"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}")
    ])

    tool_map = {t.name: t for t in tools}

    scratchpad = []
    current_input = user_input

    for step in range(max_steps):
        if verbose:
            print(f"--- Step {step+1} ---")
        chain = prompt | llm
        try:
            response = chain.invoke({"input": current_input})
        except Exception as e:
            print(f"DEBUG: LLM 调用异常: {e}")
            return f"内部处理错误：{e}"

        text = response.content.strip()
        if verbose:
            print("DEBUG: 模型原始输出:", repr(text))

        if not text:
            return "抱歉，我暂时无法回答。"

        # 尝试直接解析为 JSON
        decision = None
        try:
            clean_text = text
            if clean_text.startswith("```"):
                clean_text = clean_text.split("\n", 1)[-1]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3].strip()
            decision = json.loads(clean_text)
        except json.JSONDecodeError:
            pass

        # 如果直接 JSON 失败，尝试提取包含 tool 或 final_answer 的对象
        if decision is None:
            matches = re.findall(r'\{.*?\}', text, re.DOTALL)
            for match in matches:
                try:
                    candidate = json.loads(match)
                    if "tool" in candidate or "final_answer" in candidate:
                        decision = candidate
                        break
                except json.JSONDecodeError:
                    continue

        # 如果仍然没有决策，尝试处理纯文本工具命令（工具名 + JSON/字符串参数）
        if decision is None:
            lines = text.split('\n')
            if len(lines) >= 2 and lines[0].strip() in tool_map:
                tool_name = lines[0].strip()
                arg_str = lines[1].strip() if len(lines) > 1 else ""
                # 尝试解析参数为 JSON
                try:
                    arg_dict = json.loads(arg_str)
                    if isinstance(arg_dict, dict):
                        if "arg" in arg_dict:
                            arg = str(arg_dict["arg"])
                        elif arg_dict:
                            arg = str(next(iter(arg_dict.values())))
                        else:
                            arg = ""
                    else:
                        arg = arg_str
                except json.JSONDecodeError:
                    arg = arg_str

                if verbose:
                    print(f"DEBUG: 检测到纯文本命令: {tool_name} 参数: {arg}")

                observation = tool_map[tool_name].run(arg)
                scratchpad.append(AIMessage(content=text))
                scratchpad.append(HumanMessage(content=f"工具执行结果：{observation}"))
                current_input = user_input + "\n" + "\n".join([m.content for m in scratchpad])
                continue
            else:
                # 直接返回文本
                return text

        # 检查是否有 final_answer
        if decision and "final_answer" in decision and decision["final_answer"]:
            return decision["final_answer"]

        # 执行工具
        tool_name = decision.get("tool")
        arg = decision.get("arg", "")
        if tool_name and tool_name in tool_map:
            try:
                observation = tool_map[tool_name].run(arg if arg else "")
            except Exception as e:
                observation = f"工具执行失败：{e}"
        else:
            observation = f"未知工具：{tool_name}"

        if verbose:
            print(f"DEBUG: 工具执行结果: {observation}")

        scratchpad.append(AIMessage(content=text))
        scratchpad.append(HumanMessage(content=f"工具执行结果：{observation}"))
        current_input = user_input + "\n" + "\n".join([m.content for m in scratchpad])

    return "抱歉，我思考了太久，没能完成你的任务。"