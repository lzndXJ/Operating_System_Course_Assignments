"""Dynamic partition memory allocation algorithms."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class FreeBlock:
    start: int
    size: int

    @property
    def end(self) -> int:
        # 计算空闲分区结束地址。
        return self.start + self.size - 1


@dataclass
class AllocatedBlock:
    job_name: str
    start: int
    size: int

    @property
    def end(self) -> int:
        # 计算已分配分区结束地址。
        return self.start + self.size - 1


@dataclass
class OperationResult:
    success: bool
    message: str
    job_name: str = ""
    start: Optional[int] = None
    size: Optional[int] = None
    merged: bool = False
    merge_message: str = ""


class MemoryManager:
    """Keep one independent memory state for FF or BF."""

    def __init__(self, total_size: int = 640, algorithm: str = "FF") -> None:
        # 初始化指定算法的内存管理器。
        self.algorithm = algorithm.upper()
        if self.algorithm not in ("FF", "BF"):
            raise ValueError("algorithm must be 'FF' or 'BF'")
        self.total_size = 0
        self.free_list: List[FreeBlock] = []
        self.allocated_list: List[AllocatedBlock] = []
        self.reset(total_size)

    def reset(self, total_size: int) -> None:
        # 重置内存为一个完整空闲区。
        if total_size <= 0:
            raise ValueError("total_size must be a positive integer")
        self.total_size = total_size
        self.free_list = [FreeBlock(0, total_size)]
        self.allocated_list = []

    def allocate(self, job_name: str, request_size: int) -> OperationResult:
        # 按当前算法为作业申请内存。
        if request_size <= 0:
            return OperationResult(False, "分配失败：申请大小必须是正整数。", job_name, size=request_size)

        if any(block.job_name == job_name for block in self.allocated_list):
            return OperationResult(False, f"分配失败：{job_name} 已经存在。", job_name, size=request_size)

        index = self._select_free_block(request_size)
        if index is None:
            max_free = max((block.size for block in self.free_list), default=0)
            return OperationResult(
                False,
                f"分配失败：没有足够大的空闲分区。申请 {request_size}K，当前最大空闲分区 {max_free}K。",
                job_name,
                size=request_size,
            )

        free_block = self.free_list[index]
        alloc_start = free_block.start
        self.allocated_list.append(AllocatedBlock(job_name, alloc_start, request_size))

        if free_block.size == request_size:
            del self.free_list[index]
        else:
            free_block.start += request_size
            free_block.size -= request_size

        self.free_list.sort(key=lambda block: block.start)
        return OperationResult(
            True,
            f"分配成功：{job_name} 获得 {request_size}K，起始地址 {alloc_start}K，结束地址 {alloc_start + request_size - 1}K。",
            job_name,
            start=alloc_start,
            size=request_size,
        )

    def release(self, job_name: str) -> OperationResult:
        # 释放指定作业占用的内存。
        for index, block in enumerate(self.allocated_list):
            if block.job_name == job_name:
                released = self.allocated_list.pop(index)
                self.free_list.append(FreeBlock(released.start, released.size))
                merged, merge_message = self.merge_free_blocks()
                return OperationResult(
                    True,
                    f"释放成功：{job_name} 回收 {released.start}-{released.end}K，共 {released.size}K。",
                    job_name,
                    start=released.start,
                    size=released.size,
                    merged=merged,
                    merge_message=merge_message,
                )

        return OperationResult(False, f"释放失败：{job_name} 在当前算法中不存在或未分配成功。", job_name)

    def merge_free_blocks(self) -> Tuple[bool, str]:
        # 合并所有相邻的空闲分区。
        if not self.free_list:
            return False, ""

        blocks = sorted((FreeBlock(block.start, block.size) for block in self.free_list), key=lambda block: block.start)
        merged_blocks: List[FreeBlock] = [blocks[0]]
        merge_details: List[str] = []

        for block in blocks[1:]:
            last = merged_blocks[-1]
            if last.start + last.size == block.start:
                old_start = last.start
                old_size = last.size
                last.size += block.size
                merge_details.append(
                    f"[{old_start}K, {old_size}K] 与 [{block.start}K, {block.size}K] 合并为 [{last.start}K, {last.size}K]"
                )
            elif last.start + last.size > block.start:
                # This should not appear in normal use, but keeping it stable avoids corrupt displays.
                new_end = max(last.start + last.size, block.start + block.size)
                last.size = new_end - last.start
            else:
                merged_blocks.append(FreeBlock(block.start, block.size))

        self.free_list = merged_blocks
        return bool(merge_details), "；".join(merge_details)

    def get_free_table(self) -> List[Dict[str, int]]:
        # 返回用于界面显示的空闲分区表。
        return [
            {
                "index": index + 1,
                "start": block.start,
                "size": block.size,
                "end": block.end,
            }
            for index, block in enumerate(sorted(self.free_list, key=lambda item: item.start))
        ]

    def get_allocated_table(self) -> List[Dict[str, int]]:
        # 返回用于界面显示的已分配分区表。
        return [
            {
                "job_name": block.job_name,
                "start": block.start,
                "size": block.size,
                "end": block.end,
            }
            for block in sorted(self.allocated_list, key=lambda item: item.start)
        ]

    def get_memory_segments(self) -> List[Dict[str, object]]:
        # 生成内存分布图所需的分区数据。
        segments: List[Dict[str, object]] = []
        for block in self.free_list:
            segments.append(
                {
                    "kind": "free",
                    "name": "空闲",
                    "start": block.start,
                    "size": block.size,
                    "end": block.end,
                }
            )
        for block in self.allocated_list:
            segments.append(
                {
                    "kind": "allocated",
                    "name": block.job_name,
                    "start": block.start,
                    "size": block.size,
                    "end": block.end,
                }
            )
        return sorted(segments, key=lambda item: int(item["start"]))

    def _select_free_block(self, request_size: int) -> Optional[int]:
        # 根据 FF 或 BF 规则选择空闲分区。
        if self.algorithm == "FF":
            self.free_list.sort(key=lambda block: block.start)
            for index, block in enumerate(self.free_list):
                if block.size >= request_size:
                    return index
            return None

        best_index: Optional[int] = None
        best_key: Optional[Tuple[int, int]] = None
        for index, block in enumerate(self.free_list):
            if block.size >= request_size:
                key = (block.size, block.start)
                if best_key is None or key < best_key:
                    best_key = key
                    best_index = index
        return best_index
