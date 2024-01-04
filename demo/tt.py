from pydub import AudioSegment
from pydub.silence import split_on_silence
from pydub.playback import play

# 读取音频文件
audio = AudioSegment.from_file("temp2.wav")

# 设置分割参数
min_silence_len = 800  # 最小静音长度
silence_thresh = -38  # 静音阈值，越小越严格
keep_silence = 600  # 保留静音长度
# print(audio)
# 切分音频文件
chunks = split_on_silence(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh, keep_silence=keep_silence)

# 输出切分结果
print(len(chunks))
for i, chunk in enumerate(chunks):
    chunk.export(f"chunk{i}.wav", format="wav")
