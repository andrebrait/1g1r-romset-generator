import sys
import tarfile
import tempfile
import zipfile
from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from enum import Enum
from typing import List, IO, Optional, Dict, AnyStr

_SUPPORTED_ARCHIVE_TYPES: Dict['ArchiveKey', 'ArchiveType'] = {}


class ArchiveKey(Enum):
    TAR_KEY = 'tar'
    ZIP_KEY = 'zip'
    RAR_KEY = 'rar'
    SEVENZIP_KEY = '7z'


def for_file(path: str) -> Optional['ArchiveType']:
    for t in _SUPPORTED_ARCHIVE_TYPES.values():
        if t.supports(path):
            return t
    return None


def by_key(key: ArchiveKey) -> Optional['ArchiveType']:
    if key in _SUPPORTED_ARCHIVE_TYPES:
        return _SUPPORTED_ARCHIVE_TYPES[key]
    else:
        return None


class ArchiveType(ABC):

    @abstractmethod
    def supports(self, path: str) -> bool:
        pass

    @abstractmethod
    def open(self, path: str, mode: str = 'r') -> 'Archive':
        pass


class Archive(AbstractContextManager):
    def __init__(
            self,
            full_path: str,
            mode: str):
        if mode not in ("r", "w"):
            raise ValueError('open() requires mode "r" or "w"')
        self.__full_path = full_path
        self.__mode = mode

    @property
    def full_path(self) -> str:
        return self.__full_path

    @property
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

    @staticmethod
    def _check_context(archive_file):
        if not archive_file:
            raise ValueError('Attempt to use an archive out of context')


class _ZipArchive(Archive):

    def __init__(
            self,
            full_path: str,
            mode: str = 'r'):
        super().__init__(full_path, mode)
        self.__archive: Optional[zipfile.ZipFile] = None

    def file_names(self) -> List[str]:
        Archive._check_context(self.__archive)
        infos: List[zipfile.ZipInfo] = self.__archive.infolist()
        return [i.filename for i in infos if not i.is_dir()]

    def size(self, file_name: str) -> int:
        Archive._check_context(self.__archive)
        info: zipfile.ZipInfo = self.__archive.getinfo(file_name)
        return info.file_size

    def open(self, file_name: str) -> IO[AnyStr]:
        Archive._check_context(self.__archive)
        return self.__archive.open(file_name, self.mode)

    def __enter__(self) -> 'Archive':
        self.__archive = zipfile.ZipFile(self.full_path, self.mode).__enter__()
        return self

    def __exit__(self, typ, value, traceback):
        self.__archive.__exit__(typ, value, traceback)
        self.__archive = None


class _ZipArchiveType(ArchiveType):

    def supports(self, path: str) -> bool:
        return zipfile.is_zipfile(path)

    def open(self, path: str, mode: str = 'r') -> 'Archive':
        return _ZipArchive(path, mode)


_SUPPORTED_ARCHIVE_TYPES[ArchiveKey.ZIP_KEY] = _ZipArchiveType()


class _TarArchive(Archive):

    def __init__(
            self,
            full_path: str,
            mode: str = 'r'):
        super().__init__(full_path, mode)
        self.__archive: Optional[tarfile.TarFile] = None

    def file_names(self) -> List[str]:
        Archive._check_context(self.__archive)
        infos: List[tarfile.TarInfo] = self.__archive.getmembers()
        return [i.name for i in infos if i.isfile()]

    def size(self, file_name: str) -> int:
        Archive._check_context(self.__archive)
        info: tarfile.TarInfo = self.__archive.getmember(file_name)
        return info.size

    def open(self, file_name: str) -> IO[AnyStr]:
        Archive._check_context(self.__archive)
        return self.__archive.open(file_name, self.mode)

    def __enter__(self) -> 'Archive':
        self.__archive = tarfile.TarFile(self.full_path, self.mode).__enter__()
        return self

    def __exit__(self, typ, value, traceback):
        self.__archive.__exit__(typ, value, traceback)
        self.__archive = None


class _TarArchiveType(ArchiveType):

    def supports(self, path: str) -> bool:
        return tarfile.is_tarfile(path)

    def open(self, path: str, mode: str = 'r') -> 'Archive':
        return _TarArchive(path, mode)


