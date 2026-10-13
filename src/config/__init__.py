from . import constants as constants
from .encryption import decrypt as decrypt
from .encryption import encrypt as encrypt
from .utils import get_thumbnail_path as get_thumbnail_path
from .utils import parse_headers as parse_headers
from .utils import safe_int as safe_int


def __getattr__(name):
    if name == "Database":
        from .database import Database

        return Database
    from . import constants

    if hasattr(constants, name):
        return getattr(constants, name)
    raise AttributeError(name)
