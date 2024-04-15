from flask import Flask,render_template, g
from flask_sockets import Sockets
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
import random
import threading
from io import BytesIO

import whisper
from ppasr.predict import PPASRPredictor


from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler


app = Flask(__name__)
sockets = Sockets(app)


# DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
DEVICE = 'cpu'
# DEVICE = 'cuda'
print(f"Using device:{DEVICE}")
use_gpu = True if(DEVICE =='cuda') else False
wsID = {}
clockFlag = {}                                                    #时钟线程与主线程用于沟通的参数 
                                                                        #1：时钟中断主线程 0：主线程完成任务，等待时钟中断 2：时钟停止
ws_audio_data = {}                                                  #存储不同websocket发送数据的缓存字典
# recogENOnUse = False                                                  #True：识别模型对象正在使用
recogENOnUse = threading.Lock()
recogZHOnUse = threading.Lock()                                                 #True：识别模型对象正在使用
puncOnUse = threading.Lock()
taskOnConduct = {}
onPosProcess = False                                                #True：正在进行后处理
threadError = False                                                 #True：线程报错
mainString = {}                                                     #历史识别内容
nowString = {}                                                      #当前识别内容
tranString = {}
CutSeconde = {}
Cutted = {}
RecogMode = {}
Modes = ["zh-en","en-zh","zh-pt","en-pt"]


THRESHOLD = 1.0


count = {}


print("加载识别模型...")
####识别模型
predictor = PPASRPredictor(model_tag='conformer_streaming_fbank_wenetspeech',use_gpu= use_gpu)
# model = whisper.load_model('tiny', device=DEVICE)
# model = pipeline("automatic-speech-recognition", model="xmzhu/whisper-tiny-zh",device=DEVICE)
# model = pipeline("automatic-speech-recognition", model="zongxiao/whisper-small-zh-CN")
enmodel = whisper.load_model('tiny.en', device=DEVICE)
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
pun_predictor = PunctuationPredictor(model_dir='models/pun_models3', use_gpu=use_gpu)






#异步时钟函数，定时提醒主线程执行翻译任务
def clock(sec,ws):
    print("clock set")
    global clockFlag
    global onPosProcess
    global taskOnConduct
    time.sleep(max(1.5,sec))
    while(True):                                                    #定时检查状态
        if(clockFlag[ws] == 2 or clockFlag[ws] == None):                                         #前端停止录制，结束时钟
            print("clock end")
            break
        if(not taskOnConduct[ws] and not onPosProcess):                    #模型未占用，后处理未启用
            print("clock")
            clockFlag[ws] = 1                                           #提醒主线程执行翻译
        
        time.sleep(sec/2)
        if(clockFlag[ws] == 2 or clockFlag[ws] == None):                                         #前端停止录制，结束时钟
            print("clock end")
            break
        time.sleep(sec/2)

# #停止录制后，翻译尚未处理数据的线程
# def pos_clock(ws):
#     global recogOnUse
#     global mainString
#     global nowString
#     global tranString
#     while(recogOnUse):
#         continue
   
#     print(f"--------------------Pos_Thread-----------------------")
#     mainString = mainString + "\n"+nowString                                 #更新历史识别内容（历史识别内容 = 历史识别内容 + 当前识别内容）
#     nowString = ""
#     tranString += "\n"+translation(nowString,ws)
#     wsSend(ws)

#     print(f"------------------------------------------------")
    
#音频处理函数，将二进制数据处理为webm格式
# def save_as_webm(data,ws):
#     global count
#     global Cutted
#     global threadError
#     global wsID
#     lenn = len(data)
#     try:
#         data = b''.join(data)
#     except Exception as e:

#         print(f"Data type:{type(data)}")
#         print(f"Data len:{len(data)}")
#         # print(f"Data:{data}")
#         traceback.print_exc()
#         threadError = True
#         for i in len(data):
#             if(type(data[i]) != 'bytearray'): 
                
