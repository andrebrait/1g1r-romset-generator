import os
import re
from abc import ABC, abstractmethod
from math import log
from typing import Callable, Iterable, List

try:
    from lxml import etree as etree_
except ImportError:
    from xml.etree import ElementTree as etree_

_TRUE_REGEX = re.compile(r'^true$', re.IGNORECASE)
_FALSE_REGEX = re.compile(r'^false$', re.IGNORECASE)


def _parse_bool(s: str) -> bool:
    if _TRUE_REGEX.search(s):
        return True
    if _FALSE_REGEX.search(s):
        return False
    raise ValueError('Cannot convert %s to boolean' % s)


class Rule:
    class Test(ABC):
        @abstractmethod
        def apply(self, byte_arr: bytes) -> bool:
            pass

    class DataTest(Test):
        def __init__(
                self,
                value: str,
                offset: str,
                result: str):
            if offset is None:
                offset = '0'
            if result is None:
                result = 'true'
            value_length = len(value)
            if value_length % 2 != 0:
                raise ValueError(
                    'The length of the value must be divisible by 2: %s'
                    % value)
            self.__offset = int(offset, 16)
            self.__value = int(value, 16)
            self.__end = self.__offset + int(value_length / 2)
            self.__result = bool(_parse_bool(result))

        def apply(self, byte_arr: bytes) -> bool:
            bytes_slice = byte_arr[self.__offset:self.__end]
            found_value = int.from_bytes(bytes_slice, 'big')
            return (found_value == self.__value) == self.__result

    class BooleanTest(Test):
        def __init__(
                self,
                operation: str,
                mask: str,
                value: str,
                offset: str,
                result: str):
            if offset is None:
                offset = '0'
            if result is None:
                result = 'true'
            mask_length = len(mask)
            if mask_length != len(value) or mask_length % 2 != 0:
                raise ValueError(
                    'Mask (%s) and value (%s) must be the same length '
                    'and the length must be divisible by 2'
                    % (mask, value))
            self.__mask = int(mask, 16)
            self.__value = int(value, 16)
            self.__offset = int(offset, 16)
            self.__end = self.__offset + int(mask_length / 2)
            self.__result = _parse_bool(result)
            self.__operation = self.__get_op(operation)

        def apply(self, byte_arr: bytes) -> bool:
            return (self.__operation(byte_arr) == self.__value) == self.__result

        def __get_op(self, name: str) -> Callable[[bytes], int]:
            if name == 'and':
                return self.__bitwise_and
            if name == 'or':
                return self.__bitwise_or
            if name == 'xor':
                return self.__bitwise_xor
            raise ValueError('Unknown boolean test: %s' % name)

        def __bitwise_and(self, byte_arr: bytes) -> int:
            bytes_slice = byte_arr[self.__offset:self.__end]
            return self.__mask & int.from_bytes(bytes_slice, 'big')

        def __bitwise_or(self, byte_arr: bytes) -> int:
            bytes_slice = byte_arr[self.__offset:self.__end]
            return self.__mask | int.from_bytes(bytes_slice, 'big')

        def __bitwise_xor(self, byte_arr: bytes) -> int:
            bytes_slice = byte_arr[self.__offset:self.__end]
            return self.__mask ^ int.from_bytes(bytes_slice, 'big')

    class FileTest(Test):
        def __init__(
                self,
                size: str,
                result: str,
                operator: str):
            if result is None:
                result = 'true'
            if operator is None:
                operator = 'equal'
            self.__operation = self.__get_op(size, operator)
            self.__size = int(size, 16) if size != 'PO2' else 0
            self.__result = _parse_bool(result)

        def apply(self, byte_arr: bytes) -> bool:
            return self.__operation(byte_arr) == self.__result

        def __get_op(self, size: str, operator: str) -> Callable[[bytes], bool]:
            if size == 'PO2':
                return Rule.FileTest.__check_po2
            if operator == 'equal':
                return self.__size_eq
            if operator == 'less':
                return self.__size_less
            if operator == 'greater':
                return self.__size_greater
            raise ValueError('Invalid operator: %s' % operator)

        def __size_eq(self, byte_arr: bytes) -> bool:
            return len(byte_arr) == self.__size

        def __size_less(self, byte_arr: bytes) -> bool:
            return len(byte_arr) < self.__size

        def __size_greater(self, byte_arr: bytes) -> bool:
            return len(byte_arr) > self.__size

        @staticmethod
        def __check_po2(byte_arr: bytes) -> bool:
            return log(len(byte_arr), 2).is_integer()

    def __init__(
            self,
            start_offset: str,
            end_offset: str,
            operation: str,
            tests: Iterable[Test] = None):
        if start_offset is None:
            start_offset = '0'
        if end_offset is None:
            end_offset = 'EOF'
        if operation is None:
            operation = 'none'
        if tests is None:
            tests = []
        self.__start_offset = int(start_offset, 16)
        self.__end_offset = int(end_offset, 16) if end_offset != 'EOF' else 0
        self.__operation = self.__get_op(operation)
        self.__tests = tests

    def test(self, byte_arr: bytes) -> bool:
        for test in self.__tests:
            if not test.apply(byte_arr):
                return False
        return True

    def apply(self, byte_arr: bytes) -> bytes:
        return self.__operation(byte_arr)

    def __get_op(self, name: str) -> Callable[[bytes], bytes]:
        if name == 'bitswap':
            return self.__bitswap
        if name == 'byteswap':
            return self.__byteswap
        if name == 'wordswap':
            return self.__wordswap
        if name == 'none':
            return self.__none
        raise ValueError('Unknown operation: %s' % name)

    def __bitswap(self, byte_arr: bytes) -> bytes:
        return self.__none(byte_arr)[::-1]

    def __wordswap(self, byte_arr: bytes) -> bytes:
        return Rule.__invert_bytes(self.__none(byte_arr), 4)

    def __byteswap(self, byte_arr: bytes) -> bytes:
        return Rule.__invert_bytes(self.__none(byte_arr), 2)

    def __none(self, byte_arr: bytes) -> bytes:
        if self.__end_offset == 0:
            return byte_arr[self.__start_offset:]
        else:
            return byte_arr[self.__start_offset:self.__end_offset]

    @staticmethod
    def __invert_bytes(byte_arr: bytes, chunk_size: int) -> bytes:
        result = []
        for i in range(len(byte_arr), 0, -chunk_size):
            result.extend(byte_arr[i - chunk_size:i])
        return bytes(result)


def parse_rules(file: str) -> List[Rule]:
    file = os.path.expanduser(file)
    try:
        parser = etree_.ETCompatXMLParser()
    except AttributeError:
        parser = etree_.XMLParser()
    root = etree_.parse(file, parser).getroot()
    rules: List[Rule] = []
    for detector in root.iter('detector'):
        for rule in detector.iter('rule'):
            tests: List[Rule.Test] = []
            for test in rule.iter():
                if test.tag == 'data':
                    tests.append(Rule.DataTest(
                        test.get('value'),
                        test.get('offset'),
                        test.get('rules')))
                elif test.tag in ('and', 'or', 'xor'):
                    tests.append(Rule.BooleanTest(
                        test.tag,
                        test.get('mask'),
                        test.get('value'),
                        test.get('offset'),
                        test.get('rules')))
                elif test.tag == 'file':
                    tests.append(Rule.FileTest(
                        test.get('size'),
                        test.get('rules'),
                        test.get('operator')))
            rules.append(Rule(
                rule.get('start_offset'),
                rule.get('end_offset'),
                rule.get('operation'),
                tests))
    return rules
