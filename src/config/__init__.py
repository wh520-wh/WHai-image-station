from .constants import *
from .encryption import encrypt, decrypt
from .utils import parse_headers, safe_int, get_thumbnail_path


def __getattr__(name):
    if name == "Database":
        from .database import Database
        return Database
    raise AttributeError(name)
