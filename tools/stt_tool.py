import whisper

model = whisper.load_model("base")  # 首次运行会下载约150MB模型

def speech_to_text(audio_path):
    try:
        result = model.transcribe(audio_path, language="zh")
        return result["text"]
    except Exception as e:
        return f"语音识别失败：{e}"