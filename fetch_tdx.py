#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TDX 全台即時路況資料抓取與中繼處理模組
由 GitHub Actions 自動排程定期執行，將高公局與公路局路況彙整為輕量 traffic_live.json
"""

import json
import os
import sys
import time
import requests

TDX_CLIENT_ID = os.environ.get("TDX_CLIENT_ID", "cv1706yang-8ba9e89a-7819-43c6")
TDX_CLIENT_SECRET = os.environ.get("TDX_CLIENT_SECRET", "4ba7c5d3-e9aa-4687-981a-51f5361e8e81")

TOKEN_URL = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
VD_FREEWAY_URL = "https://tdx.transportdata.tw/api/basic/v2/Road/Traffic/Live/VD/Freeway?$format=JSON"
VD_HIGHWAY_URL = "https://tdx.transportdata.tw/api/basic/v2/Road/Traffic/Live/VD/Highway?$format=JSON"
INCIDENT_URL = "https://tdx.transportdata.tw/api/basic/v2/Road/Traffic/Live/Incident/Freeway?$format=JSON"

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
    res.raise_for_status()
    data = res.json()
    return data.get("access_token")

def fetch_tdx_resource(token, url, max_retries=2):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "TaiwanTrafficLive/1.0"
    }
    for attempt in range(max_retries):
        try:
            res = requests.get(url, headers=headers, timeout=30)
            if res.status_code == 200:
                return res.json()
            elif res.status_code == 429:
                print(f"[!] 遇到 Rate Limit (429)，等待 15 秒後重試 ({attempt+1}/{max_retries})...")
                time.sleep(15)
            else:
                print(f"[!] 請求狀態碼: {res.status_code}")
                time.sleep(3)
        except Exception as e:
            print(f"[!] 請求異常: {e}")
            time.sleep(3)
    return []

def process_vd_lives(vd_data):
    """
    將 TDX 的 VD 即時結構簡化為以 VDID 或 LinkID 為 key 的字典
    """
    speed_map = {}
    if not isinstance(vd_data, list):
        if isinstance(vd_data, dict) and "VDLives" in vd_data:
            vd_data = vd_data["VDLives"]
        else:
            return speed_map

    for item in vd_data:
        vd_id = item.get("VDID", "")
        collect_time = item.get("DataCollectTime", "")
        links = item.get("LinkLives", [])
        for link in links:
            link_id = link.get("LinkID", "")
            speed = link.get("Speed")
            if speed is not None and speed >= 0:
                data_obj = {
                    "speed": round(speed),
                    "time": collect_time,
                    "vdId": vd_id
                }
                if link_id:
                    speed_map[link_id] = data_obj
                if vd_id:
                    speed_map[vd_id] = data_obj
    return speed_map

def main():
    print("[*] 開始執行全台路況資料同步作業...")
    token = None
    try:
        token = get_token()
        print("[+] 成功取得 TDX Access Token")
    except Exception as e:
        print(f"[-] TDX Token 取得失敗: {e}")

    vd_freeway = []
    vd_highway = []
    incidents = []

    if token:
        print("[*] 正在抓取國道 VD 即時路況...")
        vd_freeway = fetch_tdx_resource(token, VD_FREEWAY_URL)
        time.sleep(1)
        print("[*] 正在抓取省道/快速公路 VD 即時路況...")
        vd_highway = fetch_tdx_resource(token, VD_HIGHWAY_URL)
        time.sleep(1)
        print("[*] 正在抓取即時事件...")
        incidents = fetch_tdx_resource(token, INCIDENT_URL)

    freeway_map = process_vd_lives(vd_freeway)
    highway_map = process_vd_lives(vd_highway)

    output = {
        "status": "success" if (freeway_map or highway_map) else "empty",
        "updateTime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "updateTimestamp": int(time.time()),
        "freewayCount": len(freeway_map),
        "highwayCount": len(highway_map),
        "freewayMap": freeway_map,
        "highwayMap": highway_map,
        "incidents": incidents if isinstance(incidents, list) else []
    }

    target_path = os.path.join(os.path.dirname(__file__), "traffic_live.json")
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    print(f"[+] 成功更新 {target_path} (國道偵測點: {len(freeway_map)}, 快速公路: {len(highway_map)})")

if __name__ == "__main__":
    main()
