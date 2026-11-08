#!/usr/bin/env python3
"""Probe bifilter API endpoints with the bearer token. Record status code, size, content-type, timing."""
import json
import time
import urllib.request
import urllib.error
import ssl
import socket

TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6IjE2RUIxNEUwQ0Y0RUM2RUQ0MjcyN0JFQTdBRDU5QzczQjFBMjk1QjhSUzI1NiIsInR5cCI6ImF0K2p3dCIsIng1dCI6IkZ1c1U0TTlPeHUxQ2NudnFldFdjYzdHaWxiZyJ9.eyJuYmYiOjE3OTQwMzUxODUsImV4cCI6MTgwMTgxMTE4NSwiaXNzIjoiaHR0cDovL2lkZW50aXR5c2VydmVyIiwiY2xpZW50X2lkIjoiZDYyYzk1NmUtN2Q0ZC00MjNiLWExYzgtYTk0MjA4M2I2OWMyIiwic3ViIjoiMjc2NDU4IiwiYXV0aF90aW1lIjoxNzk0MDM1MTg1LCJpZHAiOiJsb2NhbCIsImh0dHA6Ly9zY2hlbWFzLnhtbHNvYXAub3JnL3dzLzIwMDUvMDUvaWRlbnRpdHkvY2xhaW1zL25hbWVpZGVudGlmaWVyIjoiMjc2NDU4IiwiTW9iaWxlIjoiMDkxNTQxNjUyMTAiLCJUZWxlZ3JhbUlkIjoiIiwiUGxhbiI6IjUiLCJGUEMiOiIxIiwiVGltZUZyYW1lIjoiRmFsc2UiLCJBcHBJZCI6ImQ2MmM5NTZlLTdkNGQtNDIzYi1hMWM4LWE5NDIwODNiNjljMiIsImFwcCI6ImJpZmlsdGVyIiwianRpIjoiMUI3QTAwNEZDOTc5MzgyNkZFRUQ5MDVGRkJCMUM3RDEiLCJpYXQiOjE3OTQwMzUxODUsInNjb3BlIjpbImJpZmlsdGVyIl0sImFtciI6WyJwd2QiXX0.CNugXJNeE0t_d6qSXe0QuFpUvvU2RUi2mI-NfFZCZp8Fad_u5sWs1Fdn-Oj5hZgvbjENV63o-pi0Iqcl5Ndc7N3B3RPEyAeZ1ruqQ1gKcsbhXSyumUu9_q1BOJjY8i_39K1LCOe3pgAJZBai3aT4F7GDgjqpVx1JRoWC42LJoxvXpy0HagFSbK3jABLUUloFBny6qZFsywyQGX41revpaNsX1DWhduNlYcROs0yx_F5CX4_Vsm_CZtgDVVVN5EY1ijx3dS5tlK1mgWHPTp55lMnLm6a7mOtV6zIre_Vd8eFjPihKwTGefNIXLnPGyIQgxnMPs4X0mN3QKa4L6uGKtw"

BASE = "https://www.bifilter.ir"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 bifilter-review"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Endpoints discovered from bundle.js
GET_ENDPOINTS = [
    "/api/notifications",
    "/api/notifications/popup",
    "/api/bookmarks",
    "/api/bazar",
    "/api/bazarState/",
    "/api/indexes",
    "/api/index/",
    "/api/status/",
    "/api/istatus/",
    "/api/cstatus/",
    "/api/fstatus/",
    "/api/rstatus/",
    "/api/cstatus/",
    "/api/MyRatios",
    "/api/performance",
    "/api/program/",
    "/api/invite",
    "/api/holder/",
    "/api/group/",
    "/api/prx",
    "/api/signals",
    "/api/osignals",
    "/api/bsignals",
    "/api/comments",
    "/api/commentStatics",
    "/api/FindEvents/",
    "/api/StrategyNotes/",
    "/api/StrategyNotes/0",
    "/api/history/filter/",
    "/api/crypto/",
    "/api/crypto/filters/",
    "/api/coinsearch/",
    "/api/coinrptstrmpage",
    "/api/forex/",
    "/api/forexsearch/",
    "/api/fsn/",
    "/api/ratio/",
    "/api/search/",
    "/api/symbol/",
    "/api/tvchart/",
    "/api/tvchart/latest/",
    "/api/filter/",
    "/api/filter/I",
    "/api/filter/FILTER/7",
    "/api/filter/FILTER/16",
    "/api/filter/FILTER/59",
    "/api/filter/FILTER/124",
    "/api/rptstrmpage",
    "/api/6940",
    "/api/6940/0",
    "/api/6940/wma",
    "/wallet-report",
    "/wallet-to-plan",
    "/api/AddComment",
    "/manifest.json?s=4",
    # also some non-api paths
    "/map/new.html?s=2",
    "/api/disclaimer",
    "/api/version",
    "/api/health",
    "/api/about",
    "/api/me",
    "/api/user",
    "/api/profile",
    "/api/Account/Login",
    "/api/subscriptions",
    "/api/plan",
    "/api/plan/5",
]

def probe(method, path, with_token=True, body=None):
    url = BASE + path
    headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.6",
        "Origin": "https://www.bifilter.ir",
        "Referer": "https://www.bifilter.ir/",
    }
    if with_token:
        headers["Authorization"] = "Bearer " + TOKEN
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    else:
        data = None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            t1 = time.time()
            body_bytes = resp.read()
            return {
                "method": method,
                "path": path,
                "with_token": with_token,
                "status": resp.status,
                "ms": int((t1 - t0) * 1000),
                "len": len(body_bytes),
                "ctype": resp.headers.get("Content-Type", ""),
                "body_sample": body_bytes[:300].decode("utf-8", errors="replace").replace("\n", " "),
                "headers": dict(resp.headers),
            }
    except urllib.error.HTTPError as e:
        t1 = time.time()
        body_bytes = b""
        try:
            body_bytes = e.read()
        except Exception:
            pass
        return {
            "method": method,
            "path": path,
            "with_token": with_token,
            "status": e.code,
            "ms": int((t1 - t0) * 1000),
            "len": len(body_bytes),
            "ctype": e.headers.get("Content-Type", ""),
            "body_sample": body_bytes[:300].decode("utf-8", errors="replace").replace("\n", " "),
            "headers": dict(e.headers),
        }
    except Exception as e:
        return {
            "method": method,
            "path": path,
            "with_token": with_token,
            "status": "ERR",
            "error": f"{type(e).__name__}: {e}",
        }

results = []
print(f"Probing {len(GET_ENDPOINTS)} endpoints with bearer token (GET)...")
for ep in GET_ENDPOINTS:
    r = probe("GET", ep, with_token=True)
    results.append(r)
    status = r.get("status")
    ms = r.get("ms", "?")
    ln = r.get("len", "?")
    sample = r.get("body_sample", r.get("error", ""))[:80]
    print(f"  [{status}] {ms}ms {ln}B  {ep}  | {sample}")
print()
print("=" * 70)
print(f"Total: {len(results)} endpoints probed")
print("=" * 70)

with open("/home/z/my-project/scripts/api_probe_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

# Summary
from collections import Counter
status_counter = Counter(str(r.get("status")) for r in results)
print("Status code distribution:", dict(status_counter))
ok = [r for r in results if r.get("status") == 200]
print(f"\n200 OK endpoints ({len(ok)}):")
for r in ok:
    print(f"  {r['path']}  ({r['len']}B, {r['ms']}ms)  ctype={r['ctype']}")
