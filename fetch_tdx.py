#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TDX 全台即時路況資料抓取與中繼處理模組
由 GitHub Actions 自動排程定期執行，將高公局與公路局真實 VD 數據彙整為輕量 traffic_live.json
"""

import json
import os
import re
import sys
import time
import requests

TDX_CLIENT_ID = os.environ.get("TDX_CLIENT_ID", "cv1706yang-8ba9e89a-7819-43c6")
TDX_CLIENT_SECRET = os.environ.get("TDX_CLIENT_SECRET", "4ba7c5d3-e9aa-4687-981a-51f5361e8e81")

TOKEN_URL = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
VD_FREEWAY_URL = "https://tdx.transportdata.tw/api/basic/v2/Road/Traffic/Live/VD/Freeway?$format=JSON"
VD_HIGHWAY_URL = "https://tdx.transportdata.tw/api/basic/v2/Road/Traffic/Live/VD/Highway?$format=JSON"

def get_token():
    payload = {
        "grant_type": "client_credentials",
        "client_id": TDX_CLIENT_ID,
        "client_secret": TDX_CLIENT_SECRET
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "TaiwanTrafficLive/1.0"
    }
    res = requests.post(TOKEN_URL, data=payload, headers=headers, timeout=15)
    if res.status_code == 200:
        return res.json().get("access_token")
    return None

def fetch_data(token, url):
    if not token:
        return None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "TaiwanTrafficLive/1.0"
    }
    try:
        res = requests.get(url, headers=headers, timeout=35)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"[!] 請求失敗 {url}: {e}")
    return None

def parse_vd_lives(data):
    res_map = {}
    if not isinstance(data, dict) or "VDLives" not in data:
        return res_map

    collect_time = data.get("UpdateTime", time.strftime("%Y-%m-%d %H:%M:%S"))

    for item in data.get("VDLives", []):
        vd_id = item.get("VDID", "")
        if not vd_id:
            continue

        speeds = []
        for flow in item.get("LinkFlows", []):
            for lane in flow.get("Lanes", []):
                spd = lane.get("Speed")
                if spd is not None and spd > 0:
                    speeds.append(round(spd))

        if speeds:
            avg_speed = round(sum(speeds) / len(speeds))
            res_map[vd_id] = {
                "speed": avg_speed,
                "lanes": speeds,
                "time": collect_time
            }

    return res_map

def main():
    print("[*] 正在向 TDX 取得 Access Token...")
    token = get_token()
    if not token:
        print("[-] 無法取得 Token")
        sys.exit(1)
    print("[+] 成功取得 TDX Access Token")

    print("[*] 正在抓取全台國道 VD 即時路況...")
    fw_data = fetch_data(token, VD_FREEWAY_URL)
    freeway_map = parse_vd_lives(fw_data)
    print(f"[+] 國道 VD 即時有效測點: {len(freeway_map)} 處")

    time.sleep(2)
    print("[*] 正在抓取全台省道/快速公路 VD 即時路況...")
    hw_data = fetch_data(token, VD_HIGHWAY_URL)
    highway_map = parse_vd_lives(hw_data)
    print(f"[+] 快速公路/省道 VD 即時有效測點: {len(highway_map)} 處")

    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    output = {
        "status": "success",
        "updateTime": current_time_str,
        "updateTimestamp": int(time.time()),
        "freewayCount": len(freeway_map),
        "highwayCount": len(highway_map),
        "freewayMap": freeway_map,
        "highwayMap": highway_map,
        "incidents": []
    }

    target_path = os.path.join(os.path.dirname(__file__), "traffic_live.json")
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    print(f"[+] 成功產出 {target_path}，更新時間: {current_time_str}")

if __name__ == "__main__":
    main()
