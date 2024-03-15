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
from zhconv import convert
import re

from ppasr.predict import PPASRPredictor


from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler






app = Flask(__name__)
sockets = Sockets(app)


# DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
DEVICE = 'cpu'
print(f"Using device:{DEVICE}")

clockFlag = None                                                    #时钟线程与主线程用于沟通的参数 
                                                                        #1：时钟中断主线程 0：主线程完成任务，等待时钟中断 2：时钟停止
ws_audio_data = {}                                                  #存储不同websocket发送数据的缓存字典
recogOnUse = False                                                  #True：识别模型对象正在使用
puncOnUse = False
onPosProcess = False                                                #True：正在进行后处理
threadError = False                                                 #True：线程报错
mainString = []                                                     #历史识别内容
nowString = ""                                                      #当前识别内容
tranString = []
CutSeconde = 0
Cutted = False

THRESHOLD = 1.0


count = 0


print("加载识别模型...")
####识别模型
predictor = PPASRPredictor(model_tag='conformer_streaming_fbank_wenetspeech',use_gpu= False)
# model = whisper.load_model('tiny', device=DEVICE)
# model = pipeline("automatic-speech-recognition", model="xmzhu/whisper-tiny-zh",device=DEVICE)
# model = pipeline("automatic-speech-recognition", model="zongxiao/whisper-small-zh-CN")

head = ""


print("加载标点模型...")
####标点模型所需参数
##model 1
# from zhpr.predict import DocumentDataset,merge_stride,decode_pred
# from transformers import AutoModelForTokenClassification,AutoTokenizer,AutoProcessor, AutoModelForSpeechSeq2Seq
# from transformers import pipeline
# from torch.utils.data import DataLoader
# model_name = 'p208p2002/zh-wiki-punctuation-restore'
# pmodel = AutoModelForTokenClassification.from_pretrained(model_name)
# tokenizer = AutoTokenizer.from_pretrained(model_name)
# pmodel.to(DEVICE)

##model 2
from ppasr.infer_utils.pun_predictor import PunctuationPredictor
pun_predictor = PunctuationPredictor(model_dir='models\pun_models3', use_gpu=False)






#异步时钟函数，定时提醒主线程执行翻译任务
def clock(sec):
    print("clock set")
    global clockFlag
    global recogOnUse
    global onPosProcess
    time.sleep(max(1.5,sec))
    while(True):                                                    #定时检查状态
        if(clockFlag == 2 or clockFlag == None):                                         #前端停止录制，结束时钟
            print("clock end")
            break
        if(not recogOnUse and not onPosProcess):                    #模型未占用，后处理未启用
            print("clock")
            clockFlag = 1                                           #提醒主线程执行翻译
        
        time.sleep(sec/2)
        if(clockFlag == 2 or clockFlag == None):                                         #前端停止录制，结束时钟
            print("clock end")
            break
        time.sleep(sec/2)

#停止录制后，翻译尚未处理数据的线程
def pos_clock(ws):
    global recogOnUse
    global mainString
    global nowString
    global tranString

    while(recogOnUse):
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
    del ws_audio_data[ws][1:second]
    # ws_audio_data[ws].insert(0,head)
    Cutted = True
    print("cut finish") 

