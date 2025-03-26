def is_dollar_string(value: str) -> bool:
    if not isinstance(value, str):
        return False
    return value.startswith("${") and value.endswith("}")


def to_dollar_string(value: str) -> str:
    if not is_dollar_string(value):
        return f"${{{value}}}"
    return value


def unwrap_dollar_string(value: str) -> str:
    if is_dollar_string(value):
        return value[2:-1]
    return value


def wrap_into_parentheses(value: str) -> str:
    if is_dollar_string(value):
        value = unwrap_dollar_string(value)
        return to_dollar_string(f"({value})")
    return f"({value})"
