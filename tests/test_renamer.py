from __future__ import annotations

import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import renamer  # noqa: E402


class ReverseRng:
    """可预测的洗牌器：把顺序整个翻过来。"""

    def shuffle(self, seq):  # noqa: D401 - 测试替身
        seq.reverse()


def touch(folder: Path, name: str, content: bytes = b"x") -> Path:
    path = folder / name
    path.write_bytes(content)
    return path


class ParseTest(unittest.TestCase):
    def test_half_width(self):
        video = renamer.parse(Path("张三(1).mp4"))
        self.assertEqual(video.prefix, "张三")
        self.assertEqual(video.number, "1")
        self.assertEqual(video.target_name(7), "张三(7).mp4")

    def test_full_width_and_padding(self):
        video = renamer.parse(Path("李四（02）.MOV"))
        self.assertEqual((video.left, video.right), ("（", "）"))
        self.assertEqual(video.number, "02")
        self.assertEqual(video.target_name(3, width=2), "李四（03）.MOV")

    def test_prefix_keeps_trailing_space(self):
        video = renamer.parse(Path("王五 (3).mov"))
        self.assertEqual(video.prefix, "王五 ")
        self.assertEqual(video.target_name(4), "王五 (4).mov")

    def test_number_widens_when_needed(self):
        video = renamer.parse(Path("赵六(9).mp4"))
        self.assertEqual(video.target_name(12), "赵六(12).mp4")

    def test_non_matching_names(self):
        for name in ["花絮.mp4", "花絮(最终版).mp4", "封面.jpg", "无序号.mp4"]:
            self.assertIsNone(renamer.parse(Path(name)), name)


class ScanTest(unittest.TestCase):
    def test_scan_splits_matching_and_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            touch(folder, "甲(1).mp4")
            touch(folder, "乙(2).mp4")
            touch(folder, "花絮.mp4")
            touch(folder, "封面.png")
            (folder / "子目录").mkdir()
            touch(folder, ".vrn-abcd.mp4")

            matched, skipped = renamer.scan(folder)
            self.assertEqual(sorted(v.path.name for v in matched), ["乙(2).mp4", "甲(1).mp4"])
            self.assertEqual([p.name for p in skipped], ["花絮.mp4"])


