# coding=utf-8
from flask import Flask,render_template, g
from flask_sockets import Sockets
# import whisper
from pydub import AudioSegment
import os
import threading
from threading import Thread
from multiprocessing import Process
import time


app = Flask(__name__)
sockets = Sockets(app)

#websocket端口函数
@sockets.route('/echo')
def echo_socket(ws):                                                
    count = 0

    arr = []
    head = ""
    Cutted = False
    while not ws.closed:                                            #死循环


        
        audio_data = ws.receive()                                       #读取sockets数据，此为阻塞调用（等待直到有新数据传入）

        if(audio_data == "START_RECORDING"):                            #1. 前端提醒音频开始传输
            print("start")
            head = ws.receive() 
            arr.append(head)

        elif(audio_data == "STOP_RECORDING"):                           #3. 前端提醒音频停止传输    
            print("end")
        else:

            arr.append(audio_data)

            if(count != 0 and count % 6 == 0):
                print("cut")
                with open(f"temp{count//3}.wav","wb") as f:
                    f.write(b''.join(arr))
                if(Cutted):
                    part = ""
                    with open(f"temp{count//3}.wav","rb") as f:
                        audio = AudioSegment.from_file(f"temp{count//3}.wav")
                        part = audio[200:len(audio)]
                    os.remove(f"temp{count//3}.wav")
                    part.export(f"temp{count//3}.wav", format = "wav")
                else:
                    Cutted = True

                print(len(arr))
                arr = []
                arr.append(head)
            count+=1



@app.route('/')
def hello_world():
    return render_template("index.html")


if __name__ == '__main__':
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler
    server = pywsgi.WSGIServer(('0.0.0.0', 8000), app, handler_class=WebSocketHandler)#设立socket端口
    # empty_segment = AudioSegment.empty()
    # empty_segment.export("output.mp3", format="mp3")
    print('server start')
    server.serve_forever()   