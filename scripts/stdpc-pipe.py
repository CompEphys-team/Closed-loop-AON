import time
import sys
import win32pipe, win32file, pywintypes
import struct


def pipe_server():
    print("pipe server")
    count = 0
    pipe = win32pipe.CreateNamedPipe(
        r'\\.\pipe\Foo',
        win32pipe.PIPE_ACCESS_DUPLEX,
        win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
        1, 65536, 65536,
        0,
        None)
    try:
        print("waiting for client")
        win32pipe.ConnectNamedPipe(pipe, None)
        print("got client")

        while count < 10:
            print(f"writing message {count}")
            # convert to bytes
            some_data = str.encode(f"{count}")
            win32file.WriteFile(pipe, some_data)
            time.sleep(1)
            count += 1

        print("finished now")
    finally:
        win32file.CloseHandle(pipe)


def pipe_client():
    print("pipe client")
    quit = False

    while not quit:
        try:
            handle = win32file.CreateFile(
                r'\\.\pipe\Foo',
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None
            )
            res = win32pipe.SetNamedPipeHandleState(handle, win32pipe.PIPE_READMODE_MESSAGE, None, None)
            if res == 0:
                print(f"SetNamedPipeHandleState return code: {res}")
            while True:
                resp = win32file.ReadFile(handle, 64*1024)
                print(f"message: {resp}")
        except pywintypes.error as e:
            if e.args[0] == 2:
                print("no pipe, trying again in a sec")
                time.sleep(1)
            elif e.args[0] == 109:
                print("broken pipe, bye bye")
                quit = True


def pipe_write(server):
    pipename = sys.argv[2]
    print(f"pipe write on \\\\.\\pipe\\{pipename}")
    quit = False

    while not quit:
        handle = get_pipe_server(pipename, False) if server else get_pipe_client(pipename, False)
        count = -100
        try:
            while True:
                sample = struct.pack("@d", 0.01 * (count%200) * (1 if count%2 else -1))
                win32file.WriteFile(handle, sample)
                time.sleep(0.01)
                count += 1
            win32file.CloseHandle(handle)
            print("Write complete")
        except pywintypes.error as e:
            print(f"Something went wrong, error {e.args[0]}")
            time.sleep(1)


def pipe_read(server):
    pipename = sys.argv[2]
    print(f"pipe read on \\\\.\\pipe\\{pipename}")
    quit = False

    while not quit:
        handle = get_pipe_server(pipename, True) if server else get_pipe_client(pipename, True)
        try:
            while True:
                res, buffer = win32file.ReadFile(handle, 8)
                sample = struct.unpack("@d", buffer)[0]
                print(sample)
        except pywintypes.error as e:
            print(f"Something went wrong, error {e.args[0]}")
            time.sleep(1)

def get_pipe_server(pipename, read):
    pipe = win32pipe.CreateNamedPipe(
        f'\\\\.\\pipe\\{pipename}',
        win32pipe.PIPE_ACCESS_INBOUND if read else win32pipe.PIPE_ACCESS_OUTBOUND,
        win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
        1, 65536, 65536,
        0,
        None)
    print(f"waiting for client on {pipename}")
    while True:
        try:
            win32pipe.ConnectNamedPipe(pipe, None)
        except pywintypes.error as e:
            print(f"Something went wrong, error {e.args[0]}")
            time.sleep(1)
            continue
        print("got client")
        return pipe

def get_pipe_client(pipename, read):
    print(f"open handle to {pipename}")
    while True:
        try:
            handle = win32file.CreateFile(
                f'\\\\.\\pipe\\{pipename}',
                win32file.GENERIC_READ if read else win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None
            )
        except pywintypes.error as e:
            print(f"Something went wrong, error {e.args[0]}")
            time.sleep(1)
            continue
        print(f"opened pipe {pipename}")
        return handle


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("need s or c as argument")
    elif sys.argv[1] == "s":
        pipe_server()
    elif sys.argv[1] == "c":
        pipe_client()
    elif sys.argv[1] == "ww":
        pipe_write(True)
    elif sys.argv[1] == "rr":
        pipe_read(True)
    elif sys.argv[1] == "w":
        pipe_write(False)
    elif sys.argv[1] == "r":
        pipe_read(False)
    else:
        print(f"no can do: {sys.argv[1]}")
