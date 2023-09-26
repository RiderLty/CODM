import os
import threading
from io import BytesIO
from os.path import join
from time import sleep

import aircv as ac
import numpy as np
import requests
from bottle import *
from PIL import Image, ImageDraw

from utils.adbInterface import (adbInterface, noExtendDisplayRootedInterface,
                                rootedDeviceInterface)

def merge_dicts(*args):
    result = {}
    for dictionary in args:
        result.update(dictionary)
    return result


def aircvMatchRemote(target, templates, threshold):
    api = "http://192.168.1.223:9010/api/aircv"
    targetBase64 = base64.b64encode(target).decode()
    data = {"target": targetBase64,
            "templates": [base64.b64encode(x).decode() for x in templates], "threshold": threshold}
    r = requests.post(api, json=data)
    return r.json()


def matchInterface(target: bytes, templates: list, threshold: float):
    # return aircvMatchRemote(target, templates, threshold)
    targetImgArr = np.array(Image.open(BytesIO(target)), dtype=np.uint8)
    result = []
    for templateBytes in templates:
        templateImgArr = np.array(Image.open(
            BytesIO(templateBytes)), dtype=np.uint8)
        match_result = ac.find_template(
            targetImgArr, templateImgArr, threshold)
        result.append(match_result)
        if match_result != None:
            break
    for __ in range(len(templates) - len(result)):
        result.append(None)
    return result


frame = b''


def showResult(target, results):
    global frame
    base = Image.open(BytesIO(target))
    img = Image.fromarray(np.uint8(base))
    draw = ImageDraw.Draw(img)
    for result in results:
        if result != None:
            for i in range(4):
                for j in range(i, 4):
                    x1 = int(result['rectangle'][i][0])
                    y1 = int(result['rectangle'][i][1])
                    x2 = int(result['rectangle'][j][0])
                    y2 = int(result['rectangle'][j][1])
                    draw.line((x1, y1, x2, y2), width=3,  fill=(255, 0, 0))
    btio = BytesIO()
    img.save(btio, format='PNG')
    frame = btio.getvalue()


def scaleWithFixHeight(bytes, height):
    # width = int(img.size[0] * height / img.size[1])
    # return img.resize((width, height))
    img = Image.open(BytesIO(bytes))
    if height == img.size[1]:
        return bytes
    width = int(img.size[0] * height / img.size[1])
    result = img.resize((width, height))
    btio = BytesIO()
    result.save(btio, format='PNG')
    return btio.getvalue()

def deScaleXY(originHeight, scaledHeight, x, y):
    return int(x * scaledHeight / originHeight), int(y * scaledHeight / originHeight)

class controller:
    def __init__(self, interface: adbInterface) -> None:
        self.device = interface
        self.actions = []
        self.running = True

    def bindAction(self, img: str, function: lambda x, y, device: None):
        '''
        img: path to image
        function( x,y,adbInterfaceInstance) -> None : function to be called when image is found
        >>>=============================================================

        事件按照顺序绑定
        检测到第一个适配后 就会终止后面的
        '''
        self.actions.append((open(img, 'rb').read(), function))
        return self

    def mainLoop(self):
        while self.running:
            try:
                target = scaleWithFixHeight(self.device.screenCap(), 720)
                height = Image.open(BytesIO(target)).size[1]
                results = matchInterface(
                    target, [x[0] for x in self.actions], 0.75)
                showResult(target, results)
                for i in range(len(results)):
                    if results[i] != None:
                        print(results[i])
                        __x = int(results[i]['result'][0])
                        __y = int(results[i]['result'][1])
                        x, y = deScaleXY(720, height, __x, __y)
                        self.actions[i][1](x, y, self.device)
            except Exception as e:
                print(e)
                #如果是键盘中断
                if e.args[0] == 'KeyboardInterrupt':
                    self.stop() 
            


    def start(self):
        thread = threading.Thread(target=self.mainLoop)
        thread.start()
        return thread

    def stop(self):
        self.running = False


@route('/api/img')
def returnImg():
    response.set_header('Content-Type', 'image/jpeg')
    return frame

@route('/api/click')
def click():
    payload = merge_dicts(dict(request.forms), dict(request.query.decode()))
    print(payload)
    device.tap(int(payload["x"]),int(payload["y"]))
    time.sleep(0.3)    
    target = scaleWithFixHeight(device.screenCap(), 720)
    showResult(target, [])
    return 



@route('/')
def index():
    return '''<body>
                <img src="/api/img" id="img" style=""    />
            </body>
            <script>
                var oImg = document.getElementById('img');
                var timer = null;
                timer = setInterval(function(){
                    oImg.src = '/api/img'+'?t='+ Math.random();
                },1000);
                const imgClick = (e) => {
                    fetch(`/api/click?x=${e.clientX}&y=${e.clientY}`).then( (_) => {
                        oImg.src = '/api/img'+'?t='+ Math.random()
                    })
                }
                document.querySelector("#img").addEventListener("click",imgClick)
            </script>'''


device = None

if __name__ == "__main__":
    # os.system("adb kill-server")
    # os.system("setprop service.adb.tcp.port 5555")
    # os.system("stop adbd")
    # os.system("start adbd")
    # os.system("adb connect 192.168.3.200")
 
    device = adbInterface(  )
    # device = rootedDeviceInterface()
    # device = noExtendDisplayRootedInterface()

    displays = device.listDisplays()
    print("current displays:", displays)

    device.setDefaultDisplay(displays[-1])
    print("set default display:", displays[-1])

    # device.setScreenSize(720, 1280)
    # device.setScreenDensity(300)


    device.launchApp( "com.tencent.tmgp.cod/com.tencent.tmgp.cod.CODMainActivity",)
    
    
    currentStack = device.listStack()
    
    
    
    if currentStack['com.tencent.tmgp.cod']['displayID'] != displays[-1]:
        device.moveStack(
            currentStack['com.tencent.tmgp.cod']['stackID'], displays[-1])

    def keepCODMalive():
        while True:
            sleep(15)
            device.launchApp(
                "com.tencent.tmgp.cod/com.tencent.tmgp.cod.CODMainActivity")

    threading.Thread(target=keepCODMalive).start()
    controllerInstance = controller(device)
    rootPath = os.path.dirname(os.path.abspath(__file__))
    for file in sorted(os.listdir(join(rootPath, 'click_type')), key=lambda x: x.split('.')[0]):
        imgPath = join(join(rootPath, 'click_type'), file)
        print(imgPath, "bind click")
        controllerInstance.bindAction(
            imgPath, lambda x, y, device: device.tap(x, y))

    def runForwardAndBackward(__x, __y, device):
        device.swipe(200, 500, 200, 280, 800)
        sleep(1)
        device.swipe(200, 500, 200, 720, 800)
        sleep(5)

    def inGhost(__x, __y, device):
        print("in ghost not move")
        sleep(5)

    def died(__x, __y, device):
        print("died")
        sleep(5)

    controllerInstance.bindAction(
        join(join(rootPath, 'stause_type'), "reloading.jpg"), runForwardAndBackward)
    controllerInstance.bindAction(
        join(join(rootPath, 'stause_type'), "lock.jpg"), inGhost)
    controllerInstance.bindAction(
        join(join(rootPath, 'stause_type'), "died.jpg"), died)

    threading.Thread(target=run, kwargs={"host": "0.0.0.0", "port": 9015}).start()
    controllerInstance.start().join()