class PlanTest(unittest.TestCase):
    def test_numbers_follow_new_order_and_prefix_stays(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            touch(folder, "a(1).mp4")
            touch(folder, "b(2).mp4")
            touch(folder, "c(3).mp4")

            plan = renamer.build_plan(folder, rng=ReverseRng())
            mapping = {old.name: new for old, new in plan.renames}
            self.assertEqual(mapping["c(3).mp4"], "c(1).mp4")
            self.assertEqual(mapping["b(2).mp4"], "b(2).mp4")
            self.assertEqual(mapping["a(1).mp4"], "a(3).mp4")

    def test_padding_follows_each_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            touch(folder, "x(01).mp4")
            touch(folder, "y(02).mp4")
            touch(folder, "z(03).mp4")

            plan = renamer.build_plan(folder, rng=ReverseRng())
            mapping = {old.name: new for old, new in plan.renames}
            self.assertEqual(mapping["z(03).mp4"], "z(01).mp4")
            self.assertEqual(mapping["x(01).mp4"], "x(03).mp4")

    def test_random_numbering_with_start_offset(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            touch(folder, "a(1).mp4")
            touch(folder, "b(2).mp4")
            touch(folder, "c(3).mp4")

            plan = renamer.build_plan(folder, rng=ReverseRng(), start=5)
            mapping = {old.name: new for old, new in plan.renames}
            self.assertEqual(mapping["c(3).mp4"], "c(5).mp4")
            self.assertEqual(mapping["b(2).mp4"], "b(6).mp4")
            self.assertEqual(mapping["a(1).mp4"], "a(7).mp4")

    def test_padding_accounts_for_start_offset(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for i in range(1, 4):
                touch(folder, f"p{i}({i:02d}).mp4")

            plan = renamer.build_plan(folder, rng=ReverseRng(), start=8)
            mapping = {old.name: new for old, new in plan.renames}
            self.assertEqual(mapping["p3(03).mp4"], "p3(08).mp4")
            self.assertEqual(mapping["p2(02).mp4"], "p2(09).mp4")
            self.assertEqual(mapping["p1(01).mp4"], "p1(10).mp4")

    def test_mixed_widths_are_natural_not_padded(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for i in range(1, 13):
                touch(folder, f"p{i}({i}).mp4")

            plan = renamer.build_plan(folder, rng=ReverseRng())
            mapping = {old.name: new for old, new in plan.renames}
            self.assertEqual(mapping["p1(1).mp4"], "p1(12).mp4")
            self.assertEqual(mapping["p2(2).mp4"], "p2(11).mp4")
            self.assertEqual(mapping["p12(12).mp4"], "p12(1).mp4")


class UnifyTest(unittest.TestCase):
    def test_all_videos_renamed_in_natural_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            touch(folder, "x10.mp4", b"TEN")
            touch(folder, "x2.mp4", b"TWO")
            touch(folder, "随意名.mov", b"ANY")
            touch(folder, "封面.jpg", b"IMG")
            (folder / "子目录").mkdir()
            touch(folder / "子目录", "内层.mp4", b"NESTED")

            plan = renamer.build_unify_plan(folder, "橘子")
            mapping = {old.name: new for old, new in plan.renames}

            self.assertEqual(plan.total, 3)
            self.assertEqual(mapping["x2.mp4"], "橘子（1）.mp4")
            self.assertEqual(mapping["x10.mp4"], "橘子（2）.mp4")
            self.assertEqual(mapping["随意名.mov"], "橘子（3）.mov")

    def test_unify_with_start_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            touch(folder, "a.mp4")
            touch(folder, "b.mp4")

            plan = renamer.build_unify_plan(folder, "橘子", start=5)
            self.assertEqual(sorted(new for _, new in plan.renames),
                             ["橘子（5）.mp4", "橘子（6）.mp4"])

    def test_unify_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for i in range(1, 4):
                touch(folder, f"任意{i}.mp4", bytes([i]))

            renamer.apply_renames(renamer.build_unify_plan(folder, "橘子").renames)
            second = renamer.build_unify_plan(folder, "橘子")
            result = renamer.apply_renames(second.renames)

            self.assertEqual(result.renamed, 0)
            self.assertEqual(result.unchanged, 3)
            self.assertEqual(sorted(p.name for p in folder.iterdir()),
                             ["橘子（1）.mp4", "橘子（2）.mp4", "橘子（3）.mp4"])

    def test_unify_applies_with_content_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            touch(folder, "x2.mp4", b"TWO")
            touch(folder, "x10.mp4", b"TEN")

            result = renamer.apply_renames(renamer.build_unify_plan(folder, "橘子").renames)

            self.assertEqual(result.renamed, 2)
            self.assertEqual((folder / "橘子（1）.mp4").read_bytes(), b"TWO")
            self.assertEqual((folder / "橘子（2）.mp4").read_bytes(), b"TEN")


class SpreadOrderTest(unittest.TestCase):
    @staticmethod
    def preserved_adjacencies(order):
        return [(order[i], order[i + 1]) for i in range(len(order) - 1)
                if abs(order[i] - order[i + 1]) == 1]

    def test_no_original_neighbour_stays_neighbour(self):
        for seed in range(10):
            items = list(range(12))
            order = renamer.spread_order(items, random.Random(seed))
            self.assertEqual(sorted(order), items)
            self.assertEqual(self.preserved_adjacencies(order), [], f"seed={seed}")

    def test_small_sets_are_best_effort(self):
        # 3 个元素无论怎么排，都至少有一对原相邻元素仍然相邻
        items = list(range(3))
        order = renamer.spread_order(items, random.Random(1))
        self.assertEqual(sorted(order), items)
        self.assertEqual(len(self.preserved_adjacencies(order)), 1)

    def test_plan_uses_spread_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for i in range(1, 13):
                touch(folder, f"橘子（{i}）.mp4")

            plan = renamer.build_plan(folder, rng=random.Random(3))
            new_number = {old.name: int(new.split("（")[1].split("）")[0])
                          for old, new in plan.renames}
            for i in range(1, 12):
                self.assertNotEqual(
                    abs(new_number[f"橘子（{i}）.mp4"] - new_number[f"橘子（{i + 1}）.mp4"]),
                    1,
                    f"{i} 与 {i + 1} 仍然相邻",
                )
            self.assertEqual(sorted(new_number.values()), list(range(1, 13)))


class ApplyTest(unittest.TestCase):
    def test_content_follows_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            touch(folder, "a(1).mp4", b"AAA")
            touch(folder, "b(2).mp4", b"BBB")
            touch(folder, "c(3).mp4", b"CCC")

            plan = renamer.build_plan(folder, rng=ReverseRng())
            result = renamer.apply_renames(plan.renames)

            self.assertEqual(result.renamed, 2)
            self.assertEqual(result.unchanged, 1)
            self.assertEqual((folder / "a(3).mp4").read_bytes(), b"AAA")
            self.assertEqual((folder / "c(1).mp4").read_bytes(), b"CCC")
            self.assertEqual(sorted(p.name for p in folder.iterdir()),
                             ["a(3).mp4", "b(2).mp4", "c(1).mp4"])

    def test_same_prefix_swap_is_not_treated_as_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            touch(folder, "A(1).mp4", b"ONE")
            touch(folder, "A(2).mp4", b"TWO")

            plan = renamer.build_plan(folder, rng=ReverseRng())
            result = renamer.apply_renames(plan.renames)

            self.assertEqual(result.renamed, 2)
            self.assertEqual((folder / "A(1).mp4").read_bytes(), b"TWO")
            self.assertEqual((folder / "A(2).mp4").read_bytes(), b"ONE")

    def test_existing_target_aborts_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            a = touch(folder, "a.mp4", b"A")
            touch(folder, "b.mp4", b"B")
            touch(folder, "c.mp4", b"C")

            with self.assertRaises(renamer.RenameError):
                renamer.apply_renames([(a, "x.mp4"), (folder / "b.mp4", "c.mp4")])

            self.assertEqual(a.read_bytes(), b"A")
            self.assertTrue((folder / "b.mp4").exists())
            self.assertEqual(sorted(p.name for p in folder.iterdir()),
                             ["a.mp4", "b.mp4", "c.mp4"])

    def test_undo_restores_original_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            touch(folder, "a(1).mp4")
            touch(folder, "b(2).mp4")
            touch(folder, "c(3).mp4")

            plan = renamer.build_plan(folder, rng=ReverseRng())
            renamer.apply_renames(plan.renames)

            reverse = [(folder / new, old.name) for old, new in plan.renames]
            renamer.apply_renames(reverse)

            self.assertEqual(sorted(p.name for p in folder.iterdir()),
                             ["a(1).mp4", "b(2).mp4", "c(3).mp4"])

    def test_no_leftover_temp_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for i in range(1, 6):
                touch(folder, f"p{i}({i}).mp4")

            plan = renamer.build_plan(folder, rng=ReverseRng())
            renamer.apply_renames(plan.renames)

            leftovers = [p.name for p in folder.iterdir() if p.name.startswith(".vrn-")]
            self.assertEqual(leftovers, [])
            self.assertEqual(len(list(folder.iterdir())), 5)


if __name__ == "__main__":
    unittest.main()
