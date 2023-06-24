document.getElementById('start').addEventListener('click', function() {
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(stream => handleStream(stream))
      .catch(err => console.log('出现错误：', err));
  });
  
  function handleStream(stream) {
    const mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.start();
  
    const audioChunks = [];
    mediaRecorder.addEventListener("dataavailable", event => {
      audioChunks.push(event.data);
      sendData(event.data);
    });
  
    setTimeout(() => {
      mediaRecorder.stop();
    }, 3000);
  }
  
  function sendData(data) {
    const socket = new WebSocket('ws://localhost:8080');
    socket.binaryType = 'arraybuffer'; // We are talking binary
    socket.onopen = function(evt) {
      var reader = new FileReader();
      reader.readAsArrayBuffer(data);
      reader.onloadend = function (evt) {
        if (evt.target.readyState == FileReader.DONE) { // DONE == 2
          socket.send(evt.target.result);
        }
      };
    };
  }  