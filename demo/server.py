# coding=utf-8
from flask import Flask,render_template, g
from flask_sockets import Sockets
import whisper
from pydub import AudioSegment
from pydub.silence import split_on_silence
import os
import torch
import json
import requests
import numpy as np
from threading import Thread
import time
import traceback

from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler

from zhpr.predict import DocumentDataset,merge_stride,decode_pred
from transformers import AutoModelForTokenClassification,AutoTokenizer,AutoProcessor, AutoModelForSpeechSeq2Seq
from transformers import pipeline
from torch.utils.data import DataLoader




app = Flask(__name__)
sockets = Sockets(app)


# DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
DEVICE = 'cpu'
print(f"Using device:{DEVICE}")

clockFlag = None                                                    #时钟线程与主线程用于沟通的参数 
                                                                        #1：时钟中断主线程 0：主线程完成任务，等待时钟中断 2：时钟停止
ws_audio_data = {}                                                  #存储不同websocket发送数据的缓存字典
modelOnUse = False                                                  #True：模型对象正在使用
onPosProcess = False                                                #True：正在进行后处理
threadError = False                                                 #True：线程报错
mainString = ""                                                     #历史识别内容
nowString = ""                                                      #当前识别内容
tranString = ""
CutSeconde = 0
Cutted = False


count = 0


####标点模型所需参数
window_size = 256
step = 200
model_name = 'p208p2002/zh-wiki-punctuation-restore'
pmodel = AutoModelForTokenClassification.from_pretrained(model_name)
tokenizer = AutoTokenizer.from_pretrained(model_name)
pmodel.to(DEVICE)

####识别模型
# model = whisper.load_model('medium', device=DEVICE)
model = pipeline("automatic-speech-recognition", model="xmzhu/whisper-tiny-zh",device=DEVICE)
# model = pipeline("automatic-speech-recognition", model="zongxiao/whisper-small-zh-CN")

head = ""

INST = {"STOP_RECORDING", "RESET", "START_RECORDING"}


# 标点模型所需函数
def predict_step(batch,model,tokenizer):
        batch_out = []
        batch_input_ids = batch


        batch_input_ids = batch_input_ids.to(model.device)
        
        encodings = {'input_ids': batch_input_ids}
        output = model(**encodings)


        # # 使用tokenizer对文本进行编码，并返回attention_mask
        # encoded_input = tokenizer(batch, padding=True, return_attention_mask=True, truncation=True, max_length=512)

        # # 将input_ids和attention_mask都转移到模型所在的设备
        # input_ids = encoded_input['input_ids'].to(model.device)
        # attention_mask = encoded_input['attention_mask'].to(model.device)

        # # 将input_ids和attention_mask都传递给模型
        # output = model(input_ids=input_ids, attention_mask=attention_mask)


        predicted_token_class_id_batch = output['logits'].argmax(-1)
        for predicted_token_class_ids, input_ids in zip(predicted_token_class_id_batch, batch_input_ids):
            out=[]
            tokens = tokenizer.convert_ids_to_tokens(input_ids)
            
            # compute the pad start in input_ids
            # and also truncate the predict
            # print(tokenizer.decode(batch_input_ids))
            input_ids = input_ids.tolist()
            try:
                input_id_pad_start = input_ids.index(tokenizer.pad_token_id)
            except:
                input_id_pad_start = len(input_ids)
            input_ids = input_ids[:input_id_pad_start]
            tokens = tokens[:input_id_pad_start]
    
            # predicted_token_class_ids
            predicted_tokens_classes = [model.config.id2label[t.item()] for t in predicted_token_class_ids]
            predicted_tokens_classes = predicted_tokens_classes[:input_id_pad_start]

            for token,ner in zip(tokens,predicted_tokens_classes):
                out.append((token,ner))
            batch_out.append(out)
        return batch_out

