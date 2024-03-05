from ppasr.predict import PPASRPredictor

predictor = PPASRPredictor(model_tag='conformer_streaming_fbank_wenetspeech')

wav_path = 'total4.wav'
result = predictor.predict(audio_data=wav_path, use_pun=False)
score, text = result['score'], result['text']
print(f"识别结果: {text}, 得分: {int(score)}")