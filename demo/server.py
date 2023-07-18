from flask import Flask,render_template, g
from flask_sockets import Sockets
import whisper
from pydub import AudioSegment
import os
import threading
from threading import Thread
from multiprocessing import Process
import time



app = Flask(__name__)
sockets = Sockets(app)

model = whisper.load_model("tiny")

clockFlag = None                                                    #时钟线程与主线程用于沟通的参数 
                                                                        #1：时钟中断主线程 0：主线程完成任务，等待时钟中断 2：时钟停止
ws_audio_data = {}                                                  #存储不同websocket发送数据的缓存字典
modelOnUse = False                                                  #True：模型对象正在使用
onPosProcess = False                                                #True：正在进行后处理
threadError = False                                                 #True：线程报错
mainString = ""                                                     #历史识别内容
nowString = ""                                                      #当前识别内容

#异步时钟函数，定时提醒主线程执行翻译任务
def clock(sec):
    global clockFlag
    global modelOnUse
    global onPosProcess
    time.sleep(sec+1)
    while(True):                                                    #定时检查状态
        if(clockFlag == 2):                                         #前端停止录制，结束时钟
            print("clockend")
            break
        if(not modelOnUse and not onPosProcess):                    #模型未占用，后处理未启用
            print("clock")
            clockFlag = 1                                           #提醒主线程执行翻译
        time.sleep(sec)

#停止录制后，翻译尚未处理数据的线程
def pos_clock(data,ws):
    global modelOnUse
    global onPosProcess
    onPosProcess = True
    print("posProcess")
    while(modelOnUse):                                              #等待模型可用
        continue
    print("data length:{}".format(len(data)))
    translate = Thread(target = newThread,args=(data,ws,1))         #开启识别任务线程
    translate.daemon = True
    translate.start()
    
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
    audio.export(filename, format='mp3')
    #print("delete webm")

#音频拼接函数，将当前处理mp3文件与历史mp3文件拼接(未使用)
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

#执行翻译任务的线程函数
def newThread(data,ws,flag):

    global modelOnUse
    global threadError
    global mainString
    global nowString
    global onPosProcess
    try:
        while(modelOnUse):                                              #等待模型可用（逻辑上不需要，以防万一）
            continue
        modelOnUse = True                                               #占用模型
        T1 = time.time()                                                #开始计时
        full_audio_data = b''.join(data)
        save_as_mp3(full_audio_data,"output.mp3")                       #二进制数据转码mp3
        #stitchMedia("seg.mp3")                                         #音频合并
        print("operate")
        result = model.transcribe("output.mp3")                         #调用识别模型，返回结果
        os.remove("output.mp3")
        print(mainString + result["text"])                              #结束计时
        T2 = time.time()
        print("use time:{}".format(T2-T1))                              #打印翻译模型相应时间
        ws.send(mainString + result["text"])                            #socket传输结果（历史识别内容+当前翻译内容）
        nowString = result["text"]                                      #存储识别结果到当前翻译内容
        modelOnUse = False                                              #解锁模型
        if(flag == 1):                                                  #如果是后处理线程调用该线程，标志后线程处理结束
            onPosProcess = False
    except Exception as e:
        print(e)
        threadError = True

#websocket端口函数
@sockets.route('/echo')
def echo_socket(ws):                                                
    global ws_audio_data
    global clockFlag
    global modelOnUse
    global mainString
    global nowString
    ws_audio_data[ws] = []                                          #存储websocket传入的二进制数据的缓存数组
    while not ws.closed:                                            #死循环
        if(threadError):                                                #若某一线程报错，中断服务器
            exit(0)

        audio_data = ws.receive()                                       #读取sockets数据，此为阻塞调用（等待直到有新数据传入）
        #print(clockFlag)
        if(audio_data == "START_RECORDING"):                            #1. 前端提醒音频开始传输
            mainString = mainString + nowString                                 #更新历史识别内容（历史识别内容 = 历史识别内容 + 当前识别内容）
            clockFlag = 0                                                       #提醒时钟线程主线程就绪
            timer = Thread(target = clock, args = (1,))                 
            timer.daemon = True                                    
            timer.start()                                                       #启动时钟线程
        elif(clockFlag == 1):                                           #2. 时钟线程提醒主线程执行翻译
            print("detect")                                       
            clockFlag = 0
            print("data length:{}".format(len(ws_audio_data[ws])))
            translate = Thread(target = newThread,args=(ws_audio_data[ws],ws,0))
            translate.daemon = True
            translate.start()                                                   #主线程调用翻译任务线程   
            ws_audio_data[ws].append(audio_data)
        elif(audio_data == "STOP_RECORDING"):                           #3. 前端提醒音频停止传输    
            clockFlag = 2                                                       #提醒时钟关闭
            posProcess = Thread(target=pos_clock,args=(ws_audio_data[ws],ws))
            posProcess.daemon = True
            posProcess.start()                                                  #开启后处理线程，处理尚未处理的数据
            del ws_audio_data[ws]                                               #清空缓存数组
            ws_audio_data[ws] = []
        elif(audio_data == "RESET"):                                    #4. 前端提醒清除目前记录
            print("reset")
            del ws_audio_data[ws]                                               #清空缓存数组
            ws_audio_data[ws] = []
            mainString = ""                                                     #清空历史识别内容 
            nowString = ""                                                      #清空当前识别内容
        else:                                                           #5. 正常的数据传入
            ws_audio_data[ws].append(audio_data)                                #将sockets数据存入缓存数组中

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

