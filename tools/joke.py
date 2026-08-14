"""笑话工具"""
import random
DESCRIPTION = "joke：讲一个随机笑话。arg 固定为空字符串 \"\"。"
def run(user_input=None):
    jokes = [
        "为什么程序员总在晚上工作？因为白天有 bug。",
        "一个 SQL 语句走进酒吧，看到两张表，它问：我能 JOIN 你们吗？",
        "程序员最讨厌的数字是什么？1024。",
    ]
    return random.choice(jokes)