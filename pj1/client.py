import select
import signal
import socket
import sys

Socket_list = []
Recv_buffer = 350


class Chat_client:
    def __init__(self, host, port):
        self.host = host
        self.port = int(port)
        serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serversocket.settimeout(2)
        try:
            serversocket.connect((self.host, self.port))
        except Exception:
            print("[系统信息]  无法连接")
        print("[系统信息]  已连接至服务器,可以开始聊天")
        sys.stdout.write('[我] ')
        sys.stdout.flush()
        self.serversocket = serversocket
        self.socket_list = [sys.stdin, serversocket]

    def start(self):
        # 监听服务器和标准输入
        for _signal in (signal.SIGINT, signal.SIGTERM):
            signal.signal(_signal, self.stop)
        try:
            while True:
                r, w, e = select.select(self.socket_list, [], [])
                for sock in r:
                    # 远程服务器可读
                    if sock == self.serversocket:
                        data = sock.recv(Recv_buffer).decode("utf8").strip()
                        if not data:
                            print("\n[系统信息] 服务器已断开")
                            sys.exit()
                        else:
                            sys.stdout.write(data + '\n')
                            sys.stdout.flush()
                            sys.stdout.write('[我] ')
                            sys.stdout.flush()
                    # 标准输入可读
                    else:
       
                        msg = sys.stdin.readline()
                        if not msg.startswith('/'):
                            sys.stdout.write('[我] ')
                            sys.stdout.flush()
                        msg = msg.encode()
                        if len(msg) <= Recv_buffer:
                            msg += b' ' * (Recv_buffer - len(msg))
                        self.serversocket.send(msg)
        except OSError:
            print('select is closed')

    def stop(self,*args):
        self.serversocket.send(b'/exit')

        
def main():
    args = sys.argv
    if len(args) != 3:
        print("请提供端口和地址")
        sys.exit()
    Host = args[1]
    Port = args[2]
    myclient = Chat_client(Host, Port)
    myclient.start()


if __name__ == '__main__':
    main()
