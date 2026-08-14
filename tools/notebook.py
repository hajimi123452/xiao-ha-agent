"""记事本工具"""
DESCRIPTION = "notebook：操作记事本。arg 可以是“记一下 <内容>”、“看看”（列出全部）或“找 <关键词>”（搜索包含关键词的记录）。"
def add_note(notebook, content):
    """添加一条记事"""
    notebook.append(content)
    return f"已记住：{content}"

def show_notes(notebook):
    """查看记事本"""
    if not notebook:
        return "记事本空空如也。"
    lines = ["记事本内容："]
    for i, item in enumerate(notebook, 1):
        lines.append(f"{i}. {item}")
    return "\n".join(lines)

def run(notebook, user_input):
    text = user_input.replace("记事本", "", 1).strip()
    if text.startswith("记一下"):
        ...
    elif text.startswith("看看"):
        return show_notes(notebook)
    elif text.startswith("找 "):
        keyword = text[2:].strip()
        found = [item for item in notebook if keyword in item]
        if not found:
            return f"没有找到包含「{keyword}」的记录。"
        return "\n".join(f"{i+1}. {item}" for i, item in enumerate(found))
    else:
        return "记事本命令：记一下 <内容> / 看看 / 找 <关键词>"