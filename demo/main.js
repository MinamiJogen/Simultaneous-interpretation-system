var isRecording = 0;
var mediaRecorder;
var socket;

window.onload = function() {
  socket = new WebSocket('ws://localhost:8080');
  socket.binaryType = 'arraybuffer'; // We are talking binary
};

document.getElementById('start').addEventListener('click', function() {
    if(isRecording == 0){
      navigator.mediaDevices.getUserMedia({ audio: true })
      .then(stream => handleStream(stream))
      .catch(err => console.log('出现错误：', err));
      document.body.style.backgroundColor = '#40E0D0';
    }
    
});

document.getElementById('end').addEventListener('click', function() {
    if(isRecording == 1){
      mediaRecorder.stop();
      document.body.style.backgroundColor = '#ffffff';
    }
    isRecording = 0;
    // Add closing socket on 'end' click
    if(socket.readyState === WebSocket.OPEN){
      socket.close();
    }
});

function handleStream(stream) {
  isRecording = 1;
  mediaRecorder = new MediaRecorder(stream);
  mediaRecorder.start(1);  // Trigger dataavailable event every 1 ms

  mediaRecorder.addEventListener("dataavailable", event => {
    sendData(event.data);
  });
}

function sendData(data) {
  if (socket.readyState !== WebSocket.OPEN) {
    console.error('WebSocket is not open');
    return;
  }

  socket.onmessage = function(evt) {
    // 将接收到的消息打印到console
    console.log('Received message from server: ', evt.data);
  };

  var reader = new FileReader();
  reader.readAsArrayBuffer(data);
  reader.onloadend = function (evt) {
    if (evt.target.readyState == FileReader.DONE) { // DONE == 2
      socket.send(evt.target.result);
      console.log('Data sent: ', evt.target.result);  // Log the data sent
    }
  };
}
