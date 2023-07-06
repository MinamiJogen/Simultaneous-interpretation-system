from flask import Flask
from flask_sockets import Sockets

app = Flask(__name__)
sockets = Sockets(app)


@sockets.route('/')
def handle_socket(ws):
    print("check")
    while not ws.closed:
        message = ws.receive()
        if message:
            print(message)
            ws.send(message)

if __name__ == '__main__':
    
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler
    server = pywsgi.WSGIServer(('', 8080), app, handler_class=WebSocketHandler)
    server.serve_forever()
    