var isRecording = 0;      //标识录制状态函数。0：录制未开启 1：录制开启
var mediaRecorder;
var ws;
var receivedData = "";
var enc;
var fileType = "";
var PrevPackate = ""
var Running = true

/**页面初始化 */
window.onload = function() {

  document.getElementById('Hiscontent').style.whiteSpace = 'pre-wrap';
  document.getElementById('Trancontent').style.whiteSpace = 'pre-wrap';

  try{
    ws = new WebSocket("wss://wespeak.today:8000/echo");               //建立socket
    console.log('socket set',ws);
  }catch (err){
    window.alert("Web socket cannot connect!!!" + err.message);
    Running = False;
  }
  
  ws.addEventListener("close", (event) =>{
    window.alert("Web socket disconnected. Please refrash the page.");
    if(isRecording == 1){                                       
      mediaRecorder.stop();                                       //停止录音
    }
    isRecording = 0;

    Running = false;
  })



  ws.onmessage = function(evt) {                                //socket监听信息传入


    receivedData = JSON.parse(evt.data);                                       //储存到本地
    console.log('Received message from server: ', receivedData);   
    
            //动态更新到页面
    
    rcheck = checkOnBottom('recognition')
    const Hiscontent = document.getElementById('Hiscontent'); 
    Hiscontent.innerHTML = splicing(receivedData.mainString);
    if(rcheck){
      let div = document.getElementById('recognition');
      div.scrollTop = div.scrollHeight;
    }

    const Nowcontent = document.getElementById('Nowcontent');
    const Trancontent = document.getElementById('Trancontent');

    

  
    // Trancontent.innerHTML = receivedData.tranString;
    // Nowcontent.innerHTML = receivedData.nowString;  

    if(PrevPackate == ""){
      let speed = 500.0 / receivedData.nowString.length
      typeWriter('Nowcontent','recognition', receivedData.nowString,speed)
      speed = 500.0 / splicing(receivedData.tranString).length
      typeWriter('Trancontent','translation', splicing(receivedData.tranString),speed)

    }else{
      
      if(receivedData.tranString !== ""){
        TranCommon = getCommonPrefix(splicing(PrevPackate.tranString), splicing(receivedData.tranString))
        Trancontent.innerHTML = splicing(receivedData.tranString).substring(0,TranCommon);
        let speed = 700.0 / splicing(receivedData.tranString).substring(TranCommon).length
        setTimeout(typeWriter('Trancontent','translation', splicing(receivedData.tranString).substring(TranCommon),speed),0)
      }
      
      if(receivedData.nowString !== ""){
        NowCommon = getCommonPrefix(PrevPackate.nowString, receivedData.nowString)
        Nowcontent.innerHTML = receivedData.nowString.substring(0,NowCommon); 
        let speed = 500.0 / receivedData.nowString.substring(NowCommon).length
        setTimeout(typeWriter('Nowcontent','recognition', receivedData.nowString.substring(NowCommon),speed),0)
      }else{
        Nowcontent.innerHTML = ""; 
      }
    }  
    PrevPackate = receivedData;
  };
  
  navigator.mediaDevices.getUserMedia({ audio: true })
  .then(function(stream) {
    console.log('用户已授权使用麦克风');
  })
  .catch(function(err) {
    console.log('用户拒绝了麦克风权限请求', err);
  });

  const Hiscontent = document.getElementById('Hiscontent');             //动态更新到页面
  const Nowcontent = document.getElementById('Nowcontent');
  const Trancontent = document.getElementById('Trancontent');

  Trancontent.innerHTML = "";
  Hiscontent.innerHTML = "";
  Nowcontent.innerHTML = "";  

  ws.binaryType = 'arraybuffer'; // We are talking binary
  enc = new TextDecoder("utf-8");//解析arraybuffer
};


/**点击清除内容按钮 */
document.getElementById('clean').addEventListener('click', function() {
  if(isRecording != 0 || Running == false){
    return;
  }
                                              //清空本地储存的数据
  const Hiscontent = document.getElementById('Hiscontent');             //动态更新到页面
  const Nowcontent = document.getElementById('Nowcontent');
  const Trancontent = document.getElementById('Trancontent');

  Trancontent.innerHTML = ""
  Hiscontent.innerHTML = ""
  Nowcontent.innerHTML = ""

  PrevPackate = ""

  ws.send("RESET")                                              //提醒后端清除数据
});

