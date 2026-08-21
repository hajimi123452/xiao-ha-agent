import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()

# 处理 base_url，去掉 /chat/completions
base_url = os.getenv("LLM_BASE_URL", "").replace("/chat/completions", "")

llm = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "glm-4-flash"),
    api_key=os.getenv("LLM_API_KEY"),
    base_url=base_url,
    temperature=0.7,
)

# 定义提示词，使用 MessagesPlaceholder 来插入完整消息历史
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是小哈，一个友好的AI助手。请用简洁、亲切的语气回答问题。"),
    MessagesPlaceholder(variable_name="messages")
])

chain = prompt | llm

# 保存对话历史（初始为空，不包含 system，因为 system 在提示词里固定了）
history = []

print("带记忆的小哈已启动，输入0退出。")
while True:
    user_input = input("你：")
    if user_input == "0":
        print("再见！")
        break

    # 1. 将用户消息加入历史
    history.append(HumanMessage(content=user_input))

    # 2. 调用模型，传入当前所有历史消息
    result = chain.invoke({"messages": history})

    # 3. 将模型回复加入历史
    history.append(AIMessage(content=result.content))

    # 4. 输出回复
    print("小哈：" + result.content)