#                 print(f"{i}:({data[i]}) {bytes}")
#         # for i in range(len(data)):
#         #     if( i != 0 and type(data[i]) != type(data[i-1])):
#         #         print(data[i])

#         raise e
        

#     tempfile = "temp{}{}.wav".format(wsID[ws],count[ws])

#     with open(tempfile, 'wb') as f:                                 #将二进制数据按原格式储存为临时文件（webm）
#         f.write(data)
#         f.close()
    
#     part = ""
#     with open(tempfile,"rb") as f:
#         print(tempfile)
#         audio = AudioSegment.from_file(tempfile)
#         if(Cutted[ws]):
#             part = audio[200:len(audio)]
#         else:
#             part = audio
#     os.remove(tempfile)
#     part.export(tempfile)
#     return tempfile, lenn 

def save_as_webm(data, ws):
    global count
    global Cutted
    global threadError
    global wsID
    lenn = len(data)
    try:
        data = b''.join(data)
    except Exception as e:
        print(f"Data type:{type(data)}")
        print(f"Data len:{len(data)}")
        traceback.print_exc()
        threadError = True
        for i in len(data):
            if(type(data[i]) != 'bytearray'): 
                print(f"{i}:({data[i]}) {bytes}")
        raise e

    # Use BytesIO to handle the data in memory
    data_io = BytesIO(data)
    audio = AudioSegment.from_file(data_io)

    part = ""
    if(Cutted[ws]):
        part = audio[200:len(audio)]
    else:
        part = audio

    tempfile = "temp{}{}.wav".format(wsID[ws],count[ws])

    # Export the audio segment directly to the file
    part.export(tempfile, format="wav")

    return tempfile, lenn


def CutMedia(ws,second):

    global ws_audio_data
    global Cutted
    global head

    print(f"current length:{len(ws_audio_data[ws])}")
    print(f"cut length:{second}")
    del ws_audio_data[ws][1:second]
    # ws_audio_data[ws].insert(0,head)
    Cutted[ws] = True
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
    global puncOnUse
    
    puncOnUse.acquire()
    result = pun_predictor(text)
    puncOnUse.release()
    
    pun = {'。', '，', '！', ',','？','?','、'}
    result = [result[i] for i in range(len(result)) if not (result[i] in pun and result[i-1] in pun)]
    result = ''.join(result)
    result = result.replace('？','')
    if(result[-1] != '。'): 
        result = result + '。'
    return result

def translation(text,ws):
    # return ""
    url = "https://umcat.cis.um.edu.mo/api/translate.php"

    if(RecogMode[ws] == 'zh-en'):      
        data = {
            'from':"zh-cn",
            'to':'en',
            'text':text,
            'system':"UTI"
        }
    elif(RecogMode[ws] == 'en-zh'):
        data = {
            'from':'en',
            'to':'zh-cn',
            'text': text,
            'system':'UTI'
        }
    elif(RecogMode[ws] == "en-pt"):
        data = {
            'from':'en',
            'to':'pt',
            'text': text,
            'system':'UTI'
        }
    elif(RecogMode[ws] == "zh-pt"):
        data = {
            'from':"zh-cn",
            'to':'pt',
            'text':text,
            'system':"UTI"
        }
    t1 = time.time()
    rr = text
    while(rr == text):
        response = requests.post(url,json=data)
        response_dic = response.json()
        # print(response_dic)
        rr = response_dic['translation'][0]['translated'][0]['text'] 

        # status_code = response.status_code
        # print(status_code)
    t2 = time.time()

    print(f"trans time:{t2 - t1}")
    return rr

