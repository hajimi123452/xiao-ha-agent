import os
import requests
import base64
from dotenv import load_dotenv

load_dotenv()

def test_image(image_path):
    # 读取图片并转为 base64
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {
        "Authorization": f"Bearer {os.getenv('LLM_API_KEY')}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "glm-4v",   # 如果报错提示模型不存在，可尝试 glm-4v-flash
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请描述这张图片"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]
            }
        ],
        "stream": False
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        print("状态码:", resp.status_code)
        print("响应内容:", resp.text)
    except Exception as e:
        print("请求异常:", e)

if __name__ == "__main__":
    # 请将路径替换为你电脑上的一张真实图片路径
    test_image(r"C:\Users\wanyingxin\Pictures\272073_梦中的婚礼 2022福利.jpg")