_SUPPORTED_ARCHIVE_TYPES[ArchiveKey.TAR_KEY] = _TarArchiveType()

try:
    import rarfile

    class _RarArchive(Archive):

        def __init__(self, full_path: str, mode: str):
            super().__init__(full_path, mode)
            self.__archive: Optional[rarfile.RarFile] = None

        def file_names(self) -> List[str]:
            Archive._check_context(self.__archive)
            infos: List[rarfile.RarInfo] = self.__archive.infolist()
            return [i.filename for i in infos if not i.isdir()]

        def size(self, file_name: str) -> int:
            Archive._check_context(self.__archive)
            info: rarfile.RarInfo = self.__archive.getinfo(file_name)
            return info.file_size

        def open(self, file_name: str) -> IO[AnyStr]:
            Archive._check_context(self.__archive)
            return self.__archive.open(file_name, self.mode)

        def __enter__(self) -> 'Archive':
            self.__archive = \
                rarfile.RarFile(self.full_path, self.mode).__enter__()
            return self

        def __exit__(self, typ, value, traceback):
            self.__archive.__exit__(typ, value, traceback)
            self.__archive = None


    class _RarArchiveType(ArchiveType):

        def supports(self, path: str) -> bool:
            return rarfile.is_rarfile(path)

        def open(self, path: str, mode: str = 'r') -> 'Archive':
            return _RarArchive(path, mode)


    _SUPPORTED_ARCHIVE_TYPES[ArchiveKey.RAR_KEY] = _RarArchiveType()

except ImportError as e:
    rarfile = None
    print(
        "WARNING: Disabling support for RAR archives: %s" % e,
        file=sys.stderr)

try:
    import py7zr
    import os
    import shutil


    class _SevenZipArchive(Archive):

        def __init__(self, full_path: str, mode: str):
            super().__init__(full_path, mode)
            self.__archive: Optional[py7zr.SevenZipFile] = None
            self.__temp_dir: Optional[str] = None
            self.__extracted = False

        def file_names(self) -> List[str]:
            Archive._check_context(self.__archive)
            return [i.filename for i in self.__archive.files if
                    not i.is_directory and
                    not i.is_junction and
                    not i.is_socket and
                    not i.is_symlink]

        def size(self, file_name: str) -> int:
            Archive._check_context(self.__archive)
            for i in self.__archive.files:
                if i.filename == file_name:
                    return i.uncompressed
            raise KeyError(
                'There is no item named %s in the archive' % file_name)

        def open(self, file_name: str) -> IO[AnyStr]:
            Archive._check_context(self.__archive)
            if 'w' in self.mode:
                if not self.__temp_dir:
                    self.__temp_dir = tempfile.mkdtemp()
                full_path = os.path.join(self.__temp_dir, file_name)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                return open(full_path, 'wb')
            else:
                if not self.__temp_dir:
                    self.__temp_dir = tempfile.mkdtemp()
                full_path = os.path.join(self.__temp_dir, file_name)
                if not self.__extracted:
                    self.__archive.extractall(self.__temp_dir)
                    self.__extracted = True
                return open(full_path, 'rb')

        def __enter__(self) -> 'Archive':
            self.__archive = \
                py7zr.SevenZipFile(self.full_path, self.mode).__enter__()
            return self

        def __exit__(self, typ, value, traceback):
            if self.__temp_dir:
                if 'w' in self.mode:
                    self.__archive.writeall(self.__temp_dir, '/')
                self.__archive.__exit__(typ, value, traceback)
                shutil.rmtree(self.__temp_dir, ignore_errors=True)
            else:
                self.__archive.__exit__(typ, value, traceback)
            self.__temp_dir = None
            self.__extracted = False


    class _SevenZipArchiveType(ArchiveType):

        def supports(self, path: str) -> bool:
            return py7zr.is_7zfile(path)

        def open(self, path: str, mode: str = 'r') -> 'Archive':
            return _SevenZipArchive(path, mode)


    _SUPPORTED_ARCHIVE_TYPES[ArchiveKey.SEVENZIP_KEY] = _SevenZipArchiveType()

except ImportError as e:
    py7zr = None
    print(
        "WARNING: Disabling support for 7z archives: %s" % e,
        file=sys.stderr)
