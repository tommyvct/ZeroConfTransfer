import os
import random
import sys
import re
from zeroconf import ServiceBrowser, Zeroconf, ServiceInfo
import socket
import hashlib
import tqdm
import psutil

NODE_PORT = 23333
CHUNKS_SIZE = 2048
SERVICE_TYPE_NAME = "_ishare._udp.local."


def get_ip_list(hint: str = "") -> tuple:
    ip_list = {}

    counter = 0
    for interface, ip in psutil.net_if_addrs().copy().items():
        temp = []

        for a in ip:
            # https://www.oreilly.com/library/view/regular-expressions-cookbook/9780596802837/ch07s16.html
            if re.search("^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$", a.address) and a.address != "127.0.0.1":
                if hint == "":
                    temp.append(a.address)
                    counter += 1
                else:
                    if hint in a.address:
                        temp.append(a.address)
                        counter += 1

        if not len(temp) == 0:
            ip_list[interface] = temp

    return ip_list, counter


def get_ip() -> str:
    default_ip = socket.gethostbyname(socket.gethostname())
    if "192.168" in default_ip:
        return default_ip
    ip_list, counter = get_ip_list(hint="192.168")

    ret: str = ""
    if counter != 1:
        while ret == "":
            ip_list, counter = get_ip_list()
            if counter == 0:
                print("No usable IP address.\n Abort.")
                exit(3)
            elif counter == 1:
                for a in ip_list:
                    return ip_list[a][0]
            for interface, ip_addrs in ip_list.copy().items():
                print(interface + ": " + str(ip_addrs))
            s = input("Choose an IP address from above to send the file:")
            for a in ip_list:
                if s in ip_list[a]:
                    ret = s
                    break
            if ret == "":
                print("Invalid IP address.")
    else:
        for a in ip_list:
            return ip_list[a][0]

    return ret


def prep_zeroconf_connection_code(ip: str) -> tuple:
    connection_code = str(random.randint(999, 9999))

    si = ServiceInfo(
        SERVICE_TYPE_NAME,
        connection_code + "@." + SERVICE_TYPE_NAME,
        addresses=[socket.inet_aton(ip)],
        port=NODE_PORT,
    )
    z = Zeroconf()
    z.register_service(si)

    return connection_code, si, z


# from https://stackoverflow.com/questions/3431825/generating-an-md5-checksum-of-a-file
def md5(filename: str) -> str:
    hash_md5 = hashlib.md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def select_node() -> tuple:
    node_list = {}

    class ZeroconfListener:
        def remove_service(self, zeroconf, type, name):
            del node_list[name.split('@', 1)[0]]

        def add_service(self, zeroconf, type, name):
            # name would be like "6666@name._ishare._udp.local."
            service_info = zeroconf.get_service_info(type, name)
            node_list[name.split('@', 1)[0]] = (socket.inet_ntoa(service_info.addresses[0]), service_info.port)

    z = Zeroconf()
    _ = ServiceBrowser(z, SERVICE_TYPE_NAME, ZeroconfListener())
    while True:
        try:
            connection_code = int(input("enter connection code: "))
            if connection_code < 10000:
                z.close()
                return node_list[str(connection_code)]
        except ValueError:
            print("invalid code.")
        except KeyError:
            print("invalid code.")


def recv_ensure_from(s: socket, ip_port_tuple: tuple, chunk_sz: int) -> bytes:
    addr: tuple = ()
    while addr != ip_port_tuple:
        data, addr = s.recvfrom(chunk_sz)
        return data


def receive() -> None:
    ip_tuple = select_node()

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", 23333))
        s.sendto(b"Hi", ip_tuple)  # notify server to send the file

        filename = os.path.join(os.getcwd(), recv_ensure_from(s, ip_tuple, CHUNKS_SIZE).decode("UTF-8"))

        if filename == os.path.join(os.getcwd(), "**stdin**"):
            while True:
                data = recv_ensure_from(s, ip_tuple, CHUNKS_SIZE)
                sys.stdout.buffer.write(data)
                if len(data) < CHUNKS_SIZE:
                    return
        print("Receiving: \"" + filename + "\"")
        try:
            filesize = int(recv_ensure_from(s, ip_tuple, CHUNKS_SIZE).decode("UTF-8"))
            filehash = recv_ensure_from(s, ip_tuple, CHUNKS_SIZE).decode("UTF-8")

            with open(filename, "wb") as f:
                received_chunks = 0
                with tqdm.tqdm(-(-filesize // CHUNKS_SIZE)) as progressbar:  # ceiling division
                    progressbar.update(0)

                    while True:
                        data = recv_ensure_from(s, ip_tuple, CHUNKS_SIZE)
                        f.write(data)

                        received_chunks += 1
                        progressbar.update(received_chunks)

                        if len(data) < CHUNKS_SIZE:
                            break
        except ValueError:
            print("Bad request.\nAbort.")
            exit(2)
        except KeyboardInterrupt:
            print("Abort.")
            exit(4)

        received_filehash = md5(filename)
        if not filehash == received_filehash:
            print("Warning: File MD5 checksum don't match. Use with caution.")
            print(filehash + " != " + received_filehash)


try:
    # if something passed from stdin, send it out
    if not sys.stdin.isatty():
        ip = get_ip()
        connection_code, si, z = prep_zeroconf_connection_code(ip)
        print("Connection code: " + connection_code)

        addr: tuple = ()

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind((ip, NODE_PORT))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            data: bytes = b''

            while data != b'Hi':
                data, addr = s.recvfrom(10)

            s.sendto(b"**stdin**", addr)
            while True:
                temp = sys.stdin.buffer.read(CHUNKS_SIZE)
                s.sendto(temp, addr)
                if len(temp) < CHUNKS_SIZE:
                    break

        z.unregister_service(si)
        print("Done.")

    elif len(sys.argv) == 1:
        receive()
        print("Done.")

    else:
        ip = get_ip()
        connection_code, si, z = prep_zeroconf_connection_code(ip)
        print("Connection code: " + connection_code)

        addr: tuple = ()

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind((ip, NODE_PORT))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            data: bytes = b''

            while data != b'Hi':
                data, addr = s.recvfrom(10)

            try:
                s.sendto(bytes(sys.argv[1], encoding="UTF-8"), addr)
                s.sendto(bytes(str(os.path.getsize(sys.argv[1])), encoding="UTF-8"), addr)
                s.sendto(bytes(md5(sys.argv[1]), encoding="UTF-8"), addr)

                with open(sys.argv[1], "rb") as file:
                    while True:
                        data = file.read(CHUNKS_SIZE)
                        s.sendto(data, addr)
                        if len(data) < CHUNKS_SIZE:
                            break
            except OSError:
                print("Cannot open file " + sys.argv[1])
                exit(1)

        print("Done.")
except KeyboardInterrupt:
    pass
# filename
# file size
# md5hash
# ...file_content...


# https://stackoverflow.com/questions/1118028/file-containing-its-own-checksum
# A file's MD5 hash are less likely to be contained in that file

# https://stackoverflow.com/questions/13993514/sending-receiving-file-udp-in-python
