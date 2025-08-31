import logging

COMMON_CONTEXT: dict = dict(help_option_names=["-h", "--help"])
LOG: logging.Logger = logging.getLogger(__name__)
SHITTY_REJECT_CHARACTERS_WE_HATES: list[str] = [
    "'",
    '"',
    '/',
    '\\',
]
TAG_DELIMITER: str = ";"
