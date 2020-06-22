import shutil
from typing import List, Any, Pattern, Optional, Match, Iterable

TRIM_PREFIX = '(...)'


def get_index(ls: List[Any], item: Any, default: int) -> int:
    try:
        if ls:
            return ls.index(item)
        return default
    except ValueError:
        return default


def check_in_pattern_list(name: str, patterns: Iterable[Pattern]) -> bool:
    if patterns:
        for pattern in patterns:
            if pattern.search(name):
                return True
    return False


def to_int_list(string: str, multiplier: int) -> List[int]:
    return [multiplier * ord(x) for x in string]


def get(ls: List[int], index: int) -> int:
    return ls[index] if index < len(ls) else 0


def add_padding(strings: List[str]) -> List[str]:
    parts_list = [s.split('.') for s in strings]
    lengths = [[len(part) for part in parts] for parts in parts_list]
    max_parts = max([len(parts) for parts in parts_list])
    max_lengths = [max([get(lenght, i) for lenght in lengths])
                   for i in range(0, max_parts)]
    for parts in parts_list:
        for i in range(0, len(parts)):
            parts[i] = ('0' * (max_lengths[i] - len(parts[i]))) + parts[i]
    return ['.'.join(parts) for parts in parts_list]


def get_or_default(match: Optional[Match], default: str) -> str:
    version = match.group(1) if match else None
    return version if version else default


def available_columns(current_text: str) -> int:
    term_size = shutil.get_terminal_size((80, 20))
    return max(0, term_size.columns - len(current_text))


def trim_to(obj: Any, n: int) -> str:
    text = str(obj)
    if len(text) > n:
        return '%s%s' % (TRIM_PREFIX, text[-(n - len(TRIM_PREFIX)):])
    return text


def is_valid(x: str) -> bool:
    return bool(x and not x.isspace())
