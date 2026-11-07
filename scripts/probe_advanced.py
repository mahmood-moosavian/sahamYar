#!/usr/bin/env python3
"""Compare auth vs no-auth, check OPTIONS preflight, IDOR attempts, rate limiting."""
import json, time, urllib.request, urllib.error, ssl, threading
from collections import Counter

TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6IjE2RUIxNEUwQ0Y0RUM2RUQ0MjcyN0JFQTdBRDU5QzczQjFBMjk1QjhSUzI1NiIsInR5cCI6ImF0K2p3dCIsIng1dCI6IkZ1c1U0TTlPeHUxQ2NudnFldFdjYzdHaWxiZyJ9.eyJuYmYiOjE3OTQwMzUxODUsImV4cCI6MTgwMTgxMTE4NSwiaXNzIjoiaHR0cDovL2lkZW50aXR5c2VydmVyIiwiY2xpZW50X2lkIjoiZDYyYzk1NmUtN2Q0ZC00MjNiLWExYzgtYTk0MjA4M2I2OWMyIiwic3ViIjoiMjc2NDU4IiwiYXV0aF90aW1lIjoxNzk0MDM1MTg1LCJpZHAiOiJsb2NhbCIsImh0dHA6Ly9zY2hlbWFzLnhtbHNvYXAub3JnL3dzLzIwMDUvMDUvaWRlbnRpdHkvY2xhaW1zL25hbWVpZGVudGlmaWVyIjoiMjc2NDU4IiwiTW9iaWxlIjoiMDkxNTQxNjUyMTAiLCJUZWxlZ3JhbUlkIjoiIiwiUGxhbiI6IjUiLCJGUEMiOiIxIiwiVGltZUZyYW1lIjoiRmFsc2UiLCJBcHBJZCI6ImQ2MmM5NTZlLTdkNGQtNDIzYi1hMWM4LWE5NDIwODNiNjljMiIsImFwcCI6ImJpZmlsdGVyIiwianRpIjoiMUI3QTAwNEZDOTc5MzgyNkZFRUQ5MDVGRkJCMUM3RDEiLCJpYXQiOjE3OTQwMzUxODUsInNjb3BlIjpbImJpZmlsdGVyIl0sImFtciI6WyJwd2QiXX0.CNugXJNeE0t_d6qSXe0QuFpUvvU2RUi2mI-NfFZCZp8Fad_u5sWs1Fdn-Oj5hZgvbjENV63o-pi0Iqcl5Ndc7N3B3RPEyAeZ1ruqQ1gKcsbhXSyumUu9_q1BOJjY8i_39K1LCOe3pgAJZBai3aT4F7GDgjqpVx1JRoWC42LJoxvXpy0HagFSbK3jABLUUloFBny6qZFsywyQGX41revpaNsX1DWhduNlYcROs0yx_F5CX4_Vsm_CZtgDVVVN5EY1ijx3dS5tlK1mgWHPTp55lMnLm6a7mOtV6zIre_Vd8eFjPihKwTGefNIXLnPGyIQgxnMPs4X0mN3QKa4L6uGKtw"

