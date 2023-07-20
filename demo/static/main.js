var isRecording = 0;      //标识录制状态函数。0：录制未开启 1：录制开启
var mediaRecorder;
var ws;
var receivedData = "";
var enc;
var fileType = "";


/**页面初始化 */
window.onload = function() {

  ws = new WebSocket("ws://localhost:8000/echo");               //建立socket
  console.log('socket set',ws);
  
  ws.onmessage = function(evt) {                                //socket监听信息传入

    console.log('Received message from server: ', evt.data);
    receivedData = evt.data;                                        //储存到本地
    const content = document.getElementById('content');             //动态更新到页面
    content.innerHTML = receivedData;                       
  };


  ws.binaryType = 'arraybuffer'; // We are talking binary
  enc = new TextDecoder("utf-8");//解析arraybuffer
};

/**点击清除内容按钮 */
document.getElementById('clean').addEventListener('click', function() {
  if(isRecording != 0){
    return;
  }
  receivedData = "";                                            //清空本地储存的数据
  const content = document.getElementById('content');           //动态更新到页面
  content.innerHTML = receivedData;
  ws.send("RESET")                                              //提醒后端清除数据
});

/**点击停止录制按钮 */
document.getElementById('end').addEventListener('click', function() {
  if(isRecording == 1){                                       
    mediaRecorder.stop();                                       //停止录音
  }
  isRecording = 0;
});

/**点击开始录制按钮 */
document.getElementById('start').addEventListener('click', function() {
  if(isRecording == 0){ // 录制处于关闭状态
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(stream => handleStream(stream))
      .catch(err => console.log('出现错误：', err));
    document.body.style.backgroundColor = '#40E0D0'; // 更改页面背景提示用户
    ws.send("START_RECORDING");
    console.log("Data sent: ","START_RECORDING")
  }
});

/**处理麦克风数据流 */
function handleStream(stream) {
  isRecording = 1;
  // 创建新的MediaRecorder对象
  mediaRecorder = new MediaRecorder(stream,{mimeType: 'audio/webm'});
  fileType = mediaRecorder.mimeType;
  console.log(mediaRecorder)
  mediaRecorder.onstop = function() {                           //mediaRecorder监听录制停止

    document.body.style.backgroundColor = '#ffffff';                // 更改页面背景提示用户
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


  mediaRecorder.start(100);                                     // 每100 ms触发数据可用


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