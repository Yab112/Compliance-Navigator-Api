import time
from typing import Dict

import jwt
from jwt import PyJWTError

from config.config import settings


def token_response(token: str):
    return {"access_token": token, "type": "Bearer"}


secret_key = settings.secret_key
algorithm = settings.algorithm


def sign_jwt(email: str) -> Dict[str, str]:
    payload = {"email": email, "expires": time.time() + 2400}
    token = jwt.encode(payload, secret_key, algorithm=algorithm)
    return token_response(token)


def decode_jwt(token: str) -> dict:
    try:
        decoded_token = jwt.decode(token, secret_key, algorithms=[algorithm])
    except PyJWTError:
        return {}
    if decoded_token.get("expires", 0) >= time.time():
        return decoded_token
    return {}