def punctuation(text):

    ### model 1
    

    # 标点模型所需函数
    # def predict_step(batch,model,tokenizer):
    #         batch_out = []
    #         batch_input_ids = batch


    #         batch_input_ids = batch_input_ids.to(model.device)

    #         attention_mask = (batch_input_ids != 0).float()
    #         output = model(batch_input_ids, attention_mask=attention_mask)

    #         # # 使用tokenizer对文本进行编码，并返回attention_mask
    #         # encoded_input = tokenizer(batch, padding=True, return_attention_mask=True, truncation=True, max_length=512)

    #         # # 将input_ids和attention_mask都转移到模型所在的设备
    #         # input_ids = encoded_input['input_ids'].to(model.device)
    #         # attention_mask = encoded_input['attention_mask'].to(model.device)

    #         # # 将input_ids和attention_mask都传递给模型
    #         # output = model(input_ids=input_ids, attention_mask=attention_mask)


    #         predicted_token_class_id_batch = output['logits'].argmax(-1)
    #         for predicted_token_class_ids, input_ids in zip(predicted_token_class_id_batch, batch_input_ids):
    #             out=[]
    #             tokens = tokenizer.convert_ids_to_tokens(input_ids)

    #             # compute the pad start in input_ids
    #             # and also truncate the predict
    #             # print(tokenizer.decode(batch_input_ids))
    #             input_ids = input_ids.tolist()
    #             try:
    #                 input_id_pad_start = input_ids.index(tokenizer.pad_token_id)
    #             except:
    #                 input_id_pad_start = len(input_ids)
    #             input_ids = input_ids[:input_id_pad_start]
    #             tokens = tokens[:input_id_pad_start]

    #             # predicted_token_class_ids
    #             predicted_tokens_classes = [model.config.id2label[t.item()] for t in predicted_token_class_ids]
    #             predicted_tokens_classes = predicted_tokens_classes[:input_id_pad_start]

    #             for token,ner in zip(tokens,predicted_tokens_classes):
    #                 out.append((token,ner))
    #             batch_out.append(out)
    #         return batch_out
        
    # pattern = re.compile(r'[^\u4e00-\u9fa5]')
    # if(bool(pattern.search(text))):
    #     return text

    # # return text
    # window_size = 256
    # step = 200
    # #text = "我爱抽电子烟特别是瑞克五代"
    # dataset = DocumentDataset(text,window_size=window_size,step=step)
    # dataloader = DataLoader(dataset=dataset,shuffle=False,batch_size=5)
    # model_pred_out = []

    # for batch in dataloader:

    #     batch_out = predict_step(batch,pmodel,tokenizer)
    #     for out in batch_out:
    #         model_pred_out.append(out)

    # merge_pred_result = merge_stride(model_pred_out,step)

    # merge_pred_result_deocde = decode_pred(merge_pred_result)
    # result = ''.join(merge_pred_result_deocde)

    # result = result.replace("[UNK]", ' ')

    # pun = {'。', '，', '！', ',','？','?','、'}
    # result = [result[i] for i in range(len(result)) if not (result[i] in pun and result[i-1] in pun)]
    # result = ''.join(result)

    
    ### model 2
    result = pun_predictor(text)
    
    pun = {'。', '，', '！', ',','？','?','、'}
    result = [result[i] for i in range(len(result)) if not (result[i] in pun and result[i-1] in pun)]
    result = ''.join(result)
    
    return result

def translation(text):
    # return ""
    url = "https://umcat.cis.um.edu.mo/api/translate.php"

    data = {
        'from':"zh-cn",
        'to':'en',
        'text':text,

        'system':"UTI"
    }
    t1 = time.time()
    response = requests.post(url,json=data)
    response_dic = response.json()
    # print(response_dic)

    # status_code = response.status_code
    # print(status_code)
    t2 = time.time()
    print(f"trans time:{t2 - t1}")
    return response_dic['translation'][0]['translated'][0]['text'] 

def recognition(fileList):

    ### 并行操作
    # # text = model.transcribe(filename, language='Chinese',no_speech_threshold=3,condition_on_previous_text=True)
    # results = model(fileList)
    # text = [result['text'] for result in results]
    # return text

    ### 串行操作
    # model 1
    # result = model(fileList)['text']
    # result = result.replace('尼好','你好')
    # result = result.replace('尼号','你好')

    # whisper tiny
    # result = model.transcribe(fileList, language='Chinese',no_speech_threshold=3,condition_on_previous_text=True)['text']
    # result = convert(result, 'zh-hans')
    

    # #ppasr
    result = predictor.predict(audio_data=fileList, use_pun=False)['text']

    return result

def audioSlice(filename):

    # 读取音频文件
    audio = AudioSegment.from_file(filename)

    # 设置分割参数
    min_silence_len = 600  # 最小静音长度
    silence_thresh = -38  # 静音阈值，越小越严格
    keep_silence = 600  # 保留静音长度
    # print(audio)
    # 切分音频文件
    chunks = split_on_silence(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh, keep_silence=keep_silence)

    # if(len(chunks) == 0):
    #     return 
    # else:

    if(len(chunks) == 0):
        return -1, None, None

    audioList = chunks

    totaled = audioList[0]
    for au in range(1,len(audioList)):
        totaled = totaled + audioList[au]
    

    if(totaled.duration_seconds < THRESHOLD):
        totaled = None       

    singled = audioList[len(audioList)-1]
    singled = None if(singled.duration_seconds < THRESHOLD) else singled


    conbined = None
    if(len(audioList) > 1):
        conbined = audioList[0]
        for i in range(1,len(audioList) - 1):
            conbined += audioList[i]
        conbined = None if(conbined.duration_seconds < THRESHOLD) else conbined



    return totaled, conbined, singled
    
