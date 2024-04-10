var isRecording = 0;      //标识录制状态函数。0：录制未开启 1：录制开启
var mediaRecorder;
var ws;
var receivedData = "";
var enc;
var fileType = "";
var PrevPackate = ""
var Running = true

var nowStartButton = "start start";
var nowlang = 'cn';
var nowModel = 'zh-en';
var languages={
  'recog content':{
    'cn':'识别内容',
    'en':'Recognized Content'
  },
  'trans content':{
    'cn':"翻译内容",
    'en': 'Translated Content'
  },
  'start start':{
    'cn':"开始录制",
    'en':"Start Recording"
  },
  'start pause':{
    'cn':'录制暂停',
    'en':'Recording Paused'
  },
  'start recording':{
    'cn':'录制中',
    'en':'Recording'
  },
  'contact us':{
    'cn':'联系我们',
    'en':'Contact Us'
  },
  'related links':{
    'cn':'相关链接',
    'en':'Related Links'
  },
  'language-change':{
    'cn':'中',
    'en':'Eng'
  },

  'clean':{
    'cn':'清除内容',
    'en':'Clean Content'
  },

  'download':{
    'cn':'下载文档',
    'en':'Download File'
  },
  'UM':{
    'cn':' 澳门大学官网',
    'en':' The University of Macau'
  },
  'NLP2CT':{
    'cn':' 自然語言處理與中葡機器翻譯實驗室',
    'en':' NLP2CT'
  },
  'start stop':{
    'cn':'录制停止',
    'en':'Recording Stop'
  },

  'font-size':{
    'cn':'字',
    'en':'Font'
  },
  'zh-en':{
    'cn':'中-英',
    'en':'zh-en'
  },
  'en-zh':{
    'cn':'英-中',
    'en':'en-zh'
  },

  'en-pt':{
    'cn':'英-葡',
    'en':'en-pt'
  },

  'zh-pt':{
    'cn':'中-葡',
    'en':'zh-pt'
  }

}

var nowfont = 0;
var buttonFont = ['13pt','20pt','25pt'];
var textFont = ['14pt','16pt','18pt'];
var normalFont = ['14pt','16pt','18pt'];



