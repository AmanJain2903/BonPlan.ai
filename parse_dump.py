import json

with open("backend/app/agent/dumps/mcp_tools_dump.json") as f:
    tools = json.load(f)

for t in tools:
    name = t.get("name")
    params = t.get("parameters", {})
    props = params.get("properties", {}) or {}
    required = params.get("required") or []
    
    print(f"Tool: {name}")
    print(f"  Required: {required}")
    for k, v in props.items():
        v_type = v.get("type")
        v_desc = v.get("description", "NO_DESC")
        # clean description from new lines
        v_desc = v_desc.replace("\n", " ").strip() if v_desc else "NO_DESC"
        print(f"  - {k} ({v_type}): {v_desc[:80]}...")
    print("-" * 40)
