def camelize(string: str) -> str:
    parts = string.split('_')
    return parts[0] + ''.join(p.title() for p in parts[1:])