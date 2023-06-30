const WebSocket = require('ws');

const wss = new WebSocket.Server({ port: 8080 });

wss.on('connection', ws => {


  ws.on('message', message => {
    //console.log('Received audio data', message);
    
    console.log('Data length', message.length);
    ws.send(message.length);
    
  });

  ws.on('next', message =>{
    console.log('stream data', message)
  })

  ws.on('close', function() {
    console.log('WebSocket 连接关闭');
});

  
});