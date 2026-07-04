# 基于 Python 与 PyQt5 的动态分区存储管理模拟系统

## 1. 题目要求

本项目要求使用 **Python + PyQt5** 实现一个动态分区存储管理模拟系统，用于模拟操作系统课程中连续内存分配、空闲分区维护、内存申请、内存释放和相邻空闲区合并的过程。

系统需要同时支持并对比展示两种动态分区分配算法：

- FF：首次适应算法 First Fit
- BF：最佳适应算法 Best Fit

用户每执行一次“申请内存”或“释放内存”操作，系统都会让 FF 和 BF 两套算法同时处理同一个操作。两种算法维护的是相互独立的内存状态，因此在多次申请和释放之后，两边可能出现不同的内存布局。界面会分别显示两种算法当前的内存分布图、空闲分区表、已分配分区表和操作日志，便于观察和比较算法差异。

## 2. 开发环境的配置

开发环境：

- 操作系统：Windows 11
- 编程语言：Python 3.10
- GUI 框架：PyQt5
- 开发工具：Visual Studio Code

安装依赖：

```bash
pip install PyQt5
```

如果使用 Anaconda 管理 Python 环境，需要先进入本项目对应的 conda 环境。例如：

```bash
conda activate 你的环境名
```

然后在该环境中安装 PyQt5 和 PyInstaller：

```bash
pip install PyQt5
pip install pyinstaller
```

注意：PyInstaller 必须安装在能够正常运行本项目的 Python/conda 环境中。也就是说，在哪个环境里可以运行 `python main.py`，就应该在哪个环境里安装 PyInstaller 并进行打包。

运行方式：

```bash
python main.py
```

生成 Windows 可执行程序：

```bash
pyinstaller --onefile --windowed --name MemoryManagement main.py
```

或者使用当前环境的 Python 显式调用 PyInstaller：

```bash
python -m PyInstaller --onefile --windowed --name MemoryManagement main.py
```

参数说明：

- `--onefile`：将程序打包成单个 exe 文件。
- `--windowed`：运行 GUI 程序时不显示黑色命令行窗口。
- `--name MemoryManagement`：指定生成的可执行程序名称。
- `main.py`：项目入口文件。

打包完成后，可执行文件位于：

```text
dist/MemoryManagement.exe
```

项目结构：

```text
.
├── main.py            程序入口与 PyQt5 主窗口
├── memory_manager.py  动态分区分配、释放和合并算法
├── memory_bar.py      内存分布图绘制控件
└── README.md          项目说明文档
```

## 3. 具体算法

### 3.1 内存状态的数据结构

本项目使用 `MemoryManager` 类表示某一种算法下的独立内存状态。FF 和 BF 各自拥有一个 `MemoryManager` 实例，它们处理同一组用户操作，但彼此的空闲分区表和已分配分区表互不影响。

核心代码位于 `memory_manager.py`：

```python
class MemoryManager:
    def __init__(self, total_size: int = 640, algorithm: str = "FF") -> None:
        self.algorithm = algorithm.upper()
        self.total_size = 0
        self.free_list: List[FreeBlock] = []
        self.allocated_list: List[AllocatedBlock] = []
        self.reset(total_size)
```

空闲分区使用 `FreeBlock` 保存起始地址和大小，已分配分区使用 `AllocatedBlock` 保存作业名、起始地址和大小。所有地址单位都是 K，内存起始地址从 0 开始。

```python
@dataclass
class FreeBlock:
    start: int
    size: int

@dataclass
class AllocatedBlock:
    job_name: str
    start: int
    size: int
```

### 3.2 初始化与重置算法

程序默认总内存大小为 640K。点击“初始化 / 重置内存”后，系统会清空当前所有作业、清空日志、重新从作业1开始编号，并让 FF 和 BF 都恢复为一个完整空闲区。

核心代码如下：

```python
def reset(self, total_size: int) -> None:
    if total_size <= 0:
        raise ValueError("total_size must be a positive integer")
    self.total_size = total_size
    self.free_list = [FreeBlock(0, total_size)]
    self.allocated_list = []
```

