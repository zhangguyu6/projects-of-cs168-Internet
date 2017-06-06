#-*- coding:utf-8 -*-
import sys
import socket
import select
import signal
from collections import defaultdict
from functools import partial
from traceback import format_exc

# 处理粘包的方法,发送,接收都限定为350个byte,不够以空格填充
Recv_buffer = 350


class SetNameError(Exception):
    pass


class JoinChannelError(Exception):
    pass


class NoChannelError(Exception):
    pass


class CreateChannelError(Exception):
    pass


class HasChannelError(Exception):
    pass


class MsgIsToolong(Exception):
    pass


class Server:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, int(port)))
        server.listen(5)
        server.setblocking(0)
        self.server = server
        self.connections = {}
        self.Channels = defaultdict(list)
        epoll = select.epoll()
        self.select = epoll
        self.readhandlers = {}
        self.writehandlers = {}
        self.register = {}

    def add_handler(self, fd, event, readhander=None, writehander=None):
        if self.connections.get(fd):
            self.select.modify(fd, event)
        else:
            self.connections[fd] = ['default', None]
            self.select.register(fd, event)

        if readhander:
            self.readhandlers[fd] = (readhander)
        if writehander:
            self.writehandlers[fd] = (writehander)

    def remove_handler(self, fd):
        # 使epoll重新监控写入描述符
        self.writehandlers.pop(fd, None)
        self.select.modify(fd, select.EPOLLIN)

    def accept(self):
        for i in range(5):
            try:
                conn, address = self.server.accept()
                print("user from {} has connected".format(address))
            except OSError:
                break
            else:
                conn.setblocking(0)
                # 指定默认频道

                self.Channels['default'].append(conn)
                self.add_handler(conn.fileno(), select.EPOLLIN, readhander=partial(
                    self.read, conn))

    def read(self, conn):
        print("start read user {}".format(conn.fileno()))
        try:
            msg = conn.recv(Recv_buffer)
            msg = msg.decode('utf8')
            msg = msg.strip()
        except Exception:
            conn.close()
            raise
        else:
            self.dispatch(conn, msg)

    def dispatch(self, conn, msg):
        print("read the message is {}".format(msg))
        try:
            channel = self.connections[conn.fileno()][0]
            if msg.startswith('/'):
                if msg.startswith('/setname'):

                    if ' ' not in msg:
                        raise SetNameError
                    name = msg.split(" ")[-1]
                    originname = self.connections[conn.fileno()][1]
                    self.connections[conn.fileno()][1] = name

                    if not originname:
                        welcome = '[系统信息] 欢迎{}加入聊天室'.format(name)
                    else:
                        welcome = '[系统信息] {}已更名为{}'.format(originname, name)

                    print(welcome)

                    for person in self.Channels[channel]:
                        self.add_handler(person.fileno(),  select.EPOLLOUT, writehander=partial(
                            self.write, person, welcome),)

                elif msg.startswith('/join'):
                    if ' ' not in msg:
                        raise JoinChannelError

                    newchannel = msg.split(" ")[-1]
                    oldchannel = self.connections[conn.fileno()][0]
                    if newchannel not in self.Channels:
                        raise NoChannelError
                    self.connections[conn.fileno()][0] = newchannel
                    self.Channels[oldchannel].remove(conn)
                    self.Channels[newchannel].append(conn)
                    name = self.connections[conn.fileno()][1]
                    name = name if name else '匿名用户'
                    welcome = '[系统信息] 欢迎{}加入频道{}'.format(name, newchannel)

                    print(welcome)

                    for person in self.Channels[newchannel]:
                        self.add_handler(person.fileno(),  select.EPOLLOUT, writehander=partial(
                            self.write, person, welcome))

                elif msg.startswith('/create'):
                    if ' ' not in msg:
                        raise CreateChannelError

                    newchannel = msg.split(" ")[-1]
                    oldchannel = self.connections[conn.fileno()][0]
                    if newchannel in self.Channels:
                        raise HasChannelError

                    self.connections[conn.fileno()][0] = newchannel
                    self.Channels[oldchannel].remove(conn)
                    self.Channels[newchannel].append(conn)
                    name = self.connections[conn.fileno()][1]
                    name = name if name else '匿名用户'
                    welcome = '[系统信息] {}创建频道{}成功'.format(name, newchannel)

                    print(welcome)

                    self.add_handler(conn.fileno(), select.EPOLLOUT, writehander=partial(
                        self.write, conn, welcome))
                elif msg.startswith('/ls'):
                    channellist = self.Channels.keys()
                    news = "[系统信息] 已有的频道为: \n" + '\n'.join(channellist)

                    print(news)

                    self.add_handler(conn.fileno(), select.EPOLLOUT, writehander=partial(
                        self.write, conn, news))

                elif msg.startswith('/exit'):
                    name = self.connections[conn.fileno()][1]
                    name = name if name else '匿名用户'
                    news = "[系统信息] {}已登出".format(name)
                    for person in self.Channels[channel]:
                        print(person, conn)
                        if person == conn:
                            self.write_and_exit(person, news)
                        else:
                            self.add_handler(person.fileno(), select.EPOLLOUT, writehander=partial(
                                self.write, person, news))
                elif msg.startswith('/help'):
                    news = "[系统信息] 帮助信息: \n{0:<15}\
                                            \n{1:<15}\
                                            \n{2:<15}\
                                            \n{3:<15}\
                                            \n{4:<15}\n".format('/setname <name> 设置用户名 ',
                                                                '/create <频道> 创建频道',
                                                                '/join <频道> 加入频道',
                                                                '/ls 列出所有频道',
                                                                '/exit 退出')
                    print(len(news))
                    self.add_handler(conn.fileno(),  select.EPOLLOUT, writehander=partial(
                        self.write, conn, news))
                else:
                    print(msg)
                    news = "[系统信息] 未知命令 输入 /help 获得帮助信息"
                    self.add_handler(conn.fileno(), select.EPOLLOUT, writehander=partial(
                        self.write, conn, news))
            else:
                name = self.connections[conn.fileno()][1]
                name = name if name else '匿名用户'
                msg = "[" + name + "]  " + msg
                print('commommsg', msg)
                if len(msg) > Recv_buffer:
                    raise MsgIsToolong
                for person in self.Channels[channel]:
                    if person != conn:
                        self.add_handler(person.fileno(), select.EPOLLOUT, writehander=partial(
                            self.write, person, msg))

        except SetNameError:
            news = "[系统信息] 错误的名称命令 标准格式是 /setname <name>"
            self.add_handler(conn.fileno(),  select.EPOLLOUT, writehander=partial(
                self.write, conn, news))
        except JoinChannelError:
            news = "[系统信息] 错误的加入频道命令 标准格式是 /join <频道>"
            self.add_handler(conn.fileno(),  select.EPOLLOUT, writehander=partial(
                self.write, conn, news))
        except NoChannelError:
            news = "[系统信息] 错误的加入频道命令 该频道不存在"
            self.add_handler(conn.fileno(),  select.EPOLLOUT, writehander=partial(
                self.write, conn, news))
        except CreateChannelError:
            news = "[系统信息] 错误的创建频道命令 标准格式是 /setname <name>"
            self.add_handler(conn.fileno(), select.EPOLLOUT, writehander=partial(
                self.write, conn, news))
        except HasChannelError:
            news = "[系统信息] 错误的创建频道命令 该频道已存在"
            self.add_handler(conn.fileno(), select.EPOLLOUT, writehander=partial(
                self.write, conn, news))
        except MsgIsToolong:
            news = "[系统信息] 消息太长,只支持小于Recv_buffer的消息"
            self.add_handler(conn.fileno(), select.EPOLLOUT, writehander=partial(
                self.write, conn, news))

    def write(self, conn, msg):
        self.remove_handler(conn.fileno())
        msg = msg.encode()
        print(len(msg))
        if len(msg) < Recv_buffer:
            msg = msg + b' ' * (Recv_buffer - len(msg))
        conn.send(msg)

    def write_and_exit(self, conn, msg):
        self.remove_handler(conn.fileno())
        msg = msg.encode()
        if len(msg) < Recv_buffer:
            msg = msg + b' ' * (Recv_buffer - len(msg))
        try:
            conn.send(msg)
        finally:
            self.select.unregister(conn.fileno())
            self.Channels[self.connections[conn.fileno()][0]].remove(conn)
            self.connections.pop(conn.fileno(), None)
            conn.close()

    def run(self):
        print("servver start listen on {}:{}".format(self.host, self.port))
        for _signal in (signal.SIGINT, signal.SIGTERM):
            signal.signal(_signal, self.stop)

        self.add_handler(self.server.fileno(),  select.EPOLLIN,
                         readhander=self.accept)
        try:
            while True:
                events = self.select.poll(2)
                for fileno, event in events:
                    if event & select.EPOLLIN:
                        handler = self.readhandlers.get(fileno)
                        if handler:
                            handler()
                    elif event & select.EPOLLOUT:
                        handler = self.writehandlers.get(fileno)
                        if handler:
                            handler()
        except Exception as e:
            print(format_exc())
            self.select.close()
            self.server.close()

    def stop(self, *args):
        print("server is stoped")
        self.select.close()
        self.server.close()
        sys.exit()


def main():
    args = sys.argv
    if len(args) != 3:
        print("Please supply a server address and port.")
        sys.exit()
    Host = args[1]
    Port = args[2]
    server = Server(Host, Port)
    server.run()


if __name__ == '__main__':
    main()
