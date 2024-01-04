# coding=utf-8
from flask import Flask,render_template, g
from flask_sockets import Sockets
import whisper
from pydub import AudioSegment
import os
import torch

from threading import Thread
from multiprocessing import Process
import time
import traceback

from zhpr.predict import DocumentDataset,merge_stride,decode_pred
from transformers import AutoModelForTokenClassification,AutoTokenizer
from torch.utils.data import DataLoader




app = Flask(__name__)
sockets = Sockets(app)


DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"Using device:{DEVICE}")
model = whisper.load_model('medium', device=DEVICE)


clockFlag = None                                                    #时钟线程与主线程用于沟通的参数 
                                                                        #1：时钟中断主线程 0：主线程完成任务，等待时钟中断 2：时钟停止
ws_audio_data = {}                                                  #存储不同websocket发送数据的缓存字典
modelOnUse = False                                                  #True：模型对象正在使用
onPosProcess = False                                                #True：正在进行后处理
threadError = False                                                 #True：线程报错
mainString = ""                                                     #历史识别内容
nowString = ""                                                      #当前识别内容
CutSeconde = 0
Cutted = False


count = 0


####标点模型所需参数
window_size = 256
step = 200

model_name = 'p208p2002/zh-wiki-punctuation-restore'
pmodel = AutoModelForTokenClassification.from_pretrained(model_name)
tokenizer = AutoTokenizer.from_pretrained(model_name)
####

head = ""




# 标点模型所需函数
def predict_step(batch,model,tokenizer):
        batch_out = []
        batch_input_ids = batch

        encodings = {'input_ids': batch_input_ids}
        output = model(**encodings)

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
    time.sleep(min(2,sec))
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
    
#音频处理函数，将二进制数据处理为webm格式
def save_as_webm(data):
    global count
    global Cutted

    lenn = len(data)
    data = b''.join(data)

    tempfile = "temp{}.wav".format(count)

    with open(tempfile, 'wb') as f:                                 #将二进制数据按原格式储存为临时文件（webm）
        f.write(data)
        f.close()
    
    part = ""
    with open(tempfile,"rb") as f:
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
    global CutSeconde
    global Cutted
    global count
    try:
        while(modelOnUse):                                              #等待模型可用（逻辑上不需要，以防万一）
            continue
        modelOnUse = True                                               #占用模型
        T1 = time.time()                                                #开始计时
        
        
        audioLen = save_as_webm(data)                                   #二进制数据转码mp3
        #stitchMedia("seg.mp3")                                         #音频合并
        print(f"operate: temp{count}.wav")
        result = model.transcribe("temp{}.wav".format(count), language='Chinese',no_speech_threshold=3,condition_on_previous_text=True)                         #调用识别模型，返回结果
        # os.remove("temp{}.wav".format(count))
        count+=1
                          
        T2 = time.time()                                                #结束计时
        print("recognition time:{}".format(T2-T1))                              #打印翻译模型相应时间
        result = result["text"]
        
        ############################################################################添加标点符号
        T1 = time.time()
        #result = "我爱抽电子烟特别是瑞克五代"
        dataset = DocumentDataset(result,window_size=window_size,step=step)
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
        T2 = time.time()
        print("punctuation time:{}".format(T2-T1))
        print(f"result:{result}")
        ############################################################################

        try:
            ws.send(mainString + result)                                    #socket传输结果（历史识别内容+当前翻译内容）
            nowString = result                                              #存储识别结果到当前翻译内容
        except Exception as e:
            print(e)
        else:
            if(result.find("。") != 0):
                mainString += "\n"
                mainString += nowString
                #CutSeconde = audioLen
                CutMedia(ws,audioLen)

            modelOnUse = False                                              #解锁模型
            if(flag == 1):                                                  #如果是后处理线程调用该线程，标志后线程处理结束
                onPosProcess = False
        
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
            mainString = mainString + nowString                                 #更新历史识别内容（历史识别内容 = 历史识别内容 + 当前识别内容）
            clockFlag = 0                                                       #提醒时钟线程主线程就绪

            head = ws.receive()
            # print(f"head type{type(head)}")
            ws_audio_data[ws].append(head)

            timer = Thread(target = clock, args = (1,))                 
            timer.daemon = True                                    
            timer.start()                                                       #启动时钟线程
        elif(clockFlag == 1):                                           #2. 时钟线程提醒主线程执行翻译
            ws_audio_data[ws].append(audio_data)
            print("detect clock")                                       
            clockFlag = 0
            print("data length:{}".format(len(ws_audio_data[ws])))

            translate = Thread(target = newThread,args=(ws_audio_data[ws],ws,0))
            translate.daemon = True
            translate.start()                                                   #主线程调用翻译任务线程   
            
            if(CutSeconde != 0):
                print("cut start")
                ws_audio_data[ws].append(audio_data)                                #将sockets数据存入缓存数组中
                CutMedia(ws,CutSeconde)
                CutSeconde = 0                                                   #清空当前识别内容

        elif(audio_data == "STOP_RECORDING"):                           #3. 前端提醒音频停止传输    
            print("stop")
            clockFlag = 2                                                       #提醒时钟关闭
            # posProcess = Thread(target=pos_clock,args=(ws_audio_data[ws],ws))
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
        else:                                                                #5. 正常的数据传入
            ws_audio_data[ws].append(audio_data)                                #将sockets数据存入缓存数组中
            # if(CutSeconde != 0):
            #     print("cut start")
            #     ws_audio_data[ws].append(audio_data)                                #将sockets数据存入缓存数组中
            #     CutMedia(ws,CutSeconde)
            #     CutSeconde = 0                                                   #清空当前识别内容
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

    ws_audio_data = {}                                         
    Cutted = False
    mainString = ""
    nowString = ""
    clockFlag = None
    modelOnUse = False
    modelOnUse = False                                                  #True：模型对象正在使用
    onPosProcess = False                                                #True：正在进行后处理
    threadError = False                                                 #True：线程报错

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

