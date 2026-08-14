"""天气查询工具"""
import os
import re
import requests
from dotenv import load_dotenv

DESCRIPTION = "weather：查询单个城市的实时天气。arg 必须是一个中文城市名，如“北京”，不能包含多个城市。"
load_dotenv()  # 确保能读取 .env 中的 WEATHER_KEY

def extract_city(user_input):
    """从用户输入中提取城市名，支持'北京天气'或'天气 北京'"""
    city = user_input.replace("天气", "").strip()
    for suffix in ["怎么样", "如何", "怎样", "了", "吗"]:
        if city.endswith(suffix):
            city = city[:-len(suffix)].strip()
    return city if city else None

def get_real_weather(city):
    """查询真实天气，成功返回字符串，失败返回错误提示"""
    api_key = os.getenv("WEATHER_KEY")
    if not api_key:
        return "[错误] 未配置天气密钥，请在 .env 中设置 WEATHER_KEY"

    url = "https://restapi.amap.com/v3/weather/weatherInfo"
    params = {
        "key": api_key,
        "city": city,
        "extensions": "base"
    }

    try:
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "1":
            info = data.get("info", "未知错误")
            return f"天气查询失败：{info}"

        lives = data.get("lives")
        if not lives:
            return "未查询到该城市的天气信息"

        live = lives[0]
        return (
            f"{live['city']}天气：{live['weather']}，"
            f"温度 {live['temperature']}℃，"
            f"风向 {live['winddirection']}，"
            f"发布时间 {live['reporttime']}"
        )

    except requests.exceptions.Timeout:
        return "天气查询超时，请稍后再试"
    except requests.exceptions.ConnectionError:
        return "网络连接失败，请检查网络"
    except Exception as e:
        return f"天气查询异常：{e}"

def run(user_input):
    """天气工具的入口函数，供主程序统一调用"""
    city = extract_city(user_input)
    if not city:
        return "请指定城市，例如：天气 北京"
    return get_real_weather(city)