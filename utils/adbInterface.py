import os
import re
import subprocess
from time import sleep, time

from utils.touchController import *

class adbInterface:
    def __init__(self, device="", displayID=0) -> None:
        self.device = device
        self.displayID = displayID
        self.ADB = f"adb -s {self.device} " if device != "" else "adb "
        self.COMMAND_HEAD = self.ADB + "shell "  # 空格很重要

    def screenCap(self,) -> bytes:
        start = time()
        cmd = f"{self.COMMAND_HEAD}screencap  -d {self.displayID}   -p"
        # cmd = f"{self.COMMAND_HEAD}screencap -p"
        print(cmd)
        pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        #windows or linux
        image_bytes = None
        if os.name == "nt":  # windows
            image_bytes = pipe.stdout.read().replace(b'\r\n', b'\n')
        else:
            image_bytes = pipe.stdout.read()
        pipe.stdout.close()
        
        mbSize = len(image_bytes) / 1024 / 1024
        timeUse = time() - start
        #保留两位小数
        print(f"screencap {mbSize:.2f}MB  use {timeUse:.2f}s" )
        return image_bytes

    def tap(self, x, y, displayID=False):
        cmd = f"{self.COMMAND_HEAD}input -d {displayID or self.displayID} tap {x} {y}"
        print(cmd)
        os.system(cmd)

    def swipe(self, x1, y1, x2, y2, time, displayID=False):
        cmd = f"{self.COMMAND_HEAD}input -d {displayID or self.displayID} swipe {x1} {y1} {x2} {y2} {time}"
        print(cmd)
        os.system(cmd)

    def listStack(self):
        cmd = f"{self.COMMAND_HEAD}am stack list"
        output = subprocess.check_output(cmd, shell=True).replace( b'\r\n', b'\n').decode("utf-8")
        print(output)
        stackIDs = re.findall(r"id=\d+ bounds=[^d]+displayId=\d+ userId=\d+", output)
        indexes = [ output.find(x) for x in stackIDs]
        print(indexes)
        splitOutput = [output[indexes[i]:indexes[i+1]] for i in range(len(indexes)-1)] + [output[indexes[-1]:]]
        result = {}
        for i in range(len(splitOutput)):
            stackID = re.findall(r"id=(\d+)",stackIDs[i])[0]
            displayID = re.findall(r"displayId=(\d+)",stackIDs[i])[0]
            activity = [x.split(" ")[1] for x in re.findall(r"taskId=\d+: [^ ]+ ", splitOutput[i])]
            for j in range(len(activity)):
                packageName = activity[j].split("/")[0]
                result[packageName] = {
                    "stackID": int(stackID),
                    "displayID": int(displayID),
                }
        print(result)   
        return result

    def moveStack(self, stackID, displayID):
        cmd = f"{self.COMMAND_HEAD}am display move-stack {stackID} {displayID}"
        os.system(cmd)

    def launchApp(self, FullActivity, displayID=False):
        cmd = f"{self.COMMAND_HEAD}am start -n {FullActivity} --display {displayID or self.displayID}"
        os.system(cmd)

    def killApp(self, packageName):
        cmd = f"{self.COMMAND_HEAD}am force-stop {packageName}"
        os.system(cmd)

    def listDisplays(self):
        cmd = f"{self.COMMAND_HEAD}dumpsys display"
        output = subprocess.check_output(cmd, shell=True).replace(
            b'\r\n', b'\n').decode("utf-8")
        return [int(x) for x in re.findall(r"mDisplayId=(\d+)", output)]

    def setDefaultDisplay(self, displayID):
        self.displayID = displayID

    def setScreenSize(self, width, height, displayID=False):
        cmd = f"{self.COMMAND_HEAD}wm size  {width}x{height} -d {displayID or self.displayID}"
        os.system(cmd)

    def setScreenDensity(self, density, displayID=False):
        cmd = f"{self.COMMAND_HEAD}wm density {density} -d { displayID or  self.displayID}"
        os.system(cmd)

    def resetScreen(self, displayID=False):
        os.system(
            f"{self.COMMAND_HEAD}wm size  reset  -d { displayID or self.displayID}")
        os.system(
            f"{self.COMMAND_HEAD}wm density reset -d { displayID or self.displayID}")

class rootedDeviceInterface(adbInterface):
    # root设备 直接执行 但是貌似无法使用input命令
    def __init__(self, device="", displayID=0) -> None:
        super().__init__(device, displayID)
        self.COMMAND_HEAD = "/system/bin/"

class noExtendDisplayRootedInterface(rootedDeviceInterface):
    # 检测方向并使用sendevent模拟触摸
    # 不支持额外的屏幕
    def __init__(self, device="", displayID=0, touchPath="/dev/input/event5", screenSize=(1440, 3120)) -> None:
        super().__init__(device, displayID)
        self.touchPath = touchPath
        self.screenSize = screenSize

    def detectOrientation(self):
        # 0 竖屏 1 左侧向下 3 右侧向下
        cmd = f"{self.COMMAND_HEAD}dumpsys input | grep 'SurfaceOrientation' | awk '{{print $2}}'"
        output = subprocess.check_output(cmd, shell=True).decode("utf-8")
        return int(output)

    def translateXY(self, x, y):
        orientation = self.detectOrientation()
        # print(f"orientation={orientation} , ({x},{y}) => ",end="")
        if orientation == 0:
            # print(f"({x},{y})")
            return x, y
        elif orientation == 1:
            # print(f"({self.screenSize[0]-y},{x})")
            return self.screenSize[0] - y, x
        elif orientation == 3:
            # print(f"({y},{self.screenSize[1]-x})")
            return y, self.screenSize[1] - x
        else:
            return x, y

    def tap(self, __x, __y, displayID=False):
        tc = touchController(self.touchPath)
        x, y = self.translateXY(__x, __y)
        tid = tc.postEvent(REQURIE_FLAG, -1, x, y)
        sleep(1 / 60)  # 按下一帧
        tc.postEvent(RELEASE_FLAG, tid, -1, -1)

    def swipe(self, x1, y1, x2, y2, time, displayID=False):
        self.drag([(x1, y1), (x2, y2)], time, displayID)

    def drag(self, keyPoints, interval, displayID=False):
        tc = touchController(self.touchPath)
        startX, startY = self.translateXY(keyPoints[0][0], keyPoints[0][1])
        tid = tc.postEvent(REQURIE_FLAG, -1, startX, startY)
        sleep(interval / 1000)
        for (__x, __y) in keyPoints[1:]:
            x, y = self.translateXY(__x, __y)
            tc.postEvent(MOVE_FLAG, tid, x, y)
            sleep(interval / 1000)
        # 消除惯性
        tc.postEvent(RELEASE_FLAG, tid, -1, -1)


if __name__ == "__main__":
    # onePlus7pro = adbInterface("", 2)
    # open("p:/1.png","wb").write(onePlus7pro.screenCap())
    # onePlus7pro.tap(500,500)
    # onePlus7pro.swipe(500,500,1000,500,500)
    # print(onePlus7pro.listStack())
    # onePlus7pro.launchApp("com.tencent.tmgp.cod/com.tencent.tmgp.cod.CODMainActivity", 2)
    # print(onePlus7pro.listDisplays())
    onePlus7pro = noExtendDisplayRootedInterface()
    onePlus7pro.tap(500, 500)