#异步时钟函数，定时提醒主线程执行翻译任务
def clock(sec):
    print("clock set")
    global clockFlag
    global modelOnUse
    global onPosProcess
    time.sleep(max(1.5,sec))
    while(True):                                                    #定时检查状态
        if(clockFlag == 2 or clockFlag == None):                                         #前端停止录制，结束时钟
            print("clock end")
            break
        if(not modelOnUse and not onPosProcess):                    #模型未占用，后处理未启用
            print("clock")
            clockFlag = 1                                           #提醒主线程执行翻译
        
        time.sleep(sec/2)
        if(clockFlag == 2 or clockFlag == None):                                         #前端停止录制，结束时钟
            print("clock end")
            break
        time.sleep(sec/2)

#停止录制后，翻译尚未处理数据的线程
def pos_clock(ws):
    global modelOnUse
    global mainString
    global nowString
    global tranString

    while(modelOnUse):
        continue
   
    print(f"--------------------Pos_Thread-----------------------")
    mainString = mainString + "\n"+nowString                                 #更新历史识别内容（历史识别内容 = 历史识别内容 + 当前识别内容）
    nowString = ""
    tranString += "\n"+translation(nowString)
    wsSend(ws)

    print(f"------------------------------------------------")
    
#音频处理函数，将二进制数据处理为webm格式
def save_as_webm(data):
    global count
    global Cutted
    global threadError
    lenn = len(data)
    try:
        data = b''.join(data)
    except Exception as e:

        print(f"Data type:{type(data)}")
        print(f"Data len:{len(data)}")
        # print(f"Data:{data}")
        traceback.print_exc()
        threadError = True
        for i in range(len(data)):
            if( i != 0 and type(data[i]) != type(data[i-1])):
                print(data[i])

        raise e
        

    tempfile = "temp{}.wav".format(count)

    with open(tempfile, 'wb') as f:                                 #将二进制数据按原格式储存为临时文件（webm）
        f.write(data)
        f.close()
    
    part = ""
    with open(tempfile,"rb") as f:
        print(tempfile)
        audio = AudioSegment.from_file(tempfile)
        if(Cutted):
            part = audio[200:len(audio)]
        else:
            part = audio
    os.remove(tempfile)
    part.export(tempfile)
    return lenn 

def CutMedia(ws,second):

    global ws_audio_data
    global Cutted
    global head

    print(f"current length:{len(ws_audio_data[ws])}")
    print(f"cut length:{second}")
    del ws_audio_data[ws][0:second]
    ws_audio_data[ws].insert(0,head)
    Cutted = True
    print("cut finish")

def punctuation(text):
    #text = "我爱抽电子烟特别是瑞克五代"
    dataset = DocumentDataset(text,window_size=window_size,step=step)
    dataloader = DataLoader(dataset=dataset,shuffle=False,batch_size=5)
    model_pred_out = []

    for batch in dataloader:

        batch_out = predict_step(batch,pmodel,tokenizer)
        for out in batch_out:
            model_pred_out.append(out)

    merge_pred_result = merge_stride(model_pred_out,step)

    merge_pred_result_deocde = decode_pred(merge_pred_result)
    result = ''.join(merge_pred_result_deocde)

    result = result.replace("[UNK]", ' ')

    pun = {'。', '，', '！', ',','？','?'}
    result = [result[i] for i in range(len(result)) if not (result[i] in pun and result[i-1] in pun)]
    result = ''.join(result)

    return result

def translation(text):
    url = "https://umcat.cis.um.edu.mo/api/translate.php"

    data = {
        'from':"zh-cn",
        'to':'en',
        'text':text,

        'system':"UTI"
    }

    response = requests.post(url,json=data)
    response_dic = response.json()
    # print(response_dic)

    status_code = response.status_code
    # print(status_code)

    return response_dic['translation'][0]['translated'][0]['text'] 

def recognition(filename):

    # text = model.transcribe(filename, language='Chinese',no_speech_threshold=3,condition_on_previous_text=True)
    text = model(filename)['text']

    return text

