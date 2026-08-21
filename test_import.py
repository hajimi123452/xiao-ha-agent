import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()
base_url = os.getenv("LLM_BASE_URL", "").replace("/chat/completions", "")
llm = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "glm-4-flash"),
    api_key=os.getenv("LLM_API_KEY"),
    base_url=base_url,
    temperature=0,
)
print("开始调用 LLM...")
resp = llm.invoke("你好")
print("LLM 回复内容：", repr(resp.content))