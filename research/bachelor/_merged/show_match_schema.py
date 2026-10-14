import sys
import json
sys.path.insert(0, r"C:\Users\GopaL\AppData\Local\Temp\kilo\rel_wt\backend")

from app.schemas.match import MatchRequest

s = MatchRequest.model_json_schema()
props = s.get("properties", {})
print("REQUIRED:", s.get("required"))
print()
for k, v in props.items():
    t = v.get("type")
    if t is None:
        if "anyOf" in v:
            t = " | ".join(str(a.get("type", a.get("$ref", "?"))) for a in v["anyOf"])
        elif "$ref" in v:
            t = v["$ref"].split("/")[-1]
        elif "enum" in v:
            t = "enum"
        elif "allOf" in v:
            t = "allOf"
        else:
            t = "?"
    dflt = v.get("default", v.get("default_factory", ""))
    print(f"  {k:26} {str(t)[:44]:46} default={str(dflt)[:26]}")

print()
print("=== nested models ===")
defs = s.get("$defs", {})
for name in ("ProfileInput", "MatchProfile", "StudyPreferences", "Profile"):
    if name in defs:
        d = defs[name]
        print(f"\n{name}: required={d.get('required')}")
        for k, v in d.get("properties", {}).items():
            t = v.get("type") or ("enum" if "enum" in v else
                                  (v.get("$ref", "").split("/")[-1] or "?"))
            print(f"    {k:26} {str(t)[:40]:42} default={str(v.get('default',''))[:24]}")

# nested ProfileData
for name, d in defs.items():
    if "profile" in name.lower() or name in ("MatchRequestBody",):
        print(f"\n{name}: required={d.get('required')}")
        for k, v in list(d.get("properties", {}).items())[:20]:
            t = v.get("type") or ("enum" if "enum" in v else
                                  (v.get("$ref", "").split("/")[-1] or "?"))
            print(f"    {k:26} {str(t)[:40]:42} default={str(v.get('default',''))[:24]}")