/**页面初始化 */
window.onload = function() {

  if(isMobileDevice()){
    let mobileSize = '30pt';



    document.body.style.fontSize = '2.5em';

    textFont = ['35pt','40pt','50pt'];
    normalFont = ['35pt','40pt','50pt'];
    buttonFont = ['35pt','40pt','50pt'];
    // 设置字体大小为20px
    

    // document.getElementById('language-change').style.fontSize = '45px';
    // document.getElementById('font-size').style.fontSize = '45px';
    document.getElementById('icon1').style.height = mobileSize;
    document.getElementById('icon2').style.height = mobileSize;
    document.getElementById('model').style.fontSize = mobileSize;
    document.getElementById('zh-en').style.fontSize = mobileSize;
    document.getElementById('en-zh').style.fontSize = mobileSize;
    document.getElementById('en-pt').style.fontSize = mobileSize;
    document.getElementById('en-pt').style.fontSize = mobileSize;
    document.getElementById('title').style.width = '50vw';
    
  }
  document.getElementById('Hiscontent').style.fontSize = textFont[nowfont];
  document.getElementById('Nowcontent').style.fontSize = textFont[nowfont];
  document.getElementById('Trancontent').style.fontSize = textFont[nowfont];
  document.getElementById('recog content').style.fontSize = normalFont[nowfont];
  document.getElementById('trans content').style.fontSize = normalFont[nowfont];
  document.getElementById('start').style.fontSize = buttonFont[nowfont];
  document.getElementById('clean').style.fontSize = buttonFont[nowfont];
  document.getElementById('download').style.fontSize = buttonFont[nowfont];

  document.getElementById('Hiscontent').style.whiteSpace = 'pre-wrap';
  document.getElementById('Trancontent').style.whiteSpace = 'pre-wrap';

  try{
    ws = new WebSocket("wss://wespeak.today:8080/echo");               //建立socket
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

    let btn = document.getElementById('start');
    btn.style.backgroundColor = "#aaabac";

    nowStartButton = "start stop"
    btn.innerHTML = languages[nowStartButton][nowlang];
  })



  ws.onmessage = function(evt) {                                //socket监听信息传入


    receivedData = JSON.parse(evt.data);                                       //储存到本地
    console.log('Received message from server: ', receivedData);   
    
            //动态更新到页面
    
    rcheck = checkOnBottom('recognition')
    const Hiscontent = document.getElementById('Hiscontent'); 
    Hiscontent.innerHTML = splicing(receivedData.mainString);
    if(rcheck){
      let div = document.getElementById('recognition-scroll');
      div.scrollTop = div.scrollHeight;
    }

    const Nowcontent = document.getElementById('Nowcontent');
    const Trancontent = document.getElementById('Trancontent');

    

  
    // Trancontent.innerHTML = receivedData.tranString;
    // Nowcontent.innerHTML = receivedData.nowString;  

    if(PrevPackate == ""){
      let speed = 500.0 / receivedData.nowString.length
      typeWriter('Nowcontent','recognition-scroll', receivedData.nowString,speed)
      speed = 1000.0 / splicing(receivedData.tranString).length
      typeWriter('Trancontent','translation-scroll', splicing(receivedData.tranString),speed)

    }else{
      
      if(receivedData.tranString !== "" && receivedData.tranString.length != PrevPackate.tranString.length){
        TranCommon = getCommonPrefix(splicing(PrevPackate.tranString), splicing(receivedData.tranString))
        Trancontent.innerHTML = splicing(receivedData.tranString).substring(0,TranCommon);
        let speed = 1000.0 / splicing(receivedData.tranString).substring(TranCommon).length
        setTimeout(typeWriter('Trancontent','translation-scroll', splicing(receivedData.tranString).substring(TranCommon),speed),0)
      }
      
      if(receivedData.nowString !== ""){
        NowCommon = getCommonPrefix(PrevPackate.nowString, receivedData.nowString)
        Nowcontent.innerHTML = receivedData.nowString.substring(0,NowCommon); 
        let speed = 500.0 / receivedData.nowString.substring(NowCommon).length
        setTimeout(typeWriter('Nowcontent','recognition-scroll', receivedData.nowString.substring(NowCommon),speed),0)
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

window.addEventListener("beforeunload", (event) => {
  if(isRecording == 1)
    setTimeout(function() {
      ws.send("STOP_RECORDING");                                      // 提醒后端停止录制
      //ws.send(fileType);
      console.log("Data sent: ", "STOP_RECORDING");},100);
});


document.getElementById('language-change').addEventListener('click', function() {
    console.log('language change',nowlang);
    nowlang = (nowlang == 'cn')? 'en': 'cn';

    document.getElementById('recog content').innerHTML = languages['recog content'][nowlang];
    document.getElementById('trans content').innerHTML = languages['trans content'][nowlang];
    document.getElementById('contact us').innerHTML = languages['contact us'][nowlang];
    document.getElementById('related links').innerHTML = languages['related links'][nowlang];
    document.getElementById('recog content').innerHTML = languages['recog content'][nowlang];
    document.getElementById('start').innerHTML = languages[nowStartButton][nowlang];
    // document.getElementById('language-change').innerHTML = languages['language-change'][nowlang];
    document.getElementById('clean').innerHTML = languages['clean'][nowlang];
    document.getElementById('download').innerHTML = languages['download'][nowlang];
    // document.getElementById('font-size').innerHTML = languages['font-size'][nowlang];
    document.getElementById('model').innerHTML = languages[nowModel][nowlang];
    document.getElementById("zh-en").innerHTML = languages["zh-en"][nowlang];
    document.getElementById("en-zh").innerHTML = languages["en-zh"][nowlang];
    document.getElementById('zh-pt').innerHTML = languages['zh-pt'][nowlang];
    document.getElementById('en-pt').innerHTML = languages['en-pt'][nowlang];

    link = document.getElementById('UM');
    img = link.querySelector('img');
    link.textContent = languages['UM'][nowlang];
    link.insertBefore(img,link.firstChild);

    link = document.getElementById('NLP2CT');
    img = link.querySelector('img');
    link.textContent = languages['NLP2CT'][nowlang];
    link.insertBefore(img,link.firstChild);

})

document.getElementById('font-size').addEventListener('click', function(){
    nowfont = nowfont + 1;
    if( nowfont == 3){
      nowfont = 0;
    }

    document.getElementById('Hiscontent').style.fontSize = textFont[nowfont];
    document.getElementById('Nowcontent').style.fontSize = textFont[nowfont];
    document.getElementById('Trancontent').style.fontSize = textFont[nowfont];
    document.getElementById('recog content').style.fontSize = normalFont[nowfont];
    document.getElementById('trans content').style.fontSize = normalFont[nowfont];
    document.getElementById('start').style.fontSize = buttonFont[nowfont];
    document.getElementById('clean').style.fontSize = buttonFont[nowfont];
    document.getElementById('download').style.fontSize = buttonFont[nowfont];


})

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

document.getElementById('model').addEventListener('click', function() {
  var x = document.getElementById("hiddenButton");
  var fa = document.getElementById("model");
  var rect = fa.getBoundingClientRect();

  x.style.top = rect.bottom +"px";
  x.style.width = rect.width + "px";
  x.style.left = rect.left + "px";

  // console.log("position",[rect.bottom,rect.left])
  // console.log("realposition",[x.style.top,x.style.left])

  var buttons = document.querySelectorAll("#hiddenButton button")

  for(i=0;i<buttons.length;i++){
    if(buttons[i].innerHTML == fa.innerHTML){
      buttons[i].style.display = "none";
      // console.log("hide",buttons[i]);
    }else{
      buttons[i].style.display = "block";
      // console.log("show",buttons[i]);
    }
  }


  if(x.style.display == "none"){
    x.style.display = "block";
  }else{
    x.style.display = "none";
  }
  
});


function selectMode(mode){
  document.getElementById('hiddenButton').style.display = "none";

  if(isRecording == 1 || !Running){
    return;
  }
  if(mode != nowModel){
    
    nowModel = mode
    document.getElementById('model').innerHTML = languages[nowModel][nowlang];
    console.log("reset model",nowModel)
    ws.send('RESET')
    ws.send(nowModel)

    const Hiscontent = document.getElementById('Hiscontent');             //动态更新到页面
    const Nowcontent = document.getElementById('Nowcontent');
    const Trancontent = document.getElementById('Trancontent');
  
    Trancontent.innerHTML = ""
    Hiscontent.innerHTML = ""
    Nowcontent.innerHTML = ""
  
    PrevPackate = ""

  }

}


// /**点击停止录制按钮 */
// document.getElementById('end').addEventListener('click', function() {
//   if(isRecording == 1 && Running){                                       
//     mediaRecorder.stop();                                       //停止录音
//   }
//   isRecording = 0;
// });

/**点击开始录制按钮 */
document.getElementById('start').addEventListener('click', function() {
  let btn = document.getElementById("start");

  if(isRecording == 0 && Running){ // 录制处于关闭状态
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(stream => handleStream(stream))
      .catch(err => console.log('出现错误：', err));
    // document.body.style.backgroundColor = '#40E0D0'; // 更改页面背景提示用户
    ws.send("START_RECORDING");
    console.log("Data sent: ","START_RECORDING")

    btn.style.backgroundColor = "red";
    nowStartButton = 'start recording';

    btn.innerHTML = languages[nowStartButton][nowlang];
  }else if(Running){
    mediaRecorder.stop();                                       //停止录音
    isRecording = 0;

    btn.style.backgroundColor = "#008CBA";
    nowStartButton = "start pause";
    btn.innerHTML = languages[nowStartButton][nowlang];

  }



});

document.getElementById('download').addEventListener('click', function() {
  if(isRecording == 1){
    return ;
  }
  // 创建一个包含文本内容的Blob对象

  let text = ""
  if(PrevPackate != ""){
    console.log("rawData",PrevPackate);
    for(i = 0; i < PrevPackate.mainString.length;i++){
      text = text + PrevPackate.mainString[i] + "\n";
      if(i < PrevPackate.tranString.length)
        text = text + PrevPackate.tranString[i] + "\n";
    }
  }

  console.log("Download Content", text);

  let file = new Blob([text], {type: 'text/plain'});

  // 使用URL.createObjectURL方法将Blob对象转换为一个URL
  var url = URL.createObjectURL(file);

  // 创建一个新的a元素，并设置其href属性为上面生成的URL
  var a = document.createElement('a');
  a.href = url;

  // 设置a元素的download属性，这样当用户点击这个元素时，浏览器就会下载这个URL指向的内容，并将其保存为一个文件
  a.download = 'myFile.txt';

  // 将a元素添加到文档中
  document.body.appendChild(a);

  // 模拟用户点击a元素，从而触发下载操作
  a.click();

  // 最后，从文档中移除a元素
  document.body.removeChild(a);

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
      // console.log('Data sent: ', evt.target.result);
    }
  };
}

function isAppleWebkit() {
  var userAgent = navigator.userAgent || navigator.vendor || window.opera;//获取用户设备识别码
  var isIOS = /iPad|iPhone|iPod/.test(userAgent) && !window.MSStream;//判断是否是iOS移动设备
  var isSafariOnMac = /^((?!chrome|android).)*safari/i.test(userAgent) && /Macintosh/.test(userAgent);//判断是否是macOS且是Safari浏览器

  return isIOS || isSafariOnMac;
}

function isMobileDevice(){
  return (typeof window.orientation != 'undefined' || (navigator.userAgent.indexOf('IEMobile') !== -1));
}