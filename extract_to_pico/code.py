
import time, json, ssl, os
import wifi, usb_hid, socketpool
from adafruit_hid.keycode import Keycode
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_httpserver import Server, Request, Response, POST
import adafruit_requests
import ipaddress

# Hotspot credentials
HOTSPOT_SSID = "your hotspot ssid"
HOTSPOT_PASSWORD = "your hotspot password"

print("Connecting to hotspot:", HOTSPOT_SSID)
wifi.radio.connect(HOTSPOT_SSID, HOTSPOT_PASSWORD)

ip = str(wifi.radio.ipv4_address)
print(" Connected! IP:", ip)

pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, "/", debug=True)
https = adafruit_requests.Session(pool, ssl.create_default_context())

kbd = Keyboard(usb_hid.devices)
layout = KeyboardLayoutUS(kbd)

def type_text(text):
    for ch in text:
        layout.write(ch)
        time.sleep(0.05)

# Show IP in Notepad 
kbd.send(Keycode.GUI, Keycode.R) 
time.sleep(0.5)

layout.write("cmd")
kbd.send(Keycode.ENTER)
time.sleep(1.5) 

layout.write("echo Device IP: " + ip)
kbd.send(Keycode.ENTER)

time.sleep(4.5)

kbd.send(Keycode.ALT, Keycode.F4)

DUCKY_KEYMAP = {
    "F1": Keycode.F1,   "F2": Keycode.F2,   "F3": Keycode.F3,   "F4": Keycode.F4,
    "F5": Keycode.F5,   "F6": Keycode.F6,   "F7": Keycode.F7,   "F8": Keycode.F8,
    "F9": Keycode.F9,   "F10": Keycode.F10, "F11": Keycode.F11, "F12": Keycode.F12,
    "RIGHTARROW": Keycode.RIGHT_ARROW, "LEFTARROW": Keycode.LEFT_ARROW,
    "UPARROW": Keycode.UP_ARROW,       "DOWNARROW": Keycode.DOWN_ARROW,
    "TAB": Keycode.TAB, "ESC": Keycode.ESCAPE, "ESCAPE": Keycode.ESCAPE,
    "SPACE": Keycode.SPACE, "DELETE": Keycode.DELETE, "BACKSPACE": Keycode.BACKSPACE,
}

MOD_NAMES = {"CTRL": Keycode.CONTROL, "ALT": Keycode.ALT, "SHIFT": Keycode.SHIFT, "GUI": Keycode.GUI, "WINDOWS": Keycode.GUI, "WIN": Keycode.GUI}

def press_combo(codes):
    for c in codes:
        kbd.press(c)
    kbd.release_all()

def type_text(s): layout.write(s)

def run_hid_lines(lines):
    for raw in lines:
        line = (raw or "").strip()
        if not line:
            continue
        if line.startswith("REM ") or line.startswith("ATTACKMODE "):
            print("Skipping:", line)
            continue

        if line.startswith("STRING "):
            line = "TYPE " + line[7:]

        print("Executing line:", line)

        if line.startswith("DELAY"):
            parts = line.split()
            if len(parts) == 2 and parts[1].isdigit():
                time.sleep(int(parts[1]) / 1000)
            else:
                print("Bad DELAY:", line)
            continue

        if line.startswith("TYPE "):
            type_text(line.split(" ", 1)[1])
            continue

        if line == "ENTER":
            press_combo([Keycode.ENTER])
            continue

        if line in DUCKY_KEYMAP:
            press_combo([DUCKY_KEYMAP[line]])
            continue

        up = line.replace("-", " ").upper().split()
        if any(tok in MOD_NAMES for tok in up):
            mods = [MOD_NAMES[tok] for tok in up if tok in MOD_NAMES]
            rest = [tok for tok in up if tok not in MOD_NAMES]
            if len(rest) == 1:
                keytok = rest[0]
                if len(keytok) == 1 and keytok.isalpha():
                    press_combo(mods + [getattr(Keycode, keytok.upper())])
                elif keytok in DUCKY_KEYMAP:
                    press_combo(mods + [DUCKY_KEYMAP[keytok]])
                else:
                    print("Unknown key in combo:", line)
            else:
                print("Bad combo:", line)
            continue

        print("Unknown command:", line)


def send_json(request: Request, obj: dict):
    try:
        body = json.dumps(obj)
    except Exception as e:
        body = json.dumps({"error": "json_encode_failed", "detail": repr(e)})
    return Response(request, body=body, headers={"Content-Type": "application/json"})

def serve_index(request):
    with open("index.html", "r") as f:
        html = f.read()
    return Response(request, body=html, headers={"Content-Type": "text/html"})

@server.route("/")
def base(request: Request):
    return serve_index(request)

@server.route("/execute", POST, append_slash=True)
def execute(request: Request):
    try:
        data = request.json() or {}
        payload = data.get("content", "")
        if isinstance(payload, str):
            lines = [ln.rstrip("\r") for ln in payload.splitlines()]
            run_hid_lines(lines)
            return send_json(request, {"message": "Executed", "lines": len(lines)})
        else:
            return send_json(request, {"error": "Invalid payload: expected string"})
    except Exception as e:
        print("Execute error:", repr(e))
        return send_json(request, {"error": "execute_failed", "detail": repr(e)})

@server.route("/payloads")
def list_payloads(request: Request):
    files = []
    try:
        for fname in os.listdir("/"):
            if fname.lower().endswith(".dd"):
                try:
                    with open("/" + fname, "r") as f:
                        content = f.read()
                    files.append({"name": fname, "content": content})
                except Exception as fe:
                    files.append({"name": fname, "error": repr(fe)})
    except Exception as e:
        return send_json(request, {"error": "list_failed", "detail": repr(e)})
    return send_json(request, {"payloads": files})



try:
    server.serve_forever(str(wifi.radio.ipv4_address), 80)
except KeyboardInterrupt:
    print("Server stopped by user!")
