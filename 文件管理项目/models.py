from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Union


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class FileEntry:
    name: str
    start_block: int = -1
    size: int = 0
    is_open: bool = False
    create_time: str = field(default_factory=now_text)
    modified_time: str = field(default_factory=now_text)

    @property
    def entry_type(self) -> str:
        return "file"


@dataclass
class Directory:
    name: str
    parent: Optional["Directory"] = None
    children: Dict[str, Union["Directory", FileEntry]] = field(default_factory=dict)
    create_time: str = field(default_factory=now_text)
    modified_time: str = field(default_factory=now_text)

    @property
    def entry_type(self) -> str:
        return "directory"

    def path(self) -> str:
        if self.parent is None:
            return "/"
        parts: List[str] = []
        node: Optional[Directory] = self
        while node is not None and node.parent is not None:
            parts.append(node.name)
            node = node.parent
        return "/" + "/".join(reversed(parts))

    def get_child(self, name: str) -> Optional[Union["Directory", FileEntry]]:
        return self.children.get(name)

    def add_child(self, entry: Union["Directory", FileEntry]) -> None:
        self.children[entry.name] = entry
        self.modified_time = now_text()

    def remove_child(self, name: str) -> None:
        del self.children[name]
        self.modified_time = now_text()
