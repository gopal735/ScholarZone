import requests
import json

base_url = "https://scholarzone-api-2ee2d.containers.snapdeploy.app"

# Get the full OpenAPI schema
r = requests.get(f"{base_url}/openapi.json", timeout=30, headers={"Cache-Control": "no-cache"})
schema = r.json()

print("Available endpoints:")
for path, methods in sorted(schema.get("paths", {}).items()):
    for method, info in methods.items():
        desc = info.get("description", "")[:60]
        print(f"  {method.upper()} {path} - {info.get('summary', '')}")
        if info.get("parameters"):
            for param in info["parameters"]:
                name = param.get("name", "")
                in_ = param.get("in", "")
                required = param.get("required", False)
                print(f"    param: {name} ({'required' if required else 'optional'}) in={in_}")
        if info.get("requestBody"):
            print(f"    requestBody: {json.dumps(info['requestBody'])[:100]}")

# Security schemes
print("\nSecurity schemes:")
for name, scheme in schema.get("components", {}).get("securitySchemes", {}).items():
    print(f"  {name}: {scheme}")

# Check for any endpoint that might reveal env vars
print("\nAll paths with 'internal' in them:")
for path in sorted(schema.get("paths", {}).keys()):
    if "internal" in path:
        methods = schema["paths"][path]
        for method, info in methods.items():
            print(f"  {method.upper()} {path}")
            print(f"    Summary: {info.get('summary', '')}")
            print(f"    Description: {info.get('description', '')[:200]}")
