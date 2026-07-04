import sys
from pathlib import Path

from filesystem import FileSystem


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


DEFAULT_STORAGE = app_dir() / "filesystem.dat"


def load_or_create(path: Path = DEFAULT_STORAGE) -> FileSystem:
    if path.exists():
        return FileSystem.load(path)
    return FileSystem()


def save(filesystem: FileSystem, path: Path = DEFAULT_STORAGE) -> None:
    filesystem.save(path)