BASE = "https://www.bifilter.ir"
UA = "Mozilla/5.0 bifilter-review"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def req(method, path, with_token=True, headers_extra=None, body=None, origin=None):
    url = BASE + path
    headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fa-IR,fa;q=0.9",
    }
    if origin: headers["Origin"] = origin
    else: headers["Origin"] = "https://www.bifilter.ir"
    headers["Referer"] = "https://www.bifilter.ir/"
    if with_token: headers["Authorization"] = "Bearer " + TOKEN
    if headers_extra: headers.update(headers_extra)
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    else:
        data = None
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(r, timeout=15, context=ctx) as resp:
            body_bytes = resp.read()
            t1 = time.time()
            return {
                "method": method, "path": path, "with_token": with_token,
                "status": resp.status, "ms": int((t1-t0)*1000),
                "len": len(body_bytes),
                "ctype": resp.headers.get("Content-Type",""),
                "acao": resp.headers.get("Access-Control-Allow-Origin",""),
                "acac": resp.headers.get("Access-Control-Allow-Credentials",""),
                "body": body_bytes[:400].decode("utf-8", errors="replace").replace("\n"," "),
            }
    except urllib.error.HTTPError as e:
        t1 = time.time()
        body_bytes = b""
        try: body_bytes = e.read()
        except: pass
        return {
            "method": method, "path": path, "with_token": with_token,
            "status": e.code, "ms": int((t1-t0)*1000),
            "len": len(body_bytes),
            "ctype": e.headers.get("Content-Type",""),
            "acao": e.headers.get("Access-Control-Allow-Origin",""),
            "acac": e.headers.get("Access-Control-Allow-Credentials",""),
            "body": body_bytes[:400].decode("utf-8", errors="replace").replace("\n"," "),
        }
    except Exception as e:
        return {"method": method, "path": path, "with_token": with_token, "status":"ERR", "error": f"{type(e).__name__}: {e}"}

print("=" * 70)
print("1. ANONYMOUS vs AUTHENTICATED (auth boundary check)")
print("=" * 70)
for ep in ["/api/notifications", "/api/bookmarks", "/api/invite", "/api/signals",
           "/api/performance", "/api/bazar", "/api/indexes", "/api/prx",
           "/api/filter/FILTER/7", "/wallet-report", "/api/comments",
           "/api/StrategyNotes/0"]:
    auth = req("GET", ep, with_token=True)
    anon = req("GET", ep, with_token=False)
    print(f"\n{ep}")
    print(f"   AUTH : {auth.get('status')} {auth.get('len')}B  body={auth.get('body','')[:60]}")
    print(f"   ANON : {anon.get('status')} {anon.get('len')}B  body={anon.get('body','')[:60]}")
    if auth.get("status") == anon.get("status") and auth.get("len", 0) == anon.get("len", 0):
        print(f"   *** NO AUTH BOUNDARY - data exposed without token ***")
    elif anon.get("status") in (200, 204) and auth.get("status") in (200, 204):
        print(f"   *** PARTIAL EXPOSURE - some data accessible anonymously ***")
    else:
        print(f"   Auth boundary: enforced (anonymous blocked)")

print()
print("=" * 70)
print("2. CORS PREFLIGHT (Origin reflection test)")
print("=" * 70)
origins_to_test = [
    "https://attacker.example",
    "https://evil.com",
    "null",
    "https://www.bifilter.ir",
    "https://bifilter.ir",
]
for origin in origins_to_test:
    headers_extra = {
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization,content-type",
    }
    r = req("OPTIONS", "/api/notifications", with_token=False, headers_extra=headers_extra, origin=origin)
    print(f"  Origin: {origin:<40} -> status={r.get('status')}  ACAC={r.get('acao','-')}  ACACred={r.get('acac','-')}")
    # also try direct GET with Origin
    r2 = req("GET", "/api/notifications", with_token=False, origin=origin)
    print(f"     GET -> status={r2.get('status')}  ACAC={r2.get('acao','-')}  ACACred={r2.get('acac','-')}")

print()
print("=" * 70)
print("3. RATE LIMIT CHECK (50 rapid requests to /api/performance)")
print("=" * 70)
codes = []
t0 = time.time()
for i in range(50):
    r = req("GET", "/api/performance", with_token=True)
    codes.append(r.get("status"))
elapsed = time.time() - t0
print(f"  50 requests in {elapsed:.2f}s ({50/elapsed:.1f} req/s)")
print(f"  Status distribution: {dict(Counter(codes))}")
if all(c == 200 for c in codes):
    print(f"  *** NO RATE LIMITING detected on /api/performance ***")
elif any(c in (429, 503) for c in codes):
    print(f"  Rate limit triggered after {codes.index(next(c for c in codes if c in (429,503)))} requests")