def audioSlice(filename):

    # 读取音频文件
    audio = AudioSegment.from_file(filename)

    # 设置分割参数
    min_silence_len = 800  # 最小静音长度
    silence_thresh = -38  # 静音阈值，越小越严格
    keep_silence = 600  # 保留静音长度
    # print(audio)
    # 切分音频文件
    chunks = split_on_silence(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh, keep_silence=keep_silence)

    # if(len(chunks) == 0):
    #     return 
    # else:
    return chunks
    
def wsSend(ws):
    global mainString, nowString, tranString

    packet = {"mainString":mainString, "nowString":nowString, 'tranString':tranString}
    
    js_packet = json.dumps(packet)
    ws.send(js_packet)

#执行翻译任务的线程函数
def newThread(data,ws,flag):

    global modelOnUse
    global threadError
    global mainString
    global nowString
    global tranString
    global onPosProcess
    global CutSeconde
    global Cutted
    global count
    try:
        while(modelOnUse):                                              #等待模型可用（逻辑上不需要，以防万一）
            continue
        modelOnUse = True                                               #占用模型
        print(f"--------------------Thread{count}--------------------")
        print(f"operate: temp{count}.wav")

        T1 = time.time()                                                #开始计时
        audioLen = save_as_webm(data)                                   #二进制数据转码mp3


        audioList = audioSlice("temp{}.wav".format(count))
        os.remove("temp{}.wav".format(count))

        if(len(audioList) == 0):    
            print("empty audio") 
            CutMedia(ws,audioLen)       
            modelOnUse = False  
            nowString = "" 
            wsSend(ws)
            return 

        totaled = audioList[0]
        for au in range(1,len(audioList)):
            totaled = totaled + au
        

        if(totaled.duration_seconds < 1.0):
            print("audio too short")        
            modelOnUse = False  
            nowString = "" 
            wsSend(ws)
            return             

        singled = audioList[len(audioList)-1]
        singled = None if(singled.duration_seconds < 1.0) else singled


        conbined = None
        if(len(audioList) > 1):
            conbined = audioList[0]
            for i in range(1,len(audioList) - 1):
                conbined += audioList[i]
        
            conbined = None if(conbined.duration_seconds < 1.0) else conbined



        if(conbined != None and singled != None):
            print("Cut audio")


            conbinedLen = conbined.duration_seconds
            singledLen = singled.duration_seconds

            conbined.export("conb{}.wav".format(count))
            conbinedResult = recognition(f"conb{count}.wav")
            conbinedResult = punctuation(conbinedResult)
            print(f"conbinedResult:{conbinedResult}")
            conbinedResultTrans = translation(conbinedResult)
            mainString += "\n" + conbinedResult
            tranString += "\n" + conbinedResultTrans
            wsSend(ws)


            singled.export("sing{}.wav".format(count))  
            singledResult = recognition(f"sing{count}.wav")
            print(f"singledResult:{singledResult}")
            nowString = singledResult


            os.remove("conb{}.wav".format(count))
            os.remove("sing{}.wav".format(count))
            
            hh = 0.2 if(Cutted) else 0.0
            audioLen = int ((hh+conbinedLen)/(hh+conbinedLen + singledLen) * audioLen)
            CutMedia(ws,audioLen)

        else:
            print("no Cut")
            totaled.export("total{}.wav".format(count))
            singledResult = recognition(f"total{count}.wav") 

            if("一个市镇的一个市镇" in singledResult or
               "一个建筑的一个建筑" in singledResult):
                nowString = ""
            else:
                nowString = singledResult

            os.remove("total{}.wav".format(count))

        T2 = time.time()
        print("Process time:{}".format(T2-T1))
        count+=1

        print(f"main:{mainString}")
        print(f"now:{nowString}")
        print(f"trans:{tranString}")
        wsSend(ws)
        print(f"---------------ThreadEnd--------------------------")

        modelOnUse = False                                              #解锁模型
        
    except Exception as e:
        traceback.print_exc()
        threadError = True