初始化后，空闲分区表中只有一项：

```text
起始地址：0K
分区大小：总内存K
结束地址：总内存 - 1K
```

### 3.3 首次适应算法 FF

首次适应算法从低地址开始扫描空闲分区表，找到第一个大小不小于申请空间的空闲区后立即分配。该算法的特点是查找速度较快，优先使用低地址空间。

核心选择逻辑如下：

```python
if self.algorithm == "FF":
    self.free_list.sort(key=lambda block: block.start)
    for index, block in enumerate(self.free_list):
        if block.size >= request_size:
            return index
```

例如当前空闲区为 `[0K, 100K]`、`[200K, 300K]`，申请 80K 时，FF 会选择第一个满足条件的 `[0K, 100K]`。

### 3.4 最佳适应算法 BF

最佳适应算法会扫描所有空闲分区，从所有大小不小于申请空间的空闲区中选择大小最小的那个。该算法希望每次分配后留下的剩余空间尽量小。

核心选择逻辑如下：

```python
best_index: Optional[int] = None
best_key: Optional[Tuple[int, int]] = None
for index, block in enumerate(self.free_list):
    if block.size >= request_size:
        key = (block.size, block.start)
        if best_key is None or key < best_key:
            best_key = key
            best_index = index
return best_index
```

如果多个空闲区大小相同，则选择起始地址更小的空闲区，保证结果稳定、易于观察。

### 3.5 内存分配算法

当用户输入申请大小并点击“申请内存”时，系统自动生成作业名，例如作业1、作业2、作业3。随后 FF 和 BF 同时尝试为该作业分配内存。

分配规则如下：

1. 如果没有足够大的空闲分区，则分配失败，并在对应算法日志中显示失败原因。
2. 如果空闲分区大小刚好等于申请大小，则删除该空闲分区。
3. 如果空闲分区大于申请大小，则从低地址部分切割给作业，剩余部分仍留在空闲分区表中。

核心代码如下：

```python
free_block = self.free_list[index]
alloc_start = free_block.start
self.allocated_list.append(AllocatedBlock(job_name, alloc_start, request_size))

if free_block.size == request_size:
    del self.free_list[index]
else:
    free_block.start += request_size
    free_block.size -= request_size
```

例如选择的空闲区为 `[100K, 200K]`，申请 60K 后，作业得到 `[100K, 60K]`，原空闲区变为 `[160K, 140K]`。

### 3.6 内存释放算法

释放作业时，系统会分别在 FF 和 BF 的已分配分区表中查找该作业。如果某个算法中该作业不存在，说明它在该算法中未分配成功或已经释放，日志会给出提示，不影响另一个算法继续释放。

核心代码如下：

```python
def release(self, job_name: str) -> OperationResult:
    for index, block in enumerate(self.allocated_list):
        if block.job_name == job_name:
            released = self.allocated_list.pop(index)
            self.free_list.append(FreeBlock(released.start, released.size))
            merged, merge_message = self.merge_free_blocks()
            ...
```

释放出来的分区会先加入空闲分区表，然后调用空闲区合并算法。

### 3.7 空闲区合并算法

空闲区合并是本项目的关键步骤。释放内存后，系统先按照起始地址从小到大排序空闲分区表，再依次检查相邻空闲区是否可以合并。

合并条件如下：

```text
当前空闲区.start + 当前空闲区.size == 下一个空闲区.start
```

如果条件成立，则说明两个空闲区在地址上相邻，应合并成一个更大的空闲区。

核心代码如下：

```python
blocks = sorted(self.free_list, key=lambda block: block.start)
merged_blocks = [blocks[0]]

for block in blocks[1:]:
    last = merged_blocks[-1]
    if last.start + last.size == block.start:
        last.size += block.size
    else:
        merged_blocks.append(block)
```

例如：

```text
[0K, 100K] 和 [100K, 60K] 合并为 [0K, 160K]
```

如果释放区前后都能合并，系统也会连续合并成一个完整的大空闲区。

