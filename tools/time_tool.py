"""时间工具"""
import datetime
DESCRIPTION = "time：获取当前日期和时间。arg 固定为空字符串 \"\"。"
def run(user_input=None):
    try:
        now = datetime.datetime.now()
        return f"现在是 {now.strftime('%Y年%m月%d日 %H:%M:%S')}"
    except Exception:
        return "时间获取失败"