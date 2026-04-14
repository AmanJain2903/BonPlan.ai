def fix_schema_for_gemini(schema: dict) -> dict:
    import copy
    schema = copy.deepcopy(schema)
    defs = schema.pop("$defs", {})
    def process_node(node):
        if isinstance(node, dict):
            # Resolve $ref
            if "$ref" in node:
                ref_key = node["$ref"].split("/")[-1]
                resolved = process_node(defs[ref_key])
                for k, v in resolved.items():
                    node[k] = v
                del node["$ref"]
            # Fix anyOf
            if "anyOf" in node:
                non_nulls = [n for n in node["anyOf"] if n.get("type") != "null"]
                if non_nulls:
                    picked = non_nulls[0]
                    if "$ref" in picked:
                        ref_key = picked["$ref"].split("/")[-1]
                        resolved = process_node(defs[ref_key])
                        for k, v in resolved.items():
                            if k not in node:
                                node[k] = v
                    else:
                        picked = process_node(picked)
                        for k, v in picked.items():
                            if k not in node:
                                node[k] = v
                del node["anyOf"]
            # Strip unsupported keys
            for unsupported in ["additionalProperties", "additional_properties"]:
                if unsupported in node:
                    del node[unsupported]
            if "title" in node and isinstance(node["title"], str):
                del node["title"]
            if "default" in node:
                del node["default"]

            # Process remaining items recursively
            for k, v in list(node.items()):
                if k not in ["$ref", "anyOf"]:
                    node[k] = process_node(v)
            return node
        elif isinstance(node, list):
            return [process_node(v) for v in node]
        return node
    return process_node(schema)