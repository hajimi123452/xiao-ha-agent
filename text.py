import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

base_url = os.getenv("LLM_BASE_URL", "").replace("/chat/completions", "")

llm = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "glm-4-flash"),
    api_key=os.getenv("LLM_API_KEY"),
    base_url=base_url,        # 修复：去掉 /chat/completions
    temperature=0.3,
)

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个翻译助手，把{source_lang}翻译成{target_lang}。"),
    ("user", "{input}")
])

chain = prompt | llm

# 测试中译英
result = chain.invoke({
    "source_lang": "中文",
    "target_lang": "英文",
    "input": "苹果"
})
print(result.content)

# 测试英译中
result2 = chain.invoke({
    "source_lang": "英文",
    "target_lang": "中文",
    "input": "hello"
})
print(result2.content)