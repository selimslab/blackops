import hashlib

import simplejson as json  # type: ignore


def dict_to_hash(d: dict) -> str:
    return hashlib.md5(json.dumps(d).encode()).hexdigest()
