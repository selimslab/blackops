import base64


def encode(s: str) -> bytes:
    return base64.urlsafe_b64encode(str_to_bytes(s))


def decode(b: bytes) -> bytes:
    return base64.urlsafe_b64decode(bytes_to_str(b))


def str_to_bytes(s: str) -> bytes:
    return s.encode("utf8")


def bytes_to_str(d: bytes) -> str:
    return d.decode("utf8")


def str_to_id(s: str) -> str:
    return bytes_to_str(encode(s))


def id_to_str(s: str) -> str:
    return bytes_to_str(decode(str_to_bytes(s)))
