import hashlib
import time


def make_sign(device_sn: str, key_id: str, fixed_key: str, mystic_time: str) -> str:
    sign_raw = f"deviceSn={device_sn}&keyid={key_id}&mysticTime={mystic_time}&key={fixed_key}"
    return hashlib.md5(sign_raw.encode()).hexdigest()


def common_params(device_sn: str, key_id: str, fixed_key: str) -> dict:
    mystic_time = str(int(time.time() * 1000))
    return {
        "deviceSn": device_sn,
        "keyid": key_id,
        "mysticTime": mystic_time,
        "sign": make_sign(device_sn, key_id, fixed_key, mystic_time),
        "pointParam": "deviceSn,keyid,mysticTime",
        "product": "dictpen",
        "client": "y09",
        "appVersion": "4.13.1",
        "osAppVersion": "2.13.0",
        "mid": "Linux5.10.160",
        "screen": "640x172",
        "model": "YDPA7-1",
        "imei": device_sn,
        "deviceSku": "OVERHEAD_Y09_SKU_CHN_PRO",
        "deviceId": device_sn,
    }
