#!/usr/bin/env python3
"""Decode and analyze the bifilter JWT token (no signature verification - just inspect claims)."""
import base64
import json
import sys
from datetime import datetime, timezone

TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6IjE2RUIxNEUwQ0Y0RUM2RUQ0MjcyN0JFQTdBRDU5QzczQjFBMjk1QjhSUzI1NiIsInR5cCI6ImF0K2p3dCIsIng1dCI6IkZ1c1U0TTlPeHUxQ2NudnFldFdjYzdHaWxiZyJ9.eyJuYmYiOjE3OTQwMzUxODUsImV4cCI6MTgwMTgxMTE4NSwiaXNzIjoiaHR0cDovL2lkZW50aXR5c2VydmVyIiwiY2xpZW50X2lkIjoiZDYyYzk1NmUtN2Q0ZC00MjNiLWExYzgtYTk0MjA4M2I2OWMyIiwic3ViIjoiMjc2NDU4IiwiYXV0aF90aW1lIjoxNzk0MDM1MTg1LCJpZHAiOiJsb2NhbCIsImh0dHA6Ly9zY2hlbWFzLnhtbHNvYXAub3JnL3dzLzIwMDUvMDUvaWRlbnRpdHkvY2xhaW1zL25hbWVpZGVudGlmaWVyIjoiMjc2NDU4IiwiTW9iaWxlIjoiMDkxNTQxNjUyMTAiLCJUZWxlZ3JhbUlkIjoiIiwiUGxhbiI6IjUiLCJGUEMiOiIxIiwiVGltZUZyYW1lIjoiRmFsc2UiLCJBcHBJZCI6ImQ2MmM5NTZlLTdkNGQtNDIzYi1hMWM4LWE5NDIwODNiNjljMiIsImFwcCI6ImJpZmlsdGVyIiwianRpIjoiMUI3QTAwNEZDOTc5MzgyNkZFRUQ5MDVGRkJCMUM3RDEiLCJpYXQiOjE3OTQwMzUxODUsInNjb3BlIjpbImJpZmlsdGVyIl0sImFtciI6WyJwd2QiXX0.CNugXJNeE0t_d6qSXe0QuFpUvvU2RUi2mI-NfFZCZp8Fad_u5sWs1Fdn-Oj5hZgvbjENV63o-pi0Iqcl5Ndc7N3B3RPEyAeZ1ruqQ1gKcsbhXSyumUu9_q1BOJjY8i_39K1LCOe3pgAJZBai3aT4F7GDgjqpVx1JRoWC42LJoxvXpy0HagFSbK3jABLUUloFBny6qZFsywyQGX41revpaNsX1DWhduNlYcROs0yx_F5CX4_Vsm_CZtgDVVVN5EY1ijx3dS5tlK1mgWHPTp55lMnLm6a7mOtV6zIre_Vd8eFjPihKwTGefNIXLnPGyIQgxnMPs4X0mN3QKa4L6uGKtw"

def b64url_decode(seg: str) -> bytes:
    pad = "=" * (-len(seg) % 4)
    return base64.urlsafe_b64decode(seg + pad)

parts = TOKEN.split(".")
header_raw, payload_raw, signature_raw = parts[0], parts[1], parts[2]

header = json.loads(b64url_decode(header_raw))
payload = json.loads(b64url_decode(payload_raw))
sig_bytes = b64url_decode(signature_raw)

def ts_to_str(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

print("=" * 70)
print("JWT HEADER")
print("=" * 70)
print(json.dumps(header, indent=2, ensure_ascii=False))
print()
print("=" * 70)
print("JWT PAYLOAD (Claims)")
print("=" * 70)
print(json.dumps(payload, indent=2, ensure_ascii=False))
print()
print("=" * 70)
print("SIGNATURE")
print("=" * 70)
print(f"Algorithm : {header.get('alg')}")
print(f"Key ID    : {header.get('kid')}")
print(f"X5T       : {header.get('x5t')}")
print(f"Sig bytes : {len(sig_bytes)} bytes ({len(sig_bytes)*8} bits)")
print(f"Sig hex   : {sig_bytes.hex()[:80]}...")
print()
print("=" * 70)
print("TIME ANALYSIS")
print("=" * 70)
iat = payload.get("iat"); nbf = payload.get("nbf"); exp = payload.get("exp")
auth_time = payload.get("auth_time")
print(f"iat       : {iat}  -> {ts_to_str(iat)}")
print(f"nbf       : {nbf}  -> {ts_to_str(nbf)}")
print(f"exp       : {exp}  -> {ts_to_str(exp)}")
print(f"auth_time : {auth_time}  -> {ts_to_str(auth_time)}")
print(f"Lifetime  : {(exp-iat)/86400:.2f} days ({(exp-iat)/3600:.1f} hours)")
print(f"Current UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
now = int(datetime.now(timezone.utc).timestamp())
if now < nbf:
    print(f"Status    : NOT YET VALID (future)")
elif now > exp:
    print(f"Status    : EXPIRED")
else:
    remaining = exp - now
    print(f"Status    : VALID, {remaining/86400:.2f} days remaining")
print()
print("=" * 70)
print("CLAIMS ANALYSIS")
print("=" * 70)
print(f"Issuer          : {payload.get('iss')}")
print(f"Client ID       : {payload.get('client_id')}")
print(f"App ID          : {payload.get('AppId')}")
print(f"App             : {payload.get('app')}")
print(f"Subject (user)  : {payload.get('sub')}")
print(f"Name identifier: {payload.get('http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier')}")
print(f"Identity provider: {payload.get('idp')}")
print(f"AMR (auth method): {payload.get('amr')}")
print(f"Scope           : {payload.get('scope')}")
print(f"Mobile          : {payload.get('Mobile')}")
print(f"TelegramId      : {repr(payload.get('TelegramId'))}")
print(f"Plan            : {payload.get('Plan')}")
print(f"FPC             : {payload.get('FPC')}")
print(f"TimeFrame       : {payload.get('TimeFrame')}")
print(f"JTI (token id)  : {payload.get('jti')}")
print()
print("=" * 70)
print("SECURITY OBSERVATIONS")
print("=" * 70)
print("1. Algorithm RS256 (asymmetric RSA-SHA256) - GOOD practice")
print("2. x5t present - certificate thumbprint for key rotation")
print("3. Issuer = 'http://identityserver' (internal hostname, not bound to public URL)")
print("4. Lifetime ~90 days (long-lived - risk if compromised)")
print("5. 'amr': ['pwd'] - single factor (password only, no MFA)")
print("6. Sensitive PII in token: Mobile number (Iranian +98 09154165210)")
print("7. 'Plan' stored as string '5' - plan-based authorization")
print("8. 'FPC' and 'TimeFrame' custom claims - business logic gates")
print("9. 'sub' = 276458 (sequential numeric ID - predictable)")
print("10. No 'aud' claim - audience not pinned (potential reuse across services)")
print("11. Scope only 'bifilter' (singular scope - coarse)")
