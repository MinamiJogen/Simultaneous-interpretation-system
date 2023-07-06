var isRecording = 0;
var mediaRecorder;
var socket;
var receivedData = "";
var enc;

/**页面初始化 */
window.onload = function() {
  //var enc = new TextEncoder();                                  //转码器

  socket = new WebSocket('ws://localhost:8080');                //建立socket
  socket.onmessage = function(evt) {                            //监听socket传来的信息函数
    decodedData = Array.prototype.map                             //解码->16进制
   		.call(new Uint8Array(evt.data), x => ('00' + x.toString(16)).slice(-2))
   		.join('');
    // 将接收到的消息打印到console
    console.log('Received message from server: ', evt.data);
    //receivedData = receivedData + decodedData;         //本地储存(原数据16进制)
    receivedData = receivedData + evt.data.byteLength;         //本地储存(原数据长度)
    const content = document.getElementById('content');         //动态更新到页面
    content.innerHTML = receivedData;
  };


  socket.binaryType = 'arraybuffer'; // We are talking binary
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
    document.body.style.backgroundColor = '#ffffff';            //更改页面背景提示用户
  }
  isRecording = 0;
  // Add closing socket on 'end' click 
  // if(socket.readyState === WebSocket.OPEN){
  //   socket.close();
  // }
  
});

/**点击开始录制按钮 */
document.getElementById('start').addEventListener('click', function() {

    if(isRecording == 0){                                       //录制处于关闭状态
      if (socket.readyState !== WebSocket.OPEN) {               //尚未建立socket
        console.log('Open a new socket');
        socket = new WebSocket('ws://localhost:8080');          //建立socket
      }

      navigator.mediaDevices.getUserMedia({ audio: true })      //寻求麦克风权限
      .then(stream => handleStream(stream))                     //处理麦克风数据流
      .catch(err => console.log('出现错误：', err));      
      document.body.style.backgroundColor = '#40E0D0';          //更改页面背景提示用户
    }
    
});

/**处理麦克风数据流 */
function handleStream(stream) {
  isRecording = 1;
  mediaRecorder = new MediaRecorder(stream);
  mediaRecorder.start(10);                                      //每10 ms触发数据可用

  mediaRecorder.addEventListener("dataavailable", event => {    //监听录音数据可用
    sendData(event.data);                                       //通过socket发送数据
  });
}


/**通过socket发送数据 */
function sendData(data) {

  var reader = new FileReader();
  reader.readAsArrayBuffer(data);                               //读取数据内容，触发onloadend
  reader.onloadend = function (evt) {                           //监听reader完成读取
    if (evt.target.readyState == FileReader.DONE) { // DONE == 2
      socket.send(evt.target.result);
      console.log('Data sent: ', evt.target.result);  // Log the data sent
    }
  };
}

