from pydub import AudioSegment


with open('temp0.webm', 'rb') as f:
    audio = AudioSegment.from_file(f, format='webm')
    print(audio)


