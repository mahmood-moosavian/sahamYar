#!/usr/bin/env python3
"""Test 404 endpoints with proper parameters discovered from bundle.js analysis."""
import json, time, urllib.request, urllib.error, ssl

TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6IjE2RUIxNEUwQ0Y0RUM2RUQ0MjcyN0JFQTdBRDU5QzczQjFBMjk1QjhSUzI1NiIsInR5cCI6ImF0K2p3dCIsIng1dCI6IkZ1c1U0TTlPeHUxQ2NudnFldFdjYzdHaWxiZyJ9.eyJuYmYiOjE3OTQwMzUxODUsImV4cCI6MTgwMTgxMTE4NSwiaXNzIjoiaHR0cDovL2lkZW50aXR5c2VydmVyIiwiY2xpZW50X2lkIjoiZDYyYzk1NmUtN2Q0ZC00MjNiLWExYzgtYTk0MjA4M2I2OWMyIiwic3ViIjoiMjc2NDU4IiwiYXV0aF90aW1lIjoxNzk0MDM1MTg1LCJpZHAiOiJsb2NhbCIsImh0dHA6Ly9zY2hlbWFzLnhtbHNvYXAub3JnL3dzLzIwMDUvMDUvaWRlbnRpdHkvY2xhaW1zL25hbWVpZGVudGlmaWVyIjoiMjc2NDU4IiwiTW9iaWxlIjoiMDkxNTQxNjUyMTAiLCJUZWxlZ3JhbUlkIjoiIiwiUGxhbiI6IjUiLCJGUEMiOiIxIiwiVGltZUZyYW1lIjoiRmFsc2UiLCJBcHBJZCI6ImQ2MmM5NTZlLTdkNGQtNDIzYi1hMWM4LWE5NDIwODNiNjljMiIsImFwcCI6ImJpZmlsdGVyIiwianRpIjoiMUI3QTAwNEZDOTc5MzgyNkZFRUQ5MDVGRkJCMUM3RDEiLCJpYXQiOjE3OTQwMzUxODUsInNjb3BlIjpbImJpZmlsdGVyIl0sImFtciI6WyJwd2QiXX0.CNugXJNeE0t_d6qSXe0QuFpUvvU2RUi2mI-NfFZCZp8Fad_u5sWs1Fdn-Oj5hZgvbjENV63o-pi0Iqcl5Ndc7N3B3RPEyAeZ1ruqQ1gKcsbhXSyumUu9_q1BOJjY8i_39K1LCOe3pgAJZBai3aT4F7GDgjqpVx1JRoWC42LJoxvXpy0HagFSbK3jABLUUloFBny6qZFsywyQGX41revpaNsX1DWhduNlYcROs0yx_F5CX4_Vsm_CZtgDVVVN5EY1ijx3dS5tlK1mgWHPTp55lMnLm6a7mOtV6zIre_Vd8eFjPihKwTGefNIXLnPGyIQgxnMPs4X0mN3QKa4L6uGKtw"

BASE = "https://www.bifilter.ir"
UA = "Mozilla/5.0 bifilter-review"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Real codes from earlier responses
SYMBOL_CODE = "3407806799514469"   # شاروم
SYMBOL_CODE2 = "48241092863917835" # ولپارس
SYMBOL_SHORT = "6940"              # used in /api/6940
INDEX_CODE = "32048214673668089"   # placeholder for index code (need to find)

# Get a real index code from /api/indexes
def get_first_index_code():
    url = BASE + "/api/indexes"
    req = urllib.request.Request(url, headers={"Authorization": "Bearer "+TOKEN, "User-Agent": UA, "Origin": BASE})
    with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
        data = json.loads(r.read().decode())
        if data and isinstance(data, list):
            return data[0].get("SymbolCode") or data[0].get("Code") or data[0].get("Id")
    return None

def get_first_symbol_code():
    url = BASE + "/api/indexes"
    req = urllib.request.Request(url, headers={"Authorization": "Bearer "+TOKEN, "User-Agent": UA, "Origin": BASE})
    with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
        data = json.loads(r.read().decode())
        for it in data:
            if it.get("SymbolCode"):
                return it["SymbolCode"]
    return None

print("Fetching real codes from /api/indexes...")
idx_code = get_first_index_code()
print(f"First index code: {idx_code}")

# Also fetch a real symbol code from /api/prx (large list of portfolios)
def get_first_symbol_from_prx():
    url = BASE + "/api/prx"
    req = urllib.request.Request(url, headers={"Authorization": "Bearer "+TOKEN, "User-Agent": UA, "Origin": BASE})
    with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
        data = json.loads(r.read().decode())
        if data and isinstance(data, list) and data[0].get("SymbolsPlus"):
            return data[0]["SymbolsPlus"][0].get("TsetmcCode")
    return None

sym_code = get_first_symbol_from_prx()
print(f"First symbol code (TsetmcCode): {sym_code}")

# Also try a known format - many Iranian stock codes start with these prefixes
# From /api/signals, Code=3407806799514469 (شاروم) so that's a 17-digit code
# Let me also try symbol "فملی" which is commonly فولاد مبارکه اصفهان

