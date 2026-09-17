# tools/rag_engine.py
import os


from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

load_dotenv()

import os
import glob
from langchain_community.document_loaders import TextLoader, PyPDFLoader, UnstructuredMarkdownLoader

def load_documents_from_folder(folder_path="docs"):
    """加载文件夹中所有支持的文档，返回 Document 列表"""
    documents = []
    # 支持的文件扩展名
    extensions = ["*.txt", "*.md", "*.pdf"]
    for ext in extensions:
        for filepath in glob.glob(os.path.join(folder_path, "**", ext), recursive=True):
            try:
                if ext == "*.txt":
                    loader = TextLoader(filepath, encoding="utf-8")
                elif ext == "*.md":
                    loader = UnstructuredMarkdownLoader(filepath)
                elif ext == "*.pdf":
                    loader = PyPDFLoader(filepath)
                documents.extend(loader.load())
                print(f"已加载：{filepath}")
            except Exception as e:
                print(f"加载 {filepath} 失败：{e}")
    return documents

# ---------- 初始化 LLM（用于生成最终回答） ----------
llm_base_url = os.getenv("LLM_BASE_URL", "").replace("/chat/completions", "")
llm = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "glm-4-flash"),
    api_key=os.getenv("LLM_API_KEY"),
    base_url=llm_base_url,
    temperature=0,
    request_timeout=30,      # 请求超时时间（秒）
    max_retries=2,           # 失败后自动重试次数
)
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(
    model="embedding-2",                # 智谱嵌入模型名称，请确认你的账号支持
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL").replace("/chat/completions", ""),
)

# ---------- 全局向量数据库对象 ----------
vectorstore = None

def initialize_knowledge_base(folder_path="docs", persist_dir="./chroma_db"):
    global vectorstore
    # 如果持久化目录存在且包含数据，直接加载
    if os.path.exists(persist_dir) and os.path.isdir(persist_dir):
        try:
            vectorstore = Chroma(
                persist_directory=persist_dir,
                embedding_function=embeddings
            )
            print("已从持久化目录加载向量数据库")
            return
        except Exception:
            pass

    # 加载所有文档
    documents = load_documents_from_folder(folder_path)
    if not documents:
        print("未找到任何文档，知识库为空")
        vectorstore = None
        return

    # 切分
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=200,          # 可根据文档调整
        chunk_overlap=20,
        length_function=len,
        separators=["\n\n", "\n", "。", "！", "？", "，", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)

    # 向量化并存储
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=persist_dir
    )
    print(f"知识库构建完成，共 {len(chunks)} 个文本块")


def rag_answer(question, k=10, score_threshold=None):
    if vectorstore is None:
        return "知识库尚未初始化，无法回答。"
    # 使用 similarity_search_with_relevance_scores 获取相关度和文档
    docs_with_scores = vectorstore.similarity_search_with_relevance_scores(question, k=k)
    if not docs_with_scores:
        return "没有找到相关资料。"

    docs_with_scores = vectorstore.similarity_search_with_relevance_scores(question, k=k)
    print("检索到的文档片段：")
    for doc, score in docs_with_scores:
        print(score, doc.page_content[:100])

    # 可选：过滤低相关度文档
    if score_threshold is not None:
        docs = [doc for doc, score in docs_with_scores if score >= score_threshold]
    else:
        docs = [doc for doc, _ in docs_with_scores]

    if not docs:
        return "没有找到足够相关的资料。"

    context = "\n".join([d.page_content for d in docs])
    prompt = f"""根据以下资料回答问题。如果资料中没有答案，请回答“不知道”。

资料：
{context}

问题：{question}
回答："""
    response = llm.invoke(prompt)
    return response.content


def add_documents_to_kb(file_paths):
    """
    向知识库添加新文档。file_paths 可以是文件路径字符串或列表。
    """
    global vectorstore  # 只声明一次，且必须在函数开头

    if vectorstore is None:
        initialize_knowledge_base()
        if vectorstore is None:
            return "知识库初始化失败，无法添加文档。"

    if isinstance(file_paths, str):
        file_paths = [file_paths]

    total_chunks = 0
    for file_path in file_paths:
        try:
            # 根据扩展名选择加载器
            if file_path.endswith(".txt"):
                loader = TextLoader(file_path, encoding="utf-8")
            elif file_path.endswith(".md"):
                loader = TextLoader(file_path, encoding="utf-8")
            elif file_path.endswith(".pdf"):
                loader = PyPDFLoader(file_path)
            else:
                print(f"不支持的文件类型：{file_path}")
                continue

            documents = loader.load()
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=200,
                chunk_overlap=20,
                length_function=len,
                separators=["\n\n", "\n", "。", "！", "？", "，", " ", ""]
            )
            chunks = text_splitter.split_documents(documents)
            vectorstore.add_documents(chunks)
            total_chunks += len(chunks)
            print(f"已添加 {file_path}，共 {len(chunks)} 个文本块")
        except Exception as e:
            print(f"添加 {file_path} 失败：{e}")

    if total_chunks > 0:
        # 强制持久化（新版 Chroma 底层客户端有 persist 方法）
        try:
            vectorstore._client.persist()
        except Exception:
            pass

        # 重新从持久化目录加载，刷新内存索引（直接赋值，不需要再写 global）
        vectorstore = Chroma(
            persist_directory="./chroma_db",
            embedding_function=embeddings
        )
        return f"成功添加 {total_chunks} 个文本块到知识库。"
    else:
        return "没有添加任何内容。"