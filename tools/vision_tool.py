import os
import requests
import base64
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()

DESCRIPTION = "image_understanding：描述或回答关于图片的问题。参数 image_path 是本地图片路径，可选参数 question 是用户关于图片的问题。"

# 未指定问题时使用的默认提问
DEFAULT_QUESTION = "请详细描述这张图片"

@tool
def image_understanding(image_path: str, question: str = None) -> str:
    """描述图片内容，或根据图片回答问题。

    参数：
    - image_path：图片的本地路径（必填）
    - question：关于图片的提问，例如“图里有几个人？”，留空则默认描述整张图片
    """
    question = (question or "").strip() or DEFAULT_QUESTION
    # 读取图片并转 base64
    with open(image_path, "rb") as f:
        img_base64 = base64.b64encode(f.read()).decode("utf-8")
    # 构造消息
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
            ]
        }
    ]
    # 调用视觉模型
    headers = {
        "Authorization": f"Bearer {os.getenv('LLM_API_KEY')}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "glm-4v",  # 根据智谱实际可用模型调整
        "messages": messages,
        "temperature": 0.2
    }
    try:
        resp = requests.post(
            os.getenv("LLM_BASE_URL").replace("/chat/completions", "/chat/completions"),
            json=payload, headers=headers, timeout=60
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"图像理解失败：{e}"