def recognition(fileList,ws):

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
    global recogENOnUse
    global recogZHOnUse
    if(RecogMode[ws] == 'zh-en' or RecogMode[ws] == 'zh-pt'):
        recogZHOnUse.acquire()
        result = predictor.predict(audio_data=fileList, use_pun=False)['text']
        recogZHOnUse.release()
    elif(RecogMode[ws] == 'en-zh' or RecogMode[ws] =='en-pt'):
        recogENOnUse.acquire()
        result = enmodel.transcribe(fileList)["text"]
        recogENOnUse.release()
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

    packet = {"mainString":mainString[ws], "nowString":nowString[ws], 'tranString':tranString[ws]}
    
    js_packet = json.dumps(packet)
    ws.send(js_packet)

#执行翻译任务的线程函数
def newThread(data,ws,flag):

    global threadError
    global mainString
    global nowString
    global tranString
    global onPosProcess
    global CutSeconde
    global Cutted
    global count
    global wsID
    global taskOnConduct
    try:
        while(taskOnConduct[ws]):
            continue
        
        taskOnConduct[ws] = True
        print(f"--------------------Thread{wsID[ws]}-{count[ws]}--------------------")
        print(f"operate: temp{wsID[ws]}{count[ws]}.wav")

        T1 = time.time()                                                #开始计时
        
        t1 = time.time()
        tempFileName, audioLen = save_as_webm(data,ws)                                   #二进制数据转码mp3
        t2 = time.time()
        print(f"F saving:{t2-t1}")

        t1 = time.time()
        totaled, conbined, singled = audioSlice(tempFileName)
        t2 = time.time()
        print(f"silence segment time:{t2-t1}")
        
        os.remove(tempFileName)


        if(totaled == -1):    
            print("empty audio") 
            CutMedia(ws,audioLen)       
            nowString[ws] = "" 
            wsSend(ws)
            taskOnConduct[ws] = False
            print(f"---------------ThreadEnd--------------------------")
            return 
        elif(totaled == None):
            print("too short")
            nowString[ws] = "" 
            wsSend(ws)
            taskOnConduct[ws] = False
            print(f"---------------ThreadEnd--------------------------")
            return 

        if(conbined != None and singled != None):
            print("Two task")
            
            
            t1 = time.time()

            
            conbinedLen = conbined.duration_seconds
            singledLen = singled.duration_seconds

            conbined.export("conb{}{}.wav".format(wsID[ws],count[ws]))
            singled.export("sing{}{}.wav".format(wsID[ws],count[ws]))  

            t2 = time.time()
            print(f"file preporcessing:{t2-t1}")
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
            conbinedResult = recognition(f"conb{wsID[ws]}{count[ws]}.wav",ws)
            t2 = time.time()
            print(f"conb recognition time:{t2 - t1}")
            mainString[ws].append(conbinedResult) 
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
            singledResult = recognition(f"sing{wsID[ws]}{count[ws]}.wav",ws)
            t2 = time.time()
            print(f"sing recognition time:{t2 - t1}")
            nowString[ws] = singledResult
            wsSend(ws)
            print("---")
            ###
            t1 = time.time()
            os.remove("conb{}{}.wav".format(wsID[ws],count[ws]))
            os.remove("sing{}{}.wav".format(wsID[ws],count[ws]))
            
            hh = 0.2 if(Cutted[ws]) else 0.0
            audioLen = int ((hh+conbinedLen)/(hh+conbinedLen + singledLen) * audioLen)
            CutMedia(ws,audioLen)
            t2 = time.time()
            print(f"post processing time:{t2 - t1}")
        else:
            print("One task")


            t1 = time.time()
            totaledLen = totaled.duration_seconds
            totaled.export("total{}{}.wav".format(wsID[ws],count[ws]))

            t2 = time.time()
            print(f"file preporcessing:{t2-t1}")

            print(f"total recognition : {totaledLen}")
            t1 = time.time()           
            totaledResult = recognition(f"total{wsID[ws]}{count[ws]}.wav",ws)
            t2 = time.time()
            print(f"total recognition time:{t2 - t1}")


            # if("一个市镇的一个市镇" in totaledResult or
            #    "一个建筑的一个建筑" in totaledResult):
            #     nowString = ""

            t1 = time.time()
            if(totaledResult == nowString[ws] and nowString[ws] != ""):
                
                mainString[ws].append(totaledResult)
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
                nowString[ws] = totaledResult
                wsSend(ws)
            os.remove("total{}{}.wav".format(wsID[ws],count[ws]))
        
        t2 = time.time()
        
        print(f"postprocessing time:{t2 - t1}")

        T2 = time.time()
        print("Process time:{}".format(T2-T1))
        
        count[ws]+=1
        taskOnConduct[ws] = False
        # print(f"main:{mainString}")
        # print(f"now:{nowString}")
        # print(f"trans:{tranString}")
        print(f"---------------ThreadEnd--------------------------")


        
    except Exception as e:
        # traceback.print_exc()
        # threadError = True
        return



