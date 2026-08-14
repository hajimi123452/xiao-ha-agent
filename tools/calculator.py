"""计算器工具，支持简单四则运算"""
DESCRIPTION = "calculator：计算数学表达式，arg 为表达式，如 \"2+3*4\""

def run(user_input=None):
    if not user_input:
        return "请输入要计算的表达式，例如：计算 2+3*4"
    # 如果 user_input 包含“计算”，则去掉
    expr = user_input.replace("计算", "").strip()
    if not expr:
        return "表达式为空"
    # 安全起见，只允许数字、运算符、空格和小数点
    allowed = set("0123456789+-*/(). ")
    if not all(c in allowed for c in expr):
        return "表达式包含不支持的字符"
    try:
        result = eval(expr)
        return f"{expr} = {result}"
    except Exception as e:
        return f"计算出错：{e}"