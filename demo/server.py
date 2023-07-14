from flask import Flask,render_template
from flask_sockets import Sockets
import whisper
from pydub import AudioSegment
import os

app = Flask(__name__)
sockets = Sockets(app)

model = whisper.load_model("base")

def save_as_mp3(data,filename, type):
    # Save the data as a WebM file
    tempfile = ""
    tempformatt = ""
    if(type == "audio/webm"):
        tempfile = "temp.webm"
        tempformatt = "webm"
        
    else:
        tempfile = "temp.mp4"
        tempformatt = "mp4"
    
    with open(tempfile, 'wb') as f:
        f.write(data)

    # Convert the WebM file to MP3
    audio = AudioSegment.from_file(tempfile, format=tempformatt)
    audio.export(filename, format='mp3')
    os.remove(tempfile)

# Dictionary to hold incoming audio data for each WebSocket
ws_audio_data = {}

@sockets.route('/echo')
def echo_socket(ws):
    global ws_audio_data

    # Initialize a new list to hold the audio data for this WebSocket
    ws_audio_data[ws] = []

    while not ws.closed:
        audio_data = ws.receive()
        if audio_data == "STOP_RECORDING":
            # Process the audio data if a "STOP_RECORDING" message is received
            full_audio_data = b''.join(ws_audio_data[ws])
            dataType = ws.receive()
            save_as_mp3(full_audio_data,"output.mp3",dataType)

            result = model.transcribe("output.mp3")
            print(result["text"])
            ws.send(result["text"])

            # Reset the audio data for this WebSocket
            ws_audio_data[ws] = []
        elif audio_data is not None:
            
            # Add the incoming audio data to the list for this WebSocket
            ws_audio_data[ws].append(audio_data)

            # # load audio and pad/trim it to fit 30 seconds
            # audio = whisper.load_audio("output.mp3")
            # audio = whisper.pad_or_trim(audio)

            # # make log-Mel spectrogram and move to the same device as the model
            # mel = whisper.log_mel_spectrogram(audio).to(model.device)

            # # decode the audio
            # options = whisper.DecodingOptions()
            # result = whisper.decode(model, mel, options)

            # # send the recognized text to the client
            # ws.send(result.text)

            # # Remove the audio data for this WebSocket
            # del ws_audio_data[ws]

@app.route('/')
def hello_world():
    return render_template("index.html")

if __name__ == '__main__':
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler
    server = pywsgi.WSGIServer(('0.0.0.0', 8000), app, handler_class=WebSocketHandler)
    print('server start')
    server.serve_forever()