def P_TThread(text,ws):
    global nowString, mainString, tranString


    def find_from_end(lst, target):
        # 从后向前查找元素，返回位置
        for i in range(len(lst)-1, -1, -1):
            if lst[i] == target:
                return i
        return -1
    try:
        if(RecogMode[ws] == "zh-en" or RecogMode[ws] == "zh-pt"):
            # while(puncOnUse):
            #     continue

            textPunc = punctuation(text)

            # 找到最后一个子字符串的位置
            last_occurrence_position = find_from_end(mainString[ws],text)



            # 如果找到了子字符串
            if last_occurrence_position != -1:
                # 替换最后一个子字符串
                mainString[ws][last_occurrence_position] = textPunc
            else:
                mainString[ws].append(textPunc)
            wsSend(ws)

            textTrans = translation(textPunc,ws)
            tranString[ws].append(textTrans)
            wsSend(ws)
        elif(RecogMode[ws] == 'en-zh'):
            textTrans = translation(text,ws)
            tranString[ws].append(textTrans)
            wsSend(ws)
            

            textTranPunc = punctuation(textTrans)


            # 找到最后一个子字符串的位置
            last_occurrence_position = find_from_end(tranString[ws],textTrans)

            # 如果找到了子字符串
            if last_occurrence_position != -1:
                # 替换最后一个子字符串
                tranString[ws][last_occurrence_position] = textTranPunc
            else:
                tranString[ws].append(textTranPunc)
            wsSend(ws)      
        elif(RecogMode[ws] == "en-pt"):
            textTrans = translation(text,ws)
            tranString[ws].append(textTrans)
            wsSend(ws)
    except:
        return
      

#websocket端口函数
@sockets.route('/echo')
def echo_socket(ws):                                                
    global ws_audio_data
    global clockFlag
    global mainString
    global nowString
    global tranString
    global CutSeconde
    global head
    global count
    global Cutted
    global RecogMode
    global wsID
    global taskOnConduct
    print("ws set")
    
    init(ws)
    print(ws)
    
    random_number = random.randint(0, 1000)
    while(random_number in wsID.values()):
        random_number = random.randint(0, 1000)
    
    wsID[ws] = random_number
    
                                              #存储websocket传入的二进制数据的缓存数组

    while not ws.closed:                                            #死循环
        if(threadError):                                                #若某一线程报错，中断服务器
            exit(0)
            
        audio_data = ws.receive()                                       #读取sockets数据，此为阻塞调用（等待直到有新数据传入）
        # print(audio_data)
        #print(clockFlag)
        if(audio_data == "START_RECORDING"):                            #1. 前端提醒音频开始传输
            print("start recording")

            clockFlag[ws] = 0                                                       #提醒时钟线程主线程就绪

            # head = ws.receive()
            # print(f"head type{type(head)}")
            # ws_audio_data[ws].append(head)

            timer = Thread(target = clock, args = (0.5,ws))                 
            timer.daemon = True                                    
            timer.start()       
                                                            #启动时钟线程
        elif(audio_data == "STOP_RECORDING"):                           #3. 前端提醒音频停止传输    
            print("stop")
            clockFlag[ws] = 2                                                       #提醒时钟关闭
            # posProcess = Thread(target=pos_clock,args=(ws))
            # posProcess.daemon = True
            # posProcess.start()                                                  #开启后处理线程，处理尚未处理的数据

            del ws_audio_data[ws]                                               #清空缓存数组
            ws_audio_data[ws] = []
            Cutted[ws] = False

        elif(audio_data == "RESET"):                                    #4. 前端提醒清除目前记录
            print("reset")
            del ws_audio_data[ws]                                               #清空缓存数组
            ws_audio_data[ws] = []
            mainString[ws] = []                                                     #清空历史识别内容 
            nowString[ws] = ""  
            tranString[ws] = []

        elif(audio_data in Modes):
            if(clockFlag[ws] != 2):
                continue
            print(f"model change:{audio_data}")
            RecogMode[ws] = audio_data            
            
        elif(clockFlag[ws] == 1):                                           #2. 时钟线程提醒主线程执行翻译
            ws_audio_data[ws].append(audio_data)
            print("detect clock")                                       
            clockFlag[ws] = 0
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
    dele(ws)

