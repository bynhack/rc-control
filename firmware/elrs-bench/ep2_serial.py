#!/usr/bin/env python3
"""Switch the EP2 between CRSF serial and its earlier PWM setup, over its WiFi at 10.0.0.1.

  python3 ep2_serial.py          remove pwm_outputs (saves a backup first)
  python3 ep2_serial.py restore  put the backup back
"""
import json, os, sys, urllib.request

BASE = "http://10.0.0.1"
BACKUP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ep2_hardware_backup.json")


def post(path, data=b""):
    req = urllib.request.Request(BASE + path, data=data, method="POST", headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=8).read().decode()


def get():
    return json.load(urllib.request.urlopen(BASE + "/hardware.json", timeout=8))


if len(sys.argv) > 1 and sys.argv[1] == "restore":
    hw = json.load(open(BACKUP))
else:
    hw = get()
    if not os.path.exists(BACKUP):
        json.dump(hw, open(BACKUP, "w"))
        print("backup:", BACKUP)
    hw.pop("pwm_outputs", None)
print(post("/hardware.json", json.dumps(hw, separators=(",", ":")).encode()))
print("now:", json.dumps(get()))
try:
    post("/reboot")
except Exception:
    pass  # it reboots before answering
print("rebooting")