#websocket端口函数
@sockets.route('/echo')
def echo_socket(ws):                                                
    global ws_audio_data
    global clockFlag
    global modelOnUse
    global mainString
    global nowString
    global tranString
    global CutSeconde
    global head
    global count
    global Cutted

    print("ws set")
    init()
    ws_audio_data[ws] = []                                          #存储websocket传入的二进制数据的缓存数组
    Cutted = False
    mainString = ""
    nowString = ""
    clockFlag = None

    while not ws.closed:                                            #死循环
        if(threadError):                                                #若某一线程报错，中断服务器
            exit(0)
            
        audio_data = ws.receive()                                       #读取sockets数据，此为阻塞调用（等待直到有新数据传入）

        #print(clockFlag)
        if(audio_data == "START_RECORDING"):                            #1. 前端提醒音频开始传输
            print("start recording")

            clockFlag = 0                                                       #提醒时钟线程主线程就绪

            head = ws.receive()
            # print(f"head type{type(head)}")
            ws_audio_data[ws].append(head)

            timer = Thread(target = clock, args = (0.5,))                 
            timer.daemon = True                                    
            timer.start()       
                                                            #启动时钟线程
        elif(audio_data == "STOP_RECORDING"):                           #3. 前端提醒音频停止传输    
            print("stop")
            clockFlag = 2                                                       #提醒时钟关闭
            # posProcess = Thread(target=pos_clock,args=(ws))
            # posProcess.daemon = True
            # posProcess.start()                                                  #开启后处理线程，处理尚未处理的数据

            del ws_audio_data[ws]                                               #清空缓存数组
            ws_audio_data[ws] = []
            Cutted = False

        elif(audio_data == "RESET"):                                    #4. 前端提醒清除目前记录
            print("reset")
            del ws_audio_data[ws]                                               #清空缓存数组
            ws_audio_data[ws] = []
            mainString = ""                                                     #清空历史识别内容 
            nowString = ""  
            tranString = ""


        elif(clockFlag == 1):                                           #2. 时钟线程提醒主线程执行翻译
            ws_audio_data[ws].append(audio_data)
            print("detect clock")                                       
            clockFlag = 0
            print("data length:{}".format(len(ws_audio_data[ws])))

            translate = Thread(target = newThread,args=(ws_audio_data[ws],ws,0))
            translate.daemon = True
            translate.start()                                                   #主线程调用翻译任务线程   
                                                           #清空当前识别内容
        
        else:                                                                #5. 正常的数据传入
            ws_audio_data[ws].append(audio_data)                                #将sockets数据存入缓存数组中

    print("ws closed")
    init()

def init():
    global ws_audio_data
    global clockFlag
    global modelOnUse
    global mainString
    global nowString
    global CutSeconde
    global head
    global count
    global Cutted
    global modelOnUse
    global onPosProcess
    global threadError
    global tranString

    ws_audio_data = {}                                         
    Cutted = False
    mainString = ""
    nowString = ""
    tranString = ""
    clockFlag = None
    modelOnUse = False
    modelOnUse = False                                                  #True：模型对象正在使用
    onPosProcess = False                                                #True：正在进行后处理
    threadError = False                                                 #True：线程报错

@app.route('/')
def hello_world():
    return render_template("index.html")


# @app.errorhandler(Exception)
# def handle_exception(e):                                           #处理服务器异常函数，删除所有临时数据
#     if(os.path.exists('output.mp3')):
#         os.remove("output.mp3")
#     if(os.path.exists('temp.webm')):
#         os.remove("temp.webm")
#     return ""


# if __name__ == '__main__':
print('server starting')
server = pywsgi.WSGIServer(('0.0.0.0', 8080), app, handler_class=WebSocketHandler)#设立socket端口
print('server start')
server.serve_forever()                                         #开启服务器

