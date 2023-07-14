var isRecording = 0;
var mediaRecorder;
var ws;
var receivedData = "";
var enc;
var fileType = "";


/**页面初始化 */
window.onload = function() {
  //var enc = new TextEncoder();                                  //转码器

  ws = new WebSocket("ws://localhost:8000/echo");               //建立socket
  console.log('socket set',ws);
  
  ws.onmessage = function(evt) {
    // decodedData = Array.prototype.map                             //解码->16进制
   	// 	.call(new Uint8Array(evt.data), x => ('00' + x.toString(16)).slice(-2))
   	// 	.join('');
    // 将接收到的消息打印到console
    console.log('Received message from server: ', evt.data);
    receivedData = evt.data;                                    //本地储存(原数据16进制)
    //receivedData = receivedData + evt.data.byteLength;         //本地储存(原数据长度)
    const content = document.getElementById('content');         //动态更新到页面
    //content.innerHTML = receivedData;
    content.innerHTML = receivedData;
  };


  ws.binaryType = 'arraybuffer'; // We are talking binary
  enc = new TextDecoder("utf-8");//解析arraybuffer
};

/**点击清除内容按钮 */
document.getElementById('clean').addEventListener('click', function() {
  receivedData = "";                                            //清空本地储存的数据
  const content = document.getElementById('content');           //动态更新到页面
  content.innerHTML = receivedData;
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
  mediaRecorder.onstop = function() {
    // 处理停止录制后的操作
    document.body.style.backgroundColor = '#ffffff'; // 更改页面背景提示用户
    ws.send("STOP_RECORDING"); // Send a special message to indicate that recording has ended
    //ws.send(fileType);
    console.log("Data sent: ", "STOP_RECORDING");
    //console.log("Data sent: ", fileType);
  };
  mediaRecorder.addEventListener("dataavailable", event => {
    // 直接通过socket发送数据
    ws.send(event.data);
    console.log('Data sent: ', event.data);  // Log the data sent
  });


  mediaRecorder.start(100); // 每10 ms触发数据可用


}

/**通过socket发送数据 */
function sendData(data) {
  var reader = new FileReader();
  reader.readAsArrayBuffer(data); // 读取数据内容，触发onloadend
  reader.onloadend = function (evt) { // 监听reader完成读取
    if (evt.target.readyState == FileReader.DONE) { // DONE == 2
      ws.send(evt.target.result);
      console.log('Data sent: ', evt.target.result);  // Log the data sent
    }
  };
}