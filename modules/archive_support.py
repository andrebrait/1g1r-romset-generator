import sys
import tarfile
import tempfile
import zipfile
from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from tarfile import TarFile, TarInfo
from typing import List, IO, Optional, Dict, AnyStr
from zipfile import ZipFile, ZipInfo

TAR_KEY = 'tar'
ZIP_KEY = 'zip'
RAR_KEY = 'rar'
SEVENZIP_KEY = '7z'

_SUPPORTED_ARCHIVE_TYPES: Dict[str, 'ArchiveType'] = {}


def get_archive_type(path: str) -> Optional['ArchiveType']:
    for t in _SUPPORTED_ARCHIVE_TYPES.values():
        if t.check_type(path):
            return t
    return None


class ArchiveType(ABC):

    @abstractmethod
    def check_type(self, path: str) -> bool:
        pass

    @abstractmethod
    def create_object(self, path: str, mode: str = 'r') -> 'Archive':
        pass


class Archive(AbstractContextManager):
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
        infos: List[ZipInfo] = self.__archive.infolist()
        return [i.filename for i in infos if not i.is_dir()]

    def size(self, file_name: str) -> int:
        info: ZipInfo = self.__archive.getinfo(file_name)
        return info.file_size

    def open(self, file_name: str) -> IO[AnyStr]:
        return self.__archive.open(file_name, self.mode())

    def __enter__(self) -> 'Archive':
        self.__archive = ZipFile(self.full_path(), self.mode())
        return self

    def __exit__(self, typ, value, traceback):
        self.__archive.close()
        self.__archive = None


class _ZipArchiveType(ArchiveType):

    def check_type(self, path: str) -> bool:
        return zipfile.is_zipfile(path)

    def create_object(self, path: str, mode: str = 'r') -> 'Archive':
        return _ZipArchive(path, mode)


_SUPPORTED_ARCHIVE_TYPES[ZIP_KEY] = _ZipArchiveType()


class _TarArchive(Archive):

    def __init__(
            self,
            full_path: str,
            mode: str = 'r'):
        super().__init__(full_path, mode)
        self.__archive: Optional[TarFile] = None

    def file_names(self) -> List[str]:
        infos: List[TarInfo] = self.__archive.getmembers()
        return [i.name for i in infos if i.isfile()]

    def size(self, file_name: str) -> int:
        info: TarInfo = self.__archive.getmember(file_name)
        return info.size

    def open(self, file_name: str) -> IO[AnyStr]:
        return self.__archive.open(file_name, self.mode())

    def __enter__(self) -> 'Archive':
        self.__archive = TarFile(self.full_path(), self.mode())
        return self

    def __exit__(self, typ, value, traceback):
        self.__archive.close()
        self.__archive = None


class _TarArchiveType(ArchiveType):

    def check_type(self, path: str) -> bool:
        return tarfile.is_tarfile(path)

    def create_object(self, path: str, mode: str = 'r') -> 'Archive':
        return _TarArchive(path, mode)


_SUPPORTED_ARCHIVE_TYPES[TAR_KEY] = _TarArchiveType()

try:
    import rarfile
    from rarfile import RarFile
    from rarfile import RarInfo


    class _RarArchive(Archive):

        def __init__(self, full_path: str, mode: str):
            super().__init__(full_path, mode)
            self.__archive: Optional[RarFile] = None

        def file_names(self) -> List[str]:
            infos: List[RarInfo] = self.__archive.infolist()
            return [i.filename for i in infos if not i.isdir()]

        def size(self, file_name: str) -> int:
            info: RarInfo = self.__archive.getinfo(file_name)
            return info.file_size

        def open(self, file_name: str) -> IO[AnyStr]:
            return self.__archive.open(file_name, self.mode())

        def __enter__(self) -> 'Archive':
            self.__archive = RarFile(self.full_path(), self.mode())
            return self

        def __exit__(self, typ, value, traceback):
            self.__archive.close()


    class _RarArchiveType(ArchiveType):
        def check_type(self, path: str) -> bool:
            return rarfile.is_rarfile(path)

        def create_object(self, path: str, mode: str = 'r') -> 'Archive':
            return _RarArchive(path, mode)


    _SUPPORTED_ARCHIVE_TYPES[RAR_KEY] = _RarArchiveType()

except ImportError:
    print(
        "WARNING: Support for RAR archives requires the Python module "
        "'rarfile' to be installed",
        file=sys.stderr)

try:
    import py7zr
    from py7zr import SevenZipFile
    import os
    import shutil
    from contextlib import AbstractContextManager


    class _SevenZipArchive(Archive):

        def __init__(self, full_path: str, mode: str):
            super().__init__(full_path, mode)
            self.__archive: Optional[SevenZipFile] = None
            self.__temp_dir: Optional[str] = None
            self.__extracted = False

        def file_names(self) -> List[str]:
            return [i.filename for i in self.__archive.files if
                    not i.is_directory and
                    not i.is_junction and
                    not i.is_socket and
                    not i.is_symlink]

        def size(self, file_name: str) -> int:
            for i in self.__archive.list():
                if i.filename == file_name:
                    return i.uncompressed

        def open(self, file_name: str) -> IO[AnyStr]:
            if self.mode() == 'w':
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
            self.__archive = SevenZipFile(self.full_path(), self.mode())
            return self

        def __exit__(self, typ, value, traceback):
            if self.__temp_dir:
                if self.mode() == 'w':
                    self.__archive.writeall(self.__temp_dir, '/')
                self.__archive.__exit__(typ, value, traceback)
                shutil.rmtree(self.__temp_dir)
            else:
                self.__archive.__exit__(typ, value, traceback)
            self.__temp_dir = None
            self.__extracted = False


    class _SevenZipArchiveType(ArchiveType):
        def check_type(self, path: str) -> bool:
            return py7zr.is_7zfile(path)

        def create_object(self, path: str, mode: str = 'r') -> 'Archive':
            return _SevenZipArchive(path, mode)


    _SUPPORTED_ARCHIVE_TYPES[SEVENZIP_KEY] = _SevenZipArchiveType()

except ImportError:
    print(
        "WARNING: Support for 7Z archives requires the Python module "
        "'py7zr' to be installed",
        file=sys.stderr)