def init(ws):
    global ws_audio_data
    global clockFlag
    global mainString
    global nowString
    global CutSeconde
    global head
    global count
    global Cutted
    global onPosProcess
    global threadError
    global tranString
    global RecogMode
    global taskOnConduct
    
    taskOnConduct[ws] = False
    ws_audio_data[ws] = []                                        
    Cutted[ws] = False
    mainString[ws] = []
    nowString[ws] = ""
    tranString[ws] = []
    clockFlag[ws] = 2
    count[ws] = 0
    RecogMode[ws] = "zh-en"
    

def dele(ws):
    global ws_audio_data
    global clockFlag
    global mainString
    global nowString
    global CutSeconde
    global head
    global count
    global Cutted
    global onPosProcess
    global threadError
    global tranString
    global RecogMode
    global taskOnConduct
    if ws in ws_audio_data.keys():
        del ws_audio_data[ws]
    if ws in Cutted.keys():                                        
        del Cutted[ws]
    if ws in mainString.keys():
        del mainString[ws]
    if ws in nowString.keys(): 
        del nowString[ws] 
    if ws in tranString.keys():
        del tranString[ws]
    if ws in clockFlag.keys():
        del clockFlag[ws]
    if ws in count.keys():
        del count[ws]
    if ws in RecogMode.keys():
        del RecogMode[ws]
    if ws in taskOnConduct.keys():
        del taskOnConduct[ws]

def delete_wav_files():
    current_directory = os.getcwd()  # 获取当前目录
    """
    删除指定目录中的所有 '.wav' 文件。
    :param folder_path: 目标文件夹的路径
    """
    if not os.path.isdir(current_directory):
        print(f"错误：{current_directory} 不是一个目录")
        return

    for file in os.listdir(current_directory):
        if file.lower().endswith(".wav"):
            file_path = os.path.join(current_directory, file)
            os.remove(file_path)

@app.route('/')
def hello_world():
    random_number = random.randint(1, 100)
    return render_template("index.html",number=random_number)
@app.route("/single")
def return_single():
    random_number = random.randint(1, 100)
    return render_template("indexSingle.html",number=random_number)

# @app.errorhandler(Exception)
# def handle_exception(e):                                           #处理服务器异常函数，删除所有临时数据
#     if(os.path.exists('output.mp3')):
#         os.remove("output.mp3")
#     if(os.path.exists('temp.webm')):
#         os.remove("temp.webm")
#     return ""

delete_wav_files()

if __name__ == '__main__':
    # recognition("test.wav")
    # punctuation("测试")
    server = pywsgi.WSGIServer(('0.0.0.0', 8080), app, handler_class=WebSocketHandler)#设立socket端口
    print('server start')
    server.serve_forever()                                         #开启服务器