def wsSend(ws):
    global mainString, nowString, tranString

    packet = {"mainString":mainString, "nowString":nowString, 'tranString':tranString}
    
    js_packet = json.dumps(packet)
    ws.send(js_packet)

#执行翻译任务的线程函数
def newThread(data,ws,flag):

    global recogOnUse
    global threadError
    global mainString
    global nowString
    global tranString
    global onPosProcess
    global CutSeconde
    global Cutted
    global count
    try:
        while(recogOnUse):                                              #等待模型可用（逻辑上不需要，以防万一）
            continue
        recogOnUse = True                                               #占用模型
        print(f"--------------------Thread{count}--------------------")
        print(f"operate: temp{count}.wav")

        T1 = time.time()                                                #开始计时
        audioLen = save_as_webm(data)                                   #二进制数据转码mp3


        totaled, conbined, singled = audioSlice("temp{}.wav".format(count))
        os.remove("temp{}.wav".format(count))


        if(totaled == -1):    
            print("empty audio") 
            CutMedia(ws,audioLen)       
            recogOnUse = False  
            nowString = "" 
            wsSend(ws)
            print(f"---------------ThreadEnd--------------------------")
            return 
        elif(totaled == None):
            print("too short")
            recogOnUse = False  
            nowString = "" 
            wsSend(ws)
            print(f"---------------ThreadEnd--------------------------")
            return 

        if(conbined != None and singled != None):
            print("Two task")

            conbinedLen = conbined.duration_seconds
            singledLen = singled.duration_seconds

            conbined.export("conb{}.wav".format(count))
            singled.export("sing{}.wav".format(count))  

            #### 并行操作

            # lists = [f"conb{count}.wav",f"sing{count}.wav"]
            # Results = recognition(lists)

            # conbinedResult = Results[0]
            # singledResult = Results[1]

            # conbinedResult = punctuation(conbinedResult)
            # print(f"conbinedResult:{conbinedResult}")
            # conbinedResultTrans = translation(conbinedResult)
            # print(f"singledResult:{singledResult}")
            # nowString = singledResult
            # mainString += "\n" + conbinedResult
            # tranString += "\n" + conbinedResultTrans
            # wsSend(ws)

            #### 串行操作

            print("---")
            print("task 1:")

            print(f"conb recognition : {conbinedLen}")
            t1 = time.time()
            conbinedResult = recognition(f"conb{count}.wav")
            t2 = time.time()
            print(f"conb recognition time:{t2 - t1}")
            mainString.append(conbinedResult) 
            wsSend(ws)


            PTThread = Thread(target = P_TThread, args = (conbinedResult,ws))                 
            PTThread.daemon = True                                    
            PTThread.start()  

            # print(f"conb punctuation ")
            # t1 = time.time()
            # conbinedResult = punctuation(conbinedResult)
            # t2 = time.time()
            # print(f"conb punctuation time:{t2 - t1}")
            # nowString = ""
            # mainString += "\n" + conbinedResult
            # wsSend(ws)

            # print(f"conb transaltion ")
            # t1 = time.time()
            # conbinedResultTrans = translation(conbinedResult)
            # t2 = time.time()
            # print(f"conb transaltion time:{t2 - t1}")
            # tranString += "\n" + conbinedResultTrans
            # wsSend(ws)

            
            print("task 2:")
            print(f"sing recognition : {singledLen}")
            t1 = time.time()
            singledResult = recognition(f"sing{count}.wav")
            t2 = time.time()
            print(f"sing recognition time:{t2 - t1}")
            nowString = singledResult
            wsSend(ws)
            print("---")
            ###

            os.remove("conb{}.wav".format(count))
            os.remove("sing{}.wav".format(count))
            
            hh = 0.2 if(Cutted) else 0.0
            audioLen = int ((hh+conbinedLen)/(hh+conbinedLen + singledLen) * audioLen)
            CutMedia(ws,audioLen)

        else:
            print("One task")

            totaledLen = totaled.duration_seconds
            totaled.export("total{}.wav".format(count))

            print(f"total recognition : {totaledLen}")
            t1 = time.time()           
            totaledResult = recognition(f"total{count}.wav")
            t2 = time.time()
            print(f"total recognition time:{t2 - t1}")


            if("一个市镇的一个市镇" in totaledResult or
               "一个建筑的一个建筑" in totaledResult):
                nowString = ""


            if(totaledResult == nowString and nowString != ""):
                
                mainString.append(totaledResult)
                wsSend(ws)

                PTThread = Thread(target = P_TThread, args = (totaledResult,ws))                 
                PTThread.daemon = True                                    
                PTThread.start()  
                # print(f"total punctuation ")
                # t1 = time.time() 
                # totaledResult = punctuation(totaledResult)
                # t2 = time.time()
                # print(f"total punctuation time:{t2 - t1}")
                # nowString = ""
                # mainString += "\n" + totaledResult
                # wsSend(ws)

                # print(f"total translation ")
                # t1 = time.time()              
                # totaledResultTrans = translation(totaledResult)
                # t2 = time.time()
                # print(f"total translation time:{t2 - t1}")
                # tranString += "\n" + totaledResultTrans
                # wsSend(ws)

                CutMedia(ws,audioLen)

            else:
                nowString = totaledResult
                wsSend(ws)
            os.remove("total{}.wav".format(count))

        T2 = time.time()
        print("Process time:{}".format(T2-T1))
        count+=1

        # print(f"main:{mainString}")
        # print(f"now:{nowString}")
        # print(f"trans:{tranString}")
        print(f"---------------ThreadEnd--------------------------")

        recogOnUse = False                                              #解锁模型
        
    except Exception as e:
        traceback.print_exc()
        threadError = True