def test(method, path, label="", body=None):
    url = BASE + path
    headers = {
        "Authorization": "Bearer "+TOKEN,
        "User-Agent": UA,
        "Origin": BASE,
        "Referer": BASE+"/",
        "Accept": "application/json, text/plain, */*",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    else:
        data = None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            body_bytes = r.read()
            t1 = time.time()
            sample = body_bytes[:250].decode("utf-8", errors="replace").replace("\n"," ")
            print(f"  [{r.status}] {int((t1-t0)*1000)}ms  {len(body_bytes)}B  {label}")
            print(f"        {path}")
            print(f"        ↳ {sample}")
            return True
    except urllib.error.HTTPError as e:
        t1 = time.time()
        body_bytes = b""
        try: body_bytes = e.read()
        except: pass
        sample = body_bytes[:200].decode("utf-8", errors="replace").replace("\n"," ")
        print(f"  [{e.code}] {int((t1-t0)*1000)}ms  {len(body_bytes)}B  {label}")
        print(f"        {path}")
        if body_bytes:
            print(f"        ↳ {sample}")
        return False
    except Exception as e:
        print(f"  [ERR] {label}: {e}")
        return False

print()
print("=" * 70)
print("TESTING 404 ENDPOINTS WITH PROPER PARAMETERS")
print("=" * 70)

# Use real codes
sym = sym_code or SYMBOL_CODE
idx = idx_code or "1"

tests = [
    # symbol endpoints - need InsCode (16-17 digit)
    ("GET", f"/api/symbol/{sym}", f"symbol/{sym}"),
    ("GET", f"/api/symbol/{SYMBOL_CODE}", f"symbol/{SYMBOL_CODE} (شاروم)"),
    ("GET", f"/api/symbol/{SYMBOL_CODE2}", f"symbol/{SYMBOL_CODE2} (ولپارس)"),
    
    # status endpoints - need {type}/{id} where type is timeframe like D, W, M
    ("GET", f"/api/status/D/{SYMBOL_CODE}", f"status/D/{SYMBOL_CODE}"),
    ("GET", f"/api/status/W/{SYMBOL_CODE}", f"status/W/{SYMBOL_CODE}"),
    ("GET", f"/api/status/M/{SYMBOL_CODE}", f"status/M/{SYMBOL_CODE}"),
    
    # index status
    ("GET", f"/api/istatus/D/{idx}", f"istatus/D/{idx}"),
    
    # ratio endpoints
    ("GET", f"/api/ratio/{SYMBOL_CODE}", f"ratio/{SYMBOL_CODE}"),
    
    # rstatus - ratio status (only ID)
    ("GET", f"/api/rstatus/{SYMBOL_CODE}", f"rstatus/{SYMBOL_CODE}"),
    
    # MyRatios - with type prefix
    ("GET", f"/api/MyRatios/{SYMBOL_CODE}", f"MyRatios/{SYMBOL_CODE}"),
    ("GET", f"/api/MyRatiosD/{SYMBOL_CODE}", f"MyRatiosD/{SYMBOL_CODE}"),
    
    # group - with ID
    ("GET", f"/api/group/{SYMBOL_CODE}", f"group/{SYMBOL_CODE}"),
    
    # holder history
    ("GET", f"/api/holder/{SYMBOL_CODE}/history", f"holder/{SYMBOL_CODE}/history"),
    
    # tvchart
    ("GET", f"/api/tvchart/{SYMBOL_CODE}", f"tvchart/{SYMBOL_CODE}"),
    ("GET", "/api/tvchart/latest/GOLD", "tvchart/latest/GOLD"),
    ("GET", "/api/tvchart/latest/OIL_OPEC", "tvchart/latest/OIL_OPEC"),
    
    # search
    ("GET", "/api/search/فولاد", "search/فولاد"),
    ("GET", "/api/search/فملی", "search/فملی"),
    
    # coinsearch
    ("GET", "/api/coinsearch/bitcoin?skip=0", "coinsearch/bitcoin"),
    ("GET", "/api/forexsearch/eurusd?skip=0", "forexsearch/eurusd"),
    
    # crypto
    ("GET", f"/api/crypto/{SYMBOL_CODE}", f"crypto/{SYMBOL_CODE}"),
    ("GET", "/api/crypto/filters/bitcoin?tf=D", "crypto/filters/bitcoin?tf=D"),
    
    # forex
    ("GET", "/api/forex/eurusd", "forex/eurusd"),
    
    # fsn - follow symbol notes
    ("GET", f"/api/fsn/{SYMBOL_CODE}", f"fsn/{SYMBOL_CODE}"),
    
    # StrategyNotes with various numbers
    ("GET", "/api/StrategyNotes/1", "StrategyNotes/1"),
    
    # history/filter
    ("GET", f"/api/history/filter/{SYMBOL_CODE}/0?skip=0&htype=D", "history/filter/..."),
    
    # bazarState
    ("GET", "/api/bazarState/1", "bazarState/1"),
    ("GET", "/api/bazarState/0", "bazarState/0"),
    
    # program
    ("GET", f"/api/program/{SYMBOL_CODE}", f"program/{SYMBOL_CODE}"),
    
    # FindEvents (quantum only)
    ("GET", f"/api/FindEvents/{SYMBOL_CODE}", f"FindEvents/{SYMBOL_CODE} (quantum only)"),
]

for method, path, label in tests:
    test(method, path, label)
    print()
