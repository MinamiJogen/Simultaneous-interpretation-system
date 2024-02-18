import time
import requests

arr = {'你好，我是傻逼', '女士们、先生们， 你们好',"維基百科是維基媒體基金會運營的一個多語言的百科全書，目前是全球網路上最大且最受大眾歡迎的參考工具書，名列全球二十大最受歡迎的網站，特點是自由內容、自由編輯與自由著作權。"}


for str in arr:
    url = "https://umcat.cis.um.edu.mo/api/translate.php"

    data = {
        'from':"zh-cn",
        'to':'en',
        'text':str,

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