### 3.8 示例任务执行算法

系统内置了一组示例任务，方便课堂演示。点击“加载示例任务序列”只会准备任务，不会立即执行。点击“单步执行”时，每次执行一条任务；点击“一键执行全部”时，自动执行剩余全部任务。

示例任务以题目给出的 11 步任务为主体，并在末尾追加了三步用于更直观地观察 FF 和 BF 的差异：

```text
释放作业7
释放作业6
申请 80K
```

追加步骤执行后，FF 会优先选择低地址处的空闲区，而 BF 会选择更适合申请大小的空闲区，因此两种算法的分配位置会出现明显差异。

## 4. 功能

本系统实现了以下功能：

- 支持设置总内存大小，默认总内存为 640K。
- 支持初始化和重置内存状态。
- 支持用户手动输入申请空间大小。
- 作业名由系统自动生成，不需要用户手动输入。
- FF 和 BF 两套算法同时处理同一组申请和释放操作。
- FF 和 BF 分别维护独立的空闲分区表和已分配分区表。
- 支持从下拉框选择作业并释放。
- 释放后自动按起始地址排序空闲分区。
- 释放后自动合并相邻空闲分区。
- 支持显示 FF 和 BF 的横向内存分布图。
- 支持显示空闲分区表，字段包括序号、起始地址、分区大小、结束地址。
- 支持显示已分配分区表，字段包括作业名、起始地址、分区大小、结束地址。
- 支持分别显示 FF 和 BF 的操作日志。
- 支持加载示例任务序列、单步执行和一键执行全部。
- 支持输入校验，例如空输入、非正整数、申请空间大于总内存、未选择释放作业等。
- 当分区太小时，内存条会自动省略文字，避免界面文字重叠；完整信息仍可在表格中查看。

## 5. 演示方法

下面是一套完整的课堂演示流程。总内存保持默认 `640K`，点击“初始化 / 重置内存”后，按顺序执行以下操作。

### 5.1 操作步骤

(1) 申请内存给作业1：`100K`。

(2) 申请内存给作业2：`200K`。

(3) 申请内存给作业3：`50K`。

(4) 申请内存给作业4：`100K`。

执行到这里时，作业分布为：

```text
作业1：0-99K
作业2：100-299K
作业3：300-349K
作业4：350-449K
空闲区：450-639K，大小 190K
```

(5) 释放作业2。

释放后产生两个空闲区：

```text
空闲区1：100-299K，大小 200K
空闲区2：450-639K，大小 190K
```

(6) 申请内存给作业5：`180K`。

此时 FF 和 BF 会出现不同结果：

```text
FF：作业5 分配到 100-279K
BF：作业5 分配到 450-629K
```

原因是 FF 选择第一个能容纳 `180K` 的空闲区 `100-299K`，BF 选择大小更合适的空闲区 `450-639K`。

(7) 释放作业5。

释放后相邻空闲区会自动合并：

```text
FF：100-279K 与 280-299K 合并为 100-299K
BF：450-629K 与 630-639K 合并为 450-639K
```

(8) 释放作业3。

释放后 `300-349K` 与前面的 `100-299K` 相邻，会合并为：

```text
空闲区：100-349K，大小 250K
```

(9) 释放作业4。

释放后 `350-449K` 前后都与空闲区相邻，最终合并为：

```text
空闲区：100-639K，大小 540K
```

(10) 申请内存给作业6：`500K`。

此时作业6 可以成功分配到合并后的大空闲区：

```text
作业6：100-599K
剩余空闲区：600-639K，大小 40K
```

### 5.2 演示结论

通过这一整套操作可以观察到：

1. 动态分区分配会按照作业申请大小动态切割空闲区。
2. 作业释放后会重新形成空闲分区。
3. FF 从低地址开始选择第一个满足要求的空闲区。
4. BF 会选择所有满足要求的空闲区中大小最合适的一个。
5. 相同操作序列下，FF 和 BF 可能产生不同的内存布局。
6. 释放分区后必须合并相邻空闲区，否则会影响后续大作业的分配。
