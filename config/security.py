import os
import tempfile
import base64

from config.loader import load_yaml
_private_key_file = None
_private_key = None
def get_private_key() -> str:
    global _private_key

    if _private_key:
        return _private_key
    
    config = load_yaml("config.yaml")
    encoded_key = config["salesforce"]["JWT_PRIVATE_KEY_BASE64"]
    if not encoded_key:
        raise RuntimeError(
            "JWT_PRIVATE_KEY_BASE64 environment variable is missing."
        )

    _private_key = base64.b64decode(encoded_key).decode("utf-8")
    return _private_key


def get_private_key_file() -> str:
    global _private_key_file

    if _private_key_file:
        return _private_key_file

    key = get_private_key()

    path = os.path.join(
        tempfile.gettempdir(),
        "salesforce.key",
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write(key)

    _private_key_file = path
    return _private_key_file