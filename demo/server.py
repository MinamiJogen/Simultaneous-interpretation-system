from flask import Flask,render_template, g
from flask_sockets import Sockets
import whisper
from pydub import AudioSegment
import os
import threading
from threading import Thread

app = Flask(__name__)
sockets = Sockets(app)

model = whisper.load_model("tiny")

clockFlag = None                                                    #时钟线程与主线程沟通参数 
                                                                    #1=时钟中断主线程 0=主线程完成任务，等待时钟中断 2=时钟停止

ws_audio_data = {}                                                  #存储不同websocket发送数据的缓存字典

#异步时钟函数，定时触发主线程执行翻译任务
def clock():
    global clockFlag
    print("clock")
    if(clockFlag == 0):
        clockFlag = 1
        timer = threading.Timer(2, clock)
        timer.start()

#音频处理函数，将二进制数据处理为mp3格式
def save_as_mp3(data,filename):
    # Save the data as a WebM file
    # tempfile = ""
    # tempformatt = ""
    # if(type == "audio/webm"):
    #     tempfile = "temp.webm"
    #     tempformatt = "webm"
        
    # else:
    #     tempfile = "temp.mp4"
    #     tempformatt = "mp4"
    tempfile = "temp.webm"
    tempformatt = "webm"
    with open(tempfile, 'wb') as f:                                 #将二进制数据按原格式储存为临时文件（webm）
        f.write(data)

    audio = AudioSegment.from_file(tempfile, format=tempformatt)    #webm -> mp3
                                                                #这里进行第二次储存的时候报错，无法解码
    audio.export(filename, format='mp3')
    os.remove(tempfile)
    #print("delete webm")

#音频拼接函数，将当前处理mp3文件与历史mp3文件拼接
def stitchMedia(filename):
    output_music = None
    if(os.path.exists('output.mp3')):                               #存在历史mp3文件时拼接
        input_music_1 = AudioSegment.from_mp3("output.mp3")
        input_music_2 = AudioSegment.from_mp3("seg.mp3")
        output_music = input_music_1 + input_music_2
        print("合成音频")
    else:                                                           #不存在历史文件时不做处理
        output_music = AudioSegment.from_mp3("seg.mp3")
    print("stitch")
    output_music.export("output.mp3", format="mp3")                 #储存结果文件
    os.remove("seg.mp3")  

#执行翻译任务的现成函数
def newThread(data,ws):
    print("operate")
    full_audio_data = b''.join(data)
    save_as_mp3(full_audio_data,"seg.mp3")                          #二进制数据转码mp3
    stitchMedia("seg.mp3")                                          #音频合并
    
    result = model.transcribe("output.mp3")                         #调用翻译模型

    print(result["text"])
    ws.send(result["text"])                                         #socket回传结果



@sockets.route('/echo')
def echo_socket(ws):                                                
    global ws_audio_data
    global clockFlag
    timer = threading.Timer(2, clock)
    
    ws_audio_data[ws] = []
    while not ws.closed:
        
        audio_data = ws.receive()                                   #读取sockets数据
        #print(clockFlag)
        if(audio_data == "START_RECORDING"):                        #音频开始传输
            clockFlag = 0                                           
            timer.start()                                           #启动时钟
        elif(audio_data == "STOP_RECORDING" or clockFlag == 1):     #音频停止传输或时钟中断
            print("detect")
            translate = Thread(target = newThread,args=(ws_audio_data[ws],ws))
            translate.start()                                       #启动翻译线程
            clockFlag = 0
            del ws_audio_data[ws]                                   #清空缓存数据
            ws_audio_data[ws] = []
            if(audio_data == "STOP_RECORDING"):                     
                clockFlag = 2
            else:
                ws_audio_data[ws].append(audio_data)

        else:
            ws_audio_data[ws].append(audio_data)                    #将sockets数据存入缓存

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


@app.errorhandler(Exception)
def handle_exception(e):                                           #处理服务器异常函数，删除所有临时数据
    if(os.path.exists('output.mp3')):
        os.remove("output.mp3")
    if(os.path.exists('temp.webm')):
        os.remove("temp.webm")
    return ""
    



if __name__ == '__main__':
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler
    server = pywsgi.WSGIServer(('0.0.0.0', 8000), app, handler_class=WebSocketHandler)#设立socket端口
    # empty_segment = AudioSegment.empty()
    # empty_segment.export("output.mp3", format="mp3")
    print('server start')           
    server.serve_forever()                                         #开启服务器

