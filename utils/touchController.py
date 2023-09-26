import os
import struct
import threading

DOWN = 0x1
UP = 0x0
MOVE_FLAG = 0x0
RELEASE_FLAG = 0x2
REQURIE_FLAG = 0x1
WHEEL_REQUIRE = 0x3
MOUSE_REQUIRE = 0x4

ABS_MT_POSITION_X = 0x35
ABS_MT_POSITION_Y = 0x36
ABS_MT_SLOT = 0x2F
ABS_MT_TRACKING_ID = 0x39
EV_SYN = 0x00
EV_KEY = 0x01
EV_REL = 0x02
EV_ABS = 0x03
REL_X = 0x00
REL_Y = 0x01
REL_WHEEL = 0x08
REL_HWHEEL = 0x06
SYN_REPORT = 0x00
BTN_TOUCH = 0x14A
EVENT_FORMAT = "llHHI"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

def eventPacker(e_type, e_code, e_value): return struct.pack(
    EVENT_FORMAT, 0, 0, e_type, e_code, e_value
)

SYN_EVENT = eventPacker(EV_SYN, SYN_REPORT, 0x0)



def atomWarpper(func):
    lock = threading.Lock()

    def f(*args, **kwargs):
        lock.acquire()
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            raise e
        finally:
            lock.release()
        return result
    return f
    
class touchController:
    def __init__(self, path) -> None:
        self.path = path
        self.fd = os.open(self.path, os.O_RDWR)
        self.last_touch_id = -1
        self.allocatedID_num = 0
        self.touch_id_list = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        self.mouse_id = 0

    def __del__(self):
        os.close(self.fd)

    # 锁！！！！
    @atomWarpper
    def postEvent(self, type, uncertainId, x, y):
        trueId = uncertainId
        bytes = b''
        if type == MOVE_FLAG and uncertainId != -1:
            if self.last_touch_id != uncertainId:
                bytes += eventPacker(EV_ABS, ABS_MT_SLOT, uncertainId)
                self.last_touch_id = uncertainId
            bytes += eventPacker(EV_ABS, ABS_MT_POSITION_X, x & 0xFFFFFFFF)
            bytes += eventPacker(EV_ABS, ABS_MT_POSITION_Y, y & 0xFFFFFFFF)
            bytes += SYN_EVENT
            os.write(self.fd, bytes)

        elif type == RELEASE_FLAG and uncertainId != -1:
            trueId = -1
            self.touch_id_list[uncertainId] = 0
            self.allocatedID_num -= 1
            if self.last_touch_id != uncertainId:
                bytes += eventPacker(EV_ABS, ABS_MT_SLOT, uncertainId)
                self.last_touch_id = uncertainId
            bytes += eventPacker(EV_ABS, ABS_MT_TRACKING_ID, 0xFFFFFFFF)
            if self.allocatedID_num == 0:
                bytes += eventPacker(EV_KEY, BTN_TOUCH, UP)
            bytes += SYN_EVENT
            os.write(self.fd, bytes)

        else:
            if type == MOUSE_REQUIRE:
                self.mouse_id = 1 if self.mouse_id == 0 else 0
                trueId = self.mouse_id
            elif type == WHEEL_REQUIRE:
                trueId = 2
            elif type == REQURIE_FLAG:
                for i in range(3, 10):
                    if self.touch_id_list[i] == 0:
                        trueId = i
                        break
            if trueId == -1:
                # 没有空余的触摸点
                return -1
            self.touch_id_list[trueId] = 1
            self.allocatedID_num += 1
            self.last_touch_id = trueId
            bytes += eventPacker(EV_ABS, ABS_MT_SLOT, trueId)
            bytes += eventPacker(EV_ABS, ABS_MT_TRACKING_ID, trueId)
            bytes += eventPacker(EV_KEY, BTN_TOUCH,  DOWN) if self.allocatedID_num == 1 else b''
            bytes += eventPacker(EV_ABS, ABS_MT_POSITION_X, x & 0xFFFFFFFF)
            bytes += eventPacker(EV_ABS, ABS_MT_POSITION_Y, y & 0xFFFFFFFF)
            bytes += SYN_EVENT
            os.write(self.fd, bytes)

        return trueId


