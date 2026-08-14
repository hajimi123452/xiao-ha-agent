"""百度翻译工具（通用翻译API）"""
import os
import hashlib
import random
import requests
import json
from dotenv import load_dotenv

load_dotenv()

DESCRIPTION = "translator：翻译，arg 为 \"翻译 <词语或句子> 到<中文/英文>\"，例如 \"翻译 苹果 到英文\" 或 \"翻译 hello 到中文\""

def baidu_translate(text, from_lang, to_lang):
    """调用百度翻译API"""
    appid = os.getenv("BAIDU_FANYI_APPID")
    secret_key = os.getenv("BAIDU_FANYI_KEY")
    if not appid or not secret_key:
        return "翻译功能未配置，请在 .env 中设置 BAIDU_FANYI_APPID 和 BAIDU_FANYI_KEY"

    url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
    salt = str(random.randint(32768, 65536))
    # 签名：appid + text + salt + secret_key 的 MD5
    sign_str = appid + text + salt + secret_key
    sign = hashlib.md5(sign_str.encode()).hexdigest()

    params = {
        "q": text,
        "from": from_lang,
        "to": to_lang,
        "appid": appid,
        "salt": salt,
        "sign": sign
    }
    try:
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        if "trans_result" in data:
            return data["trans_result"][0]["dst"]
        elif "error_code" in data:
            return f"翻译失败，错误码：{data['error_code']}，{data.get('error_msg', '')}"
        else:
            return f"翻译接口返回异常：{json.dumps(data, ensure_ascii=False)}"
    except Exception as e:
        return f"翻译请求出错：{e}"

def run(user_input=None):
    if not user_input:
        return "请按格式输入：翻译 <词语或句子> 到<中文/英文>，例如：翻译 苹果 到英文"
    text = user_input.replace("翻译", "").strip()
    if "到英文" in text:
        content = text.replace("到英文", "").strip()
        result = baidu_translate(content, "zh", "en")
        return f"'{content}' 翻译成英文：{result}"
    elif "到中文" in text:
        content = text.replace("到中文", "").strip()
        result = baidu_translate(content, "en", "zh")
        return f"'{content}' 翻译成中文：{result}"
    else:
        return "请指定目标语言：到中文 或 到英文"