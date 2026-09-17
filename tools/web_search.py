import os
import requests
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()

DESCRIPTION = "web_search：联网搜索实时信息。参数 query 是搜索关键词，建议不超过70字。"

@tool
def web_search(query: str) -> str:
    """联网搜索实时信息。参数 query 是搜索关键词。"""
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        return "未配置智谱 API Key，无法联网搜索。"

    url = "https://open.bigmodel.cn/api/paas/v4/web_search"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "search_query": query[:70],      # 智谱限制70字符
        "search_engine": "search_std",   # 基础版，免费额度足够
        "search_intent": False,          # 直接搜索，不走意图改写
        "count": 5                       # 返回5条结果
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return f"搜索请求失败：{e}"

    # 提取搜索结果
    results = data.get("search_result", [])
    if not results:
        # 有些版本返回字段可能是 search_results
        results = data.get("search_results", [])
    if not results:
        return "未找到相关搜索结果。"

    output = []
    for item in results[:5]:
        title = item.get("title", "")
        content = item.get("content", "")[:150]   # 截断摘要
        link = item.get("link", "") or item.get("url", "")
        media = item.get("media", "")
        output.append(f"标题：{title}\n来源：{media}\n摘要：{content}\n链接：{link}")

    return "\n\n".join(output)