/**点击停止录制按钮 */
document.getElementById('end').addEventListener('click', function() {
  if(isRecording == 1 && Running){                                       
    mediaRecorder.stop();                                       //停止录音
  }
  isRecording = 0;
});

/**点击开始录制按钮 */
document.getElementById('start').addEventListener('click', function() {
  if(isRecording == 0 && Running){ // 录制处于关闭状态
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(stream => handleStream(stream))
      .catch(err => console.log('出现错误：', err));
    // document.body.style.backgroundColor = '#40E0D0'; // 更改页面背景提示用户
    ws.send("START_RECORDING");
    console.log("Data sent: ","START_RECORDING")
  }
});

/**处理麦克风数据流 */
function handleStream(stream) {
  isRecording = 1;
  // 创建新的MediaRecorder对象
  if (isAppleWebkit()) {
    // 对于AppleWebkit设备，使用audio/mp4
    mediaRecorder = new MediaRecorder(stream, {mimeType: 'audio/mp4'});
  } else {
    // 对于非AppleWebkit设备，使用audio/webm
    mediaRecorder = new MediaRecorder(stream, {mimeType: 'audio/webm'});
  }
  fileType = mediaRecorder.mimeType;
  console.log(mediaRecorder)
  mediaRecorder.onstop = function() {                           //mediaRecorder监听录制停止

    // document.body.style.backgroundColor = '#ffffff';                // 更改页面背景提示用户
    setTimeout(function() {
      ws.send("STOP_RECORDING");                                      // 提醒后端停止录制
      //ws.send(fileType);
      console.log("Data sent: ", "STOP_RECORDING");},100);
    
    //console.log("Data sent: ", fileType);
  };
  mediaRecorder.addEventListener("dataavailable", event => {    //mediaRecorder监听数据可用
    
    // ws.send(event.data);                                            
    // console.log('Data sent: ', event.data);
    sendData(event.data);
  });


  mediaRecorder.start(200);                                     // 每500 ms触发数据可用


}

function checkOnBottom(id){

  return true;
  let div = document.getElementById(id);

  if (div.scrollTop + div.clientHeight >= div.scrollHeight){
    return true
  }else{
    return false
  }
}

function typeWriter(id,divid,txt,speed) {
  let i = 0;
  // console.log('aa',typeof(txt))
  // console.log('bb', txt)

  let lengg = txt.length

  function type(){
    if (i < lengg) {
      let isOnBottom = checkOnBottom(divid);
      document.getElementById(id).innerHTML += txt.charAt(i);
      if(isOnBottom){
        document.getElementById(divid).scrollTop = document.getElementById(divid).scrollHeight;
      }
      i++;
      setTimeout(type, speed);
    }
  }

  type();

}

function splicing(lst){
  let str = "";
  if(lst.length > 0)
    str = lst[0];

  for(i=1;i<lst.length;i++){
    str += "\n"+lst[i];
  }

  return str
}


function getCommonPrefix(str1, str2) {
  let i = 0; // 初始化索引为0
  // console.log('bb', str1)
  // console.log('bb', str2)
  while (i < Math.min(str1.length, str2.length)) {
      if (str1[i] !== str2[i]) {
          break; // 如果当前位置不相等，则跳出循环
      }
      i++; // 遍历下一个字符
  }
  return i;
  // str2.substring(i);
}

/**通过socket发送数据 */
function sendData(data) {
  var reader = new FileReader();
  reader.readAsArrayBuffer(data); // 读取数据内容，触发onloadend
  reader.onloadend = function (evt) { // 监听reader完成读取
    if (evt.target.readyState == FileReader.DONE) { // DONE == 2
      ws.send(evt.target.result);
      console.log('Data sent: ', evt.target.result);
    }
  };
}

function isAppleWebkit() {
  var userAgent = navigator.userAgent || navigator.vendor || window.opera;
  var isIOS = /iPad|iPhone|iPod/.test(userAgent) && !window.MSStream;
  var isSafariOnMac = /^((?!chrome|android).)*safari/i.test(userAgent) && /Macintosh/.test(userAgent);

  return isIOS || isSafariOnMac;
}