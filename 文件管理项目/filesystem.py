from __future__ import annotations

import math
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from models import Directory, FileEntry, now_text


FREE_BLOCK = -2
END_BLOCK = -1


class FileSystemError(Exception):
    pass


class FileSystem:
    def __init__(self, block_count: int = 128, block_size: int = 64) -> None:
        self.block_count = block_count
        self.block_size = block_size
        self.disk_blocks: List[bytes] = [b"" for _ in range(block_count)]
        self.bitmap: List[bool] = [False for _ in range(block_count)]
        self.fat: List[int] = [FREE_BLOCK for _ in range(block_count)]
        self.root = Directory("/")
        self.current_dir = self.root

    @property
    def capacity(self) -> int:
        return self.block_count * self.block_size

    @property
    def used_blocks(self) -> int:
        return sum(1 for used in self.bitmap if used)

    @property
    def free_blocks(self) -> int:
        return self.block_count - self.used_blocks

    def format(self) -> None:
        self.disk_blocks = [b"" for _ in range(self.block_count)]
        self.bitmap = [False for _ in range(self.block_count)]
        self.fat = [FREE_BLOCK for _ in range(self.block_count)]
        self.root = Directory("/")
        self.current_dir = self.root

    def current_path(self) -> str:
        return self.current_dir.path()

    def resolve_path(self, path: str) -> Union[Directory, FileEntry]:
        if not path or path == ".":
            return self.current_dir
        node: Union[Directory, FileEntry] = self.root if path.startswith("/") else self.current_dir
        parts = [part for part in path.strip("/").split("/") if part and part != "."]
        for part in parts:
            if part == "..":
                if isinstance(node, FileEntry):
                    raise FileSystemError("文件没有上级目录")
                node = node.parent or node
                continue
            if not isinstance(node, Directory):
                raise FileSystemError(f"{part} 不是目录")
            child = node.get_child(part)
            if child is None:
                raise FileSystemError(f"路径不存在：{path}")
            node = child
        return node

    def change_dir(self, path: str) -> str:
        node = self.resolve_path(path)
        if not isinstance(node, Directory):
            raise FileSystemError("目标不是目录")
        self.current_dir = node
        return self.current_path()

    def parent_dir(self) -> str:
        if self.current_dir.parent is not None:
            self.current_dir = self.current_dir.parent
        return self.current_path()

    def list_dir(self, directory: Optional[Directory] = None) -> List[Union[Directory, FileEntry]]:
        target = directory or self.current_dir
        return sorted(target.children.values(), key=lambda entry: (entry.entry_type != "directory", entry.name.lower()))

    def create_dir(self, name: str) -> Directory:
        self._validate_name(name)
        if name in self.current_dir.children:
            raise FileSystemError("同名文件或目录已存在")
        directory = Directory(name=name, parent=self.current_dir)
        self.current_dir.add_child(directory)
        return directory

    def delete_dir(self, name: str) -> None:
        entry = self.current_dir.get_child(name)
        if entry is None:
            raise FileSystemError("目录不存在")
        if not isinstance(entry, Directory):
            raise FileSystemError("目标不是目录")
        if entry.children:
            raise FileSystemError("目录非空，不能删除")
        self.current_dir.remove_child(name)

    def delete_entry(self, name: str) -> List[int]:
        entry = self.current_dir.get_child(name)
        if entry is None:
            raise FileSystemError("文件或目录不存在")
        released: List[int] = []
        if isinstance(entry, Directory):
            released = self._release_directory(entry)
        else:
            if entry.is_open:
                raise FileSystemError("文件已打开，请先关闭")
            released = self._release_chain(entry.start_block)
        self.current_dir.remove_child(name)
        return released

    def rename_entry(self, old_name: str, new_name: str) -> None:
        self._validate_name(new_name)
        if old_name not in self.current_dir.children:
            raise FileSystemError("文件或目录不存在")
        if new_name in self.current_dir.children and new_name != old_name:
            raise FileSystemError("同名文件或目录已存在")
        entry = self.current_dir.children.pop(old_name)
        entry.name = new_name
        entry.modified_time = now_text()
        self.current_dir.children[new_name] = entry
        self.current_dir.modified_time = now_text()

    def create_file(self, name: str, content: str = "") -> FileEntry:
        self._validate_name(name)
        if name in self.current_dir.children:
            raise FileSystemError("同名文件或目录已存在")
        file_entry = FileEntry(name=name)
        self.current_dir.add_child(file_entry)
        if content:
            self.write_file(name, content)
        return file_entry

    def delete_file(self, name: str) -> List[int]:
        entry = self.current_dir.get_child(name)
        if entry is None:
            raise FileSystemError("文件不存在")
        if not isinstance(entry, FileEntry):
            raise FileSystemError("目标不是文件")
        if entry.is_open:
            raise FileSystemError("文件已打开，请先关闭")
        released = self._release_chain(entry.start_block)
        self.current_dir.remove_child(name)
        return released

    def open_file(self, name: str) -> None:
        entry = self._get_file(name)
        if entry.is_open:
            raise FileSystemError("文件已经处于打开状态")
        entry.is_open = True

    def close_file(self, name: str) -> None:
        entry = self._get_file(name)
        if not entry.is_open:
            raise FileSystemError("文件尚未打开")
        entry.is_open = False

    def write_file(self, name: str, content: str) -> List[int]:
        entry = self._get_file(name)
        data = content.encode("utf-8")
        old_blocks = self._release_chain(entry.start_block)
        entry.start_block = END_BLOCK
        entry.size = 0
        if not data:
            entry.modified_time = now_text()
            return old_blocks

        block_need = math.ceil(len(data) / self.block_size)
        blocks = self._allocate_blocks(block_need)
        for index, block_id in enumerate(blocks):
            start = index * self.block_size
            chunk = data[start : start + self.block_size]
            self.disk_blocks[block_id] = chunk
            self.bitmap[block_id] = True
            self.fat[block_id] = blocks[index + 1] if index + 1 < len(blocks) else END_BLOCK
        entry.start_block = blocks[0]
        entry.size = len(data)
        entry.modified_time = now_text()
        return blocks

    def read_file(self, name: str) -> str:
        entry = self._get_file(name)
        if entry.start_block == END_BLOCK or entry.size == 0:
            return ""
        data = bytearray()
        for block_id in self.file_blocks(entry):
            data += self.disk_blocks[block_id]
        return bytes(data[: entry.size]).decode("utf-8", errors="replace")

    def file_blocks(self, entry: FileEntry) -> List[int]:
        blocks: List[int] = []
        block_id = entry.start_block
        seen = set()
        while block_id not in (END_BLOCK, FREE_BLOCK) and block_id >= 0:
            if block_id in seen or block_id >= self.block_count:
                raise FileSystemError("FAT 链异常")
            seen.add(block_id)
            blocks.append(block_id)
            block_id = self.fat[block_id]
        return blocks

    def block_owner_map(self) -> Dict[int, str]:
        owners: Dict[int, str] = {}

        def visit(directory: Directory) -> None:
            for entry in directory.children.values():
                if isinstance(entry, Directory):
                    visit(entry)
                else:
                    path = self._entry_path(directory, entry.name)
                    for block_id in self.file_blocks(entry):
                        owners[block_id] = path

        visit(self.root)
        return owners

    def entry_info(self, entry: Union[Directory, FileEntry]) -> Dict[str, str]:
        if isinstance(entry, Directory):
            return {
                "名称": entry.name,
                "类型": "目录",
                "路径": entry.path(),
                "创建时间": entry.create_time,
                "修改时间": entry.modified_time,
                "子项数量": str(len(entry.children)),
            }
        blocks = self.file_blocks(entry)
        return {
            "名称": entry.name,
            "类型": "文件",
            "起始块": "-" if entry.start_block == END_BLOCK else str(entry.start_block),
            "占用块": " -> ".join(map(str, blocks)) if blocks else "-",
            "大小": f"{entry.size} B",
            "是否打开": "是" if entry.is_open else "否",
            "创建时间": entry.create_time,
            "修改时间": entry.modified_time,
        }

    def save(self, file_path: Union[str, Path]) -> None:
        with open(file_path, "wb") as fp:
            pickle.dump(self, fp)

    @staticmethod
    def load(file_path: Union[str, Path]) -> "FileSystem":
        with open(file_path, "rb") as fp:
            loaded = pickle.load(fp)
        if not isinstance(loaded, FileSystem):
            raise FileSystemError("存档文件格式不正确")
        return loaded

    def _allocate_blocks(self, count: int) -> List[int]:
        free = [index for index, used in enumerate(self.bitmap) if not used]
        if len(free) < count:
            raise FileSystemError(f"磁盘空间不足，需要 {count} 块，当前仅剩 {len(free)} 块")
        return free[:count]

    def _release_chain(self, start_block: int) -> List[int]:
        if start_block in (END_BLOCK, FREE_BLOCK):
            return []
        released: List[int] = []
        block_id = start_block
        seen = set()
        while block_id not in (END_BLOCK, FREE_BLOCK) and block_id >= 0:
            if block_id in seen or block_id >= self.block_count:
                raise FileSystemError("FAT 链异常，释放失败")
            seen.add(block_id)
            next_block = self.fat[block_id]
            self.disk_blocks[block_id] = b""
            self.bitmap[block_id] = False
            self.fat[block_id] = FREE_BLOCK
            released.append(block_id)
            block_id = next_block
        return released

    def _release_directory(self, directory: Directory) -> List[int]:
        released: List[int] = []
        for entry in list(directory.children.values()):
            if isinstance(entry, Directory):
                released.extend(self._release_directory(entry))
            else:
                if entry.is_open:
                    raise FileSystemError(f"文件 {entry.name} 已打开，请先关闭")
                released.extend(self._release_chain(entry.start_block))
        directory.children.clear()
        return released

    def _get_file(self, name: str) -> FileEntry:
        entry = self.current_dir.get_child(name)
        if entry is None:
            raise FileSystemError("文件不存在")
        if not isinstance(entry, FileEntry):
            raise FileSystemError("目标不是文件")
        return entry

    def _validate_name(self, name: str) -> None:
        if not name or not name.strip():
            raise FileSystemError("名称不能为空")
        if "/" in name or "\\" in name:
            raise FileSystemError("名称不能包含路径分隔符")
        if name in (".", ".."):
            raise FileSystemError("名称不合法")

    def _entry_path(self, directory: Directory, name: str) -> str:
        if directory.parent is None:
            return "/" + name
        return directory.path().rstrip("/") + "/" + name
