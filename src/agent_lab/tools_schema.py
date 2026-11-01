"""Turn local tool details into model tool definitions. Check tool arguments before a call."""


def to_openai(tool) -> dict:
    """Give the model a tool name, description, and input schema."""
    return {"type": "function", "function": {
        "name": tool.name,
        "description": tool.description or "",
        "parameters": tool.input_schema,
    }}


def check_args(schema: dict, args) -> list[str]:
    """List missing, unknown, and wrong type tool arguments."""
    if not isinstance(args, dict):
        return ["arguments must be a JSON object"]

    properties = schema.get("properties", {})
    problems = [f"missing argument '{name}'" for name in schema.get("required", []) if name not in args]
    problems.extend(f"unknown argument '{name}'" for name in args if name not in properties)

    # ponytail: Check only the simple types used by the nine tools; add schema rules when a tool needs them.
    kinds = {"string": str, "number": (int, float), "integer": int,
             "boolean": bool, "object": dict, "array": list, "null": type(None)}
    for name, value in args.items():
        if name not in properties:
            continue
        kind = properties[name].get("type")
        if not isinstance(kind, str) or kind not in kinds:
            continue
        if not isinstance(value, kinds[kind]) or (kind in ("number", "integer") and isinstance(value, bool)):
            problems.append(f"argument '{name}' must be {kind}, got {type(value).__name__}")
    return problems
