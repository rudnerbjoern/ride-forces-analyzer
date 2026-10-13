"""Runtime checks at typed dataclass boundaries; annotations do not validate input."""


def has_type(value: object, expected: type | tuple[type, ...]) -> bool:
    return isinstance(value, expected)
