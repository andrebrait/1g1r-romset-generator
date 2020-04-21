import os
import sys
import tarfile
import zipfile
from abc import ABC, abstractmethod
from tarfile import TarFile
from typing import List, IO, Optional
from zipfile import ZipFile


class ArchiveType(ABC):

    @abstractmethod
    def check_type(self, path: str) -> bool:
        pass

    @abstractmethod
    def create_object(self, path: str, mode: str = 'r') -> 'Archive':
        pass


class Archive(ABC):
    def __init__(
            self,
            full_path: str,
            mode: str):
        self.__full_path = full_path
        self.__mode = mode

    def full_path(self) -> str:
        return self.__full_path

    def mode(self) -> str:
        return self.__mode

    @abstractmethod
    def file_names(self) -> List[str]:
        pass

    @abstractmethod
    def size(self, file_name: str) -> int:
        pass

    @abstractmethod
    def open(self, file_name: str) -> IO:
        pass

    @abstractmethod
    def __enter__(self) -> 'Archive':
        pass

    @abstractmethod
    def __exit__(self, typ, value, traceback):
        pass


class _ZipArchive(Archive):

    def __init__(
            self,
            full_path: str,
            mode: str = 'r'):
        super().__init__(full_path, mode)
        self.__archive: Optional[ZipFile] = None

    def file_names(self) -> List[str]:
        return [n for n in self.__archive.namelist()
                if not (n.endswith(os.path.sep) or n.endswith('/'))]

    def size(self, file_name: str) -> int:
        return self.__archive.getinfo(file_name).file_size

    def open(self, file_name: str) -> IO:
        return self.__archive.open(file_name, mode=self.mode())

    def __enter__(self) -> 'Archive':
        self.__archive = ZipFile(self.full_path(), mode=self.mode())
        return self

    def __exit__(self, typ, value, traceback):
        self.__archive.close()
        self.__archive = None


class _TarArchive(Archive):

    def __init__(
            self,
            full_path: str,
            mode: str = 'r'):
        super().__init__(full_path, mode)
        self.__archive: Optional[TarFile] = None

    def file_names(self) -> List[str]:
        return [n for n in self.__archive.getnames()
                if not (n.endswith(os.path.sep) or n.endswith('/'))]

    def size(self, file_name: str) -> int:
        return self.__archive.getmember(file_name).size

    def open(self, file_name: str) -> IO:
        return self.__archive.open(file_name, mode=self.mode())

    def __enter__(self) -> 'Archive':
        self.__archive = TarFile(self.full_path(), mode=self.mode())
        return self

    def __exit__(self, typ, value, traceback):
        self.__archive.close()
        self.__archive = None


class _ZipArchiveType(ArchiveType):

    def check_type(self, path: str) -> bool:
        return zipfile.is_zipfile(str)

    def create_object(self, path: str, mode: str = 'r') -> 'Archive':
        return _ZipArchive(path, mode)


class _TarArchiveType(ArchiveType):

    def check_type(self, path: str) -> bool:
        return tarfile.is_tarfile(str)

    def create_object(self, path: str, mode: str = 'r') -> 'Archive':
        return _TarArchive(path, mode)


_SUPPORTED_ARCHIVE_TYPES: List[ArchiveType] = [
    _ZipArchiveType(),
    _TarArchiveType()
]

try:
    import rarfile
except ImportError:
    print(
        "WARNING: Support for RAR archives requires the Python module "
        "'rarfile' to be installed",
        file=sys.stderr)
