"""字节存储抽象。

约定：
- 数据库只存 `storage_profile + storage_key`，绝存不绝对路径
- 根目录强制限制在项目根目录内
- 图片仅做原样写入，禁止任何转换 / 缩放 / 重压缩
"""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import settings
from app.core.exceptions import StorageWriteError
from app.core.hashing import sha256_file


class StoredObject:
    def __init__(self, *, profile: str, key: str, absolute_path: Path) -> None:
        self.profile = profile
        self.key = key
        self.absolute_path = absolute_path

    def __repr__(self) -> str:  # pragma: no cover
        return f"StoredObject(profile={self.profile!r}, key={self.key!r})"


class StorageBackend(ABC):
    """存储抽象接口。"""

    @abstractmethod
    def put(self, *, key: str, data: bytes, overwrite: bool = False) -> StoredObject:
        """写入字节，返回存储句柄。"""

    @abstractmethod
    def get_path(self, *, key: str) -> Path:
        """返回可读取的本地路径。"""

    @abstractmethod
    def exists(self, *, key: str) -> bool:
        """对象是否存在。"""

    @abstractmethod
    def read_bytes(self, *, key: str) -> bytes:
        """读取全部字节。"""

    @abstractmethod
    def verify(self, *, key: str, expected_sha256: str, expected_size: int) -> bool:
        """校验字节完整性与大小。"""


class FilesystemStorage(StorageBackend):
    """本地文件系统实现（跨平台），启用原子写入。"""

    def __init__(self, *, root: Path | None = None, profile: str | None = None) -> None:
        self.root = root or settings.storage_root_path
        self.profile = profile or settings.STORAGE_PROFILE

    def _resolve(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        root = self.root.resolve()
        if root not in candidate.parents and candidate != root:
            raise StorageWriteError(detail=f"越界路径: {key}")
        return candidate

    def put(self, *, key: str, data: bytes, overwrite: bool = False) -> StoredObject:
        target = self._resolve(key)
        if target.exists() and not overwrite:
            raise StorageWriteError(detail=f"对象已存在: {key}")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        try:
            tmp.write_bytes(data)
            shutil.move(str(tmp), str(target))
        except OSError as exc:
            tmp.unlink(missing_ok=True)
            raise StorageWriteError(detail=str(exc)) from exc
        return StoredObject(profile=self.profile, key=key, absolute_path=target)

    def get_path(self, *, key: str) -> Path:
        return self._resolve(key)

    def exists(self, *, key: str) -> bool:
        return self._resolve(key).exists()

    def read_bytes(self, *, key: str) -> bytes:
        path = self._resolve(key)
        if not path.exists():
            raise StorageWriteError(detail=f"对象不存在: {key}")
        return path.read_bytes()

    def verify(self, *, key: str, expected_sha256: str, expected_size: int) -> bool:
        path = self._resolve(key)
        if not path.exists():
            return False
        if path.stat().st_size != expected_size:
            return False
        return sha256_file(str(path)) == expected_sha256


storage = FilesystemStorage()
