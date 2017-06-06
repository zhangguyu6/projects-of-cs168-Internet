import socket
import Checksum
import traceback
'''
文件接收客户端
'''


class Receiver:
    def __init__(self, dest, port, filename):
        self.address = (dest, int(port))
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(self.address)
        self.file = open(filename, 'wb')
        self.current_seq = 0
        self.except_seq = 0

    # 读取回复,堵塞
    def receive(self, timeout=None):
        self.socket.settimeout(timeout)
        try:
            data, addr = self.socket.recvfrom(4096)
            self.remoteaddr = addr
            return data
        except (socket.timeout, socket.error):
            return None

    # 拼包
    def make_packet(self, msg_type, seqno, msg):
        # syn|<sequence number>||<checksum>
        # dat|<sequence number>|<data>|<checksum>
        # fin|<sequence number>|<data>|<checksum>
        # ack|<sequence number>|<checksum>
        body = b"%b|%d|%b|" % (msg_type, seqno, msg)
        checksum = Checksum.generate_checksum(body)
        packet = body + checksum
        return packet

    # 发送
    def send(self, message, address=None):
        if address is None:
            address = self.remoteaddr
        self.socket.sendto(message, address)

    def split_packet(self, message):
        pieces = message.split(b'|')
        # syn dat fin ack 以及序号
        msg_type, seqno = pieces[0:2]
        checksum = pieces[-1]
        data = b'|'.join(pieces[2:-1])
        seqno = int(seqno)
        return msg_type, seqno, data, checksum

    def handler_syn(self, *data):
        seqno, data, checksum = data
        self.current_seq = seqno
        self.except_seq = seqno + 1

    def handler_ack(self, *data):
        seqno, data, checksum, message = data
        if Checksum.validate_checksum(message) and seqno == self.except_seq:
            self.current_seq = seqno
            self.except_seq = seqno + len(data)
            self.file.write(data)

    def handler_fin(self, *data):
        seqno, data, checksum = data
        self.current_seq = seqno
        self.except_seq = seqno + len(data)
        self.file.close()
        packet = self.make_packet(b'ack', self.except_seq, b"")
        print("send:", packet)
        self.send(packet)

    def start(self):
        print("start listen on {}".format(self.address))
        try:
            while True:
                message = self.receive(0.5)
                print("receive:", message)
                if message:
                    msg_type, seqno, data, checksum = self.split_packet(
                        message)
                    if msg_type == b'syn':
                        self.handler_syn(seqno, data, checksum)
                    elif msg_type == b"dat":
                        self.handler_ack(seqno, data, checksum, message)
                    else:
                        self.handler_fin(seqno, data, checksum)
                        break
                    packet = self.make_packet(b'ack', self.except_seq, b"")
                    print("send:", packet)
                    self.send(packet)
        except Exception as e:
            print(e)
            traceback.print_exc()
        finally:
            print("close socket")
            self.socket.close()


def main():
    server = Receiver("", 10086, "mytest1.txt")
    server.start()
if __name__ == '__main__':
    main()