def P_TThread(text,ws):
    global nowString, mainString, tranString
    global puncOnUse 


    while(puncOnUse):
        continue

    puncOnUse = True
    textPunc = punctuation(text)
    puncOnUse = False

    def find_from_end(lst, target):
        # 从后向前查找元素，返回位置
        for i in range(len(lst)-1, -1, -1):
            if lst[i] == target:
                return i
        return -1
    # 找到最后一个子字符串的位置
    last_occurrence_position = find_from_end(mainString,text)



    # 如果找到了子字符串
    if last_occurrence_position != -1:
        # 替换最后一个子字符串
        mainString[last_occurrence_position] = textPunc
    else:
        mainString.append(textPunc)
    wsSend(ws)

    textTrans = translation(textPunc)
    tranString.append(textTrans)
    wsSend(ws)

#websocket端口函数
@sockets.route('/echo')
def echo_socket(ws):                                                
    global ws_audio_data
    global clockFlag
    global recogOnUse
    global mainString
    global nowString
    global tranString
    global CutSeconde
    global head
    global count
    global Cutted

    print("ws set")

    if(recogOnUse):
        while(recogOnUse):
            continue


    init()
    ws_audio_data[ws] = []                                          #存储websocket传入的二进制数据的缓存数组

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
            mainString = []                                                     #清空历史识别内容 
            nowString = ""  
            tranString = []


        elif(clockFlag == 1):                                           #2. 时钟线程提醒主线程执行翻译
            ws_audio_data[ws].append(audio_data)
            print("detect clock")                                       
            clockFlag = 0
            if(len(ws_audio_data[ws]) >= 100):
                process_data = ws_audio_data[ws][0:99]
                print("DATA TOO LONG. PROCESS FIRST 100 DATA")
            else:
                process_data = ws_audio_data[ws]
            print("data length:{}".format(len(process_data)))
            
            translate = Thread(target = newThread,args=(process_data,ws,0))
            translate.daemon = True
            translate.start()                                                   #主线程调用翻译任务线程   

        
        else:                                                                #5. 正常的数据传入
            ws_audio_data[ws].append(audio_data)                                #将sockets数据存入缓存数组中

    print("ws closed") 

def init():
    global ws_audio_data
    global clockFlag
    global recogOnUse
    global mainString
    global nowString
    global CutSeconde
    global head
    global count
    global Cutted
    global recogOnUse
    global onPosProcess
    global threadError
    global tranString

    ws_audio_data = {}                                         
    Cutted = False
    mainString = []
    nowString = ""
    tranString = []
    clockFlag = None
    recogOnUse = False
    recogOnUse = False                                                  #True：模型对象正在使用
    onPosProcess = False                                                #True：正在进行后处理
    threadError = False                                                 #True：线程报错
    count = 0

@app.route('/')
def hello_world():
    return render_template("index2.html")


# @app.errorhandler(Exception)
# def handle_exception(e):                                           #处理服务器异常函数，删除所有临时数据
#     if(os.path.exists('output.mp3')):
#         os.remove("output.mp3")
#     if(os.path.exists('temp.webm')):
#         os.remove("temp.webm")
#     return ""


if __name__ == '__main__':
    # recognition("test.wav")
    # punctuation("测试")
    server = pywsgi.WSGIServer(('0.0.0.0', 8000), app, handler_class=WebSocketHandler)#设立socket端口
    print('server start')
    server.serve_forever()                                         #开启服务器
