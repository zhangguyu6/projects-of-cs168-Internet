import socket
import random
import traceback
import Checksum
from collections import deque

'''
文件发送客户端
'''


class MaxSyntimesError(Exception):
    ''' max syn times '''


class NotSuchFileError(Exception):
    '''can not find such file '''


class BasicSender(object):
    def __init__(self, dest, port, filename):
        self.dest = dest
        self.dport = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(None)  # blocking
        self.sock.bind(('', random.randint(10000, 40000)))
        print(self.sock.getsockname())
        if filename is None:
            raise NotSuchFileError
        else:
            self.infile = open(filename, "rb")
        # 滑窗最大为 7
        self.window = 7
        # 缓存为 window * 2
        self.buf = deque(maxlen=2 * self.window)

        # 所有收到的回复
        self.recv_record = {}
        # 已接受包的下一个序号
        self.next_ack_seq = None
        # 下一个未接收包的序号
        self.next_not_ack_seq = None

    # 读取回复,堵塞
    def receive(self, timeout=None):
        self.sock.settimeout(timeout)
        try:
            data = self.sock.recv(4096)
            print("receive:", data)
            return data.decode("utf8")
        except (socket.timeout, socket.error):
            return None

    # 发送
    def send(self, message, address=None):
        if address is None:
            address = (self.dest, self.dport)
        print("send:", message)
        self.sock.sendto(message, address)

    # 拼包
    def make_packet(self, msg_type, seqno, msg):
        # syn|<sequence number>||<checksum>
        # dat|<sequence number>|<data>|<checksum>
        # fin|<sequence number>|<data>|<checksum>
        # ack|<sequence number>|<checksum>
        body = b"%b|%d|%b|" % (msg_type.encode(), seqno, msg)
        checksum = Checksum.generate_checksum(body)
        packet = body + checksum
        return packet

    def fileread(self):
        '''
        20ip,8udp, 最多传送1472个字节,设置为1400
        '''
        try:
            data = self.infile.read(1400)
        except Exception as e:
            traceback.print_exc()
            data = None
        finally:
            return data

    def split_packet(self, message):
        pieces = message.split('|')
        # syn dat fin ack 以及序号
        msg_type, seqno = pieces[0:2]
        checksum = pieces[-1]
        data = '|'.join(pieces[2:-1])
        seqno = int(seqno)
        return msg_type, seqno, data, checksum

    def bufinit(self):
        '''
        滑窗初始化
        '''
        seq = self.next_ack_seq
        for i in range(self.window * 2):
            data = self.fileread()
            if data:
                self.buf.append((seq, data))
                seq += len(data)
                self.next_not_ack_seq = seq
            # 至文件尾部,不追加
            else:
                break

    def movewindow(self):
        '''
        接收方的窗口是1,每收到一个ack,并且该序列是第一次收到的,
        向右移动滑窗,并追加一个文件块
        '''
        self.buf.popleft()
        data = self.fileread()
        seq = self.next_not_ack_seq
        if data:
            # packet = self.make_packet("dat", seq, data)
            self.buf.append((seq, data))
            self.next_not_ack_seq = seq + len(data)

    def make_send_task(self):
        '''
        准备发送任务
        '''
        index = 0
        for i in range(len(self.buf)):
            if self.buf[i][0] == self.next_ack_seq:
                index = i
                break
        # 每次发送,从当前已接受序列的下一个序列开始
        tasks = []
        for j in range(7):
            if index + j < len(self.buf):
                tasks.append(self.buf[index + j])
        return tasks

    def receive_all(self):
        '''
        发送结束后,堵塞的接收数据
        '''
        # 0.5ms限时
        data = self.receive(0.5)
        self.hanlder(data)
        while data:
            data = self.receive(0.5)
            self.hanlder(data)

    def hanlder(self, data):
        '''
        根据接收数据调整最大接收seq,移动滑窗
        '''
        if data:
            # 每次回复当前收到的最大包的下一个包的起始位置
            msg_type, seqno, data, checksum = self.split_packet(data)
            # 如果序号没有接受过,滑动窗口
            print(self.next_ack_seq, seqno, self.recv_record)
            if self.next_ack_seq < seqno:
                self.movewindow()
            currnet_seq = self.next_ack_seq
            self.recv_record[currnet_seq] = self.recv_record.get(
                currnet_seq, 0) + 1
            self.next_ack_seq = seqno

    def start(self):
        '''
        Main sending loop.
        '''
        try:
            print("start connect")
            sequence_num = random.randint(0, 100)
            first_syn_packet = self.make_packet("syn", sequence_num, b"")
            re_syn_times = 3
            # 数据起始序号
            self.next_ack_seq = sequence_num + 1
            # 发送第一个包,重试三次
            print("first syn")
            while re_syn_times > 0:
                print("restart connect", re_syn_times)
                self.send(first_syn_packet)
                first_ack = self.receive(0.5)
                if first_ack:
                    break
                re_syn_times -= 1
            else:
                raise MaxSyntimesError

            print("start send")
            # 缓存初始化
            self.bufinit()
            # 添加最初的7个任务
            send_tasks = [self.buf[i] for i in range(7) if i < len(self.buf)]
            # 数据发送
            while len(self.buf) != 0:
                # 发送所有任务,并将已发送,但未接收的指针前移
                for seq, data in send_tasks:
                    packet = self.make_packet('dat', seq, data)
                    self.send(packet)
                    
                # 接收全部任务,并根据ack移动滑窗
                self.receive_all()
                # 根据ack,返回发送任务,采用后退n协议,返回接收到的最大ack之后的7个包
                send_tasks = self.make_send_task()
            # 连接中断
            fin_packet = self.make_packet("fin", self.next_not_ack_seq, b"")
            re_fin_times = 3
            # 发送最后一个包,重试三次
            while re_fin_times > 0:
                self.send(fin_packet)
                fin_ack = self.receive(0.5)
                if fin_ack:
                    print('ok we will close the connect')
                    break
                re_fin_times -= 1
            else:
                self.sock.close()
                raise MaxSyntimesError
        finally:
            self.sock.close()


def main():
    sender = BasicSender("", 10086, "mytest.txt")
    sender.start()

if __name__ == '__main__':
    main()
