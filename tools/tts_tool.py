import edge_tts
import asyncio

async def _generate_speech(text, output_path, voice="zh-CN-XiaoxiaoNeural"):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

def text_to_speech(text, output_path="reply.mp3", voice="zh-CN-XiaoxiaoNeural"):
    """
    将文本转换为语音，保存为 MP3 文件。
    voice 可选：zh-CN-XiaoxiaoNeural（女声）、zh-CN-YunxiNeural（男声）等。
    """
    try:
        asyncio.run(_generate_speech(text, output_path, voice))
        return output_path
    except Exception as e:
        print(f"TTS 失败：{e}")
        return None