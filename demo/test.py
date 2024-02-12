from transformers import AutoModelForTokenClassification,AutoTokenizer,AutoProcessor, AutoModelForSpeechSeq2Seq
from transformers import pipeline
from pydub import AudioSegment
import numpy as np
from pydub.playback import play
import torchaudio

model = pipeline("automatic-speech-recognition", model="xmzhu/whisper-tiny-zh")


filename = 'sing59.wav'

# # 使用pydub加载音频文件
# audio = AudioSegment.from_file(filename)
# # play(audio)
# # 将音频数据转换为numpy数组
# waveform = np.array(audio.get_array_of_samples())


# print(waveform.shape)
# print(waveform)


# waveform, sample_rate = torchaudio.load(filename)

# if waveform.shape[0] > 1:
#     waveform = waveform[0]

# waveform = np.squeeze(waveform.numpy())

# print(waveform.shape)
# print(waveform)

# 如果音频是立体声，只取第一个通道
# if audio.channels == 2:
#     waveform = waveform[::2]

text = model(filename)
print(text)