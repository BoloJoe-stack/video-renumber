"""核心逻辑：识别「名称(序号)」形式的视频文件，打乱顺序后按新顺序重新编号。

约定：
- 只处理选定文件夹的顶层文件，不递归子目录。
- 只处理视频扩展名。
- 文件名形如「张三(1).mp4」「李四（02）.mov」，括号可为半角或全角，括号前的内容原样保留。
- 重命名采用两阶段（先改临时名，再改目标名），避免同名互相覆盖。
"""

from __future__ import annotations

import random
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

VIDEO_EXTS = frozenset({
    ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".m4v", ".webm",
    ".mpg", ".mpeg", ".ts", ".mts", ".m2ts", ".3gp", ".rmvb", ".rm",
})

# 前缀非贪婪 + 结尾锚定：文件名中若出现多组括号，以最后一组数字括号为序号。
NAME_RE = re.compile(r"^(?P<prefix>.*?)(?P<lp>[（(])(?P<num>\d+)(?P<rp>[)）])$")


class RenameError(RuntimeError):
    """重命名无法安全执行（同名冲突、目标已存在等）。"""


@dataclass(frozen=True)
class VideoFile:
    path: Path
    prefix: str
    left: str
    number: str
    right: str
    suffix: str

    def target_name(self, n: int, width: int | None = None) -> str:
        """返回序号为 n 时的目标文件名。width 为补零位宽，0/None 表示不补零。"""
        width = max(width or 0, len(str(n)))
        return f"{self.prefix}{self.left}{str(n).zfill(width)}{self.right}{self.suffix}"


@dataclass
class Plan:
    folder: Path
    renames: list[tuple[Path, str]] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.renames)


@dataclass
class ApplyResult:
    renamed: int
    unchanged: int


def parse(path: Path) -> VideoFile | None:
    """解析单个文件；非视频或不符合「名称(序号)」时返回 None。"""
    if path.suffix.lower() not in VIDEO_EXTS:
        return None
    m = NAME_RE.match(path.stem)
    if m is None:
        return None
    return VideoFile(
        path=path,
        prefix=m.group("prefix"),
        left=m.group("lp"),
        number=m.group("num"),
        right=m.group("rp"),
        suffix=path.suffix,
    )


def scan(folder: Path) -> tuple[list[VideoFile], list[Path]]:
    """返回（可参与重编号的视频, 不符合格式的视频）。"""
    matched: list[VideoFile] = []
    skipped: list[Path] = []
    for entry in sorted(Path(folder).iterdir(), key=lambda p: natural_key(p.name)):
        if not entry.is_file() or entry.name.startswith(".vrn-"):
            continue
        video = parse(entry)
        if video is not None:
            matched.append(video)
        elif entry.suffix.lower() in VIDEO_EXTS:
            skipped.append(entry)
    return matched, skipped


def natural_key(text: str) -> list[tuple[int, object]]:
    """自然排序键：让 2 排在 10 前面。"""
    return [
        (1, int(part)) if part.isdigit() else (0, part.lower())
        for part in re.split(r"(\d+)", text)
        if part
    ]


def list_videos(folder: Path) -> list[Path]:
    """列出顶层全部视频文件（不要求符合「名称(序号)」格式），按自然顺序排列。"""
    videos = [
        entry
        for entry in Path(folder).iterdir()
        if entry.is_file()
        and entry.suffix.lower() in VIDEO_EXTS
        and not entry.name.startswith(".vrn-")
    ]
    return sorted(videos, key=lambda p: natural_key(p.name))


def build_unify_plan(folder: Path, name: str, start: int = 1) -> Plan:
    """把顶层全部视频统一命名为「人名（序号）」，序号按现有文件名自然顺序分配。"""
    folder = Path(folder)
    videos = list_videos(folder)
    renames = [
        (path, f"{name}（{number}）{path.suffix}")
        for number, path in enumerate(videos, start)
    ]
    _check_collisions(folder, renames)
    return Plan(folder=folder, renames=renames, skipped=[])


def spread_order(items: list, rng: random.Random) -> list:
    """随机打散顺序，尽量不让原本相邻的两个元素在新顺序里仍然相邻。

    做法：重复洗牌，取第一份「原相邻对全部被打散」的结果；若多轮都做不到
    （如只有 3 个元素时数学上无解），取相邻对数最少的那份。
    """
    n = len(items)
    if n < 3:
        result = list(items)
        rng.shuffle(result)
        return result

    origin = list(range(n))
    best_order = None
    best_score = n
    for _ in range(200):
        order = list(origin)
        rng.shuffle(order)
        score = sum(1 for a, b in zip(order, order[1:]) if abs(a - b) == 1)
        if score < best_score:
            best_order, best_score = order, score
            if score == 0:
                break
    return [items[i] for i in best_order]


def build_plan(folder: Path, rng: random.Random | None = None, start: int = 1) -> Plan:
    """扫描目录并生成随机顺序的重命名计划。rng 仅用于测试注入。"""
    folder = Path(folder)
    files, skipped = scan(folder)
    order = spread_order(list(files), rng or random.SystemRandom())
    width = _number_width(files, max(start + len(order) - 1, 0))
    renames = [
        (video.path, video.target_name(start + i, width))
        for i, video in enumerate(order)
    ]
    _check_collisions(folder, renames)
    return Plan(folder=folder, renames=renames, skipped=skipped)


def _number_width(files: list[VideoFile], last_number: int) -> int:
    """原始编号位宽统一（如 01…12）则沿用；混用（如 1…12）视为自然编号，不补零。"""
    widths = {len(video.number) for video in files}
    if len(widths) != 1:
        return 0
    return max(widths.pop(), len(str(last_number)))


def _check_collisions(folder: Path, renames: list[tuple[Path, str]]) -> None:
    targets: set[str] = set()
    for _, new_name in renames:
        key = new_name.casefold()
        if key in targets:
            raise RenameError(f"重命名后会出现同名文件：{new_name}")
        targets.add(key)

    renaming = {old.name.casefold() for old, _ in renames}
    for entry in folder.iterdir():
        if not entry.is_file():
            continue
        if entry.name.casefold() in renaming:
            continue
        if entry.name.casefold() in targets:
            raise RenameError(f"目标文件名已被目录内其他文件占用：{entry.name}")


def apply_renames(renames: list[tuple[Path, str]]) -> ApplyResult:
    """按 (原路径, 新文件名) 列表执行两阶段重命名；失败时尽力回滚。"""
    staged: list[tuple[Path, Path, Path]] = []  # (原路径, 临时路径, 目标路径)
    unchanged = 0
    # 目标名若正是本次计划中某个源文件的现名，属正常换位，不算冲突。
    sources = {old.resolve() for old, _ in renames}
    try:
        for old_path, new_name in renames:
            if old_path.name == new_name:
                unchanged += 1
                continue
            target = old_path.with_name(new_name)
            if target.exists() and target.resolve() not in sources:
                raise RenameError(f"目标文件已存在：{target.name}")
            temp = old_path.with_name(f".vrn-{uuid.uuid4().hex}{old_path.suffix}")
            old_path.rename(temp)
            staged.append((old_path, temp, target))
    except Exception:
        _restore(staged)
        raise

    try:
        for _, temp, target in staged:
            temp.rename(target)
    except Exception:
        for _, temp, target in reversed(staged):
            if target.exists() and not temp.exists():
                _safe_rename(target, temp)
        _restore(staged)
        raise

    missing = [target for _, _, target in staged if not target.exists()]
    if missing:
        raise RenameError(f"重命名后校验失败，缺少文件：{missing[0].name}")
    return ApplyResult(renamed=len(staged), unchanged=unchanged)


def _restore(staged: list[tuple[Path, Path, Path]]) -> None:
    for old_path, temp, _ in reversed(staged):
        if temp.exists():
            _safe_rename(temp, old_path)


def _safe_rename(src: Path, dst: Path) -> None:
    try:
        if not dst.exists():
            src.rename(dst)
    except OSError:
        pass
