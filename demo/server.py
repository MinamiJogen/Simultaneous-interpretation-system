from flask import Flask,render_template
from flask_sockets import Sockets

app = Flask(__name__)
sockets = Sockets(app)


@sockets.route('/echo')
def echo_socket(ws):
    while not ws.closed:
        msg = ws.receive()
        ws.send(msg)


@app.route('/')
def hello_world():
    return render_template("index.html")

if __name__ == '__main__':
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler
    server = pywsgi.WSGIServer(('0.0.0.0', 8000), app, handler_class=WebSocketHandler)
    print('server start')
    server.serve_forever()

