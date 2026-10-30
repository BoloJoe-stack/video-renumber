"""视频随机编号 —— 小挂件式图形界面。"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import renamer
import storage

BG = "#f6f7f9"
FG = "#1f2328"
MUTED = "#6b7280"
ACCENT = "#2f6bff"
ACCENT_ACTIVE = "#1f57d6"
SUCCESS = "#1a7f37"
DANGER = "#c0392b"

FONT = ("Microsoft YaHei UI", 9)
FONT_SMALL = ("Microsoft YaHei UI", 8)
FONT_BOLD = ("Microsoft YaHei UI", 9, "bold")
FONT_TITLE = ("Microsoft YaHei UI", 12, "bold")

INVALID_NAME_CHARS = set('<>:"/\\|?*')


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        config = storage.load_config()
        self.folders: list[str] = config["folders"]
        self.selected: str | None = config["selected"]
        self.names: dict[str, str] = config["names"]
        self.start_value: int = config["start"]
        self._refreshing = False
        self._build_ui()
        self._refresh_list()
        self.name_var.set(self.names.get(self.selected or "", ""))
        if not self.folders:
            # 首次打开直接弹出选择框，符合「打开后先选定文件夹」的使用顺序。
            self.root.after(200, self.on_add)

    # ---------- 界面 ----------

    def _build_ui(self) -> None:
        self.root.title("视频随机编号")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=16, pady=14)

        tk.Label(main, text="视频随机编号", font=FONT_TITLE, bg=BG, fg=FG).pack(anchor="w")
        tk.Label(
            main,
            text="统一命名为「人名（序号）」，或打乱顺序重新编号",
            font=FONT_SMALL,
            bg=BG,
            fg=MUTED,
        ).pack(anchor="w", pady=(2, 12))

        tk.Label(main, text="文件夹", font=FONT_BOLD, bg=BG, fg=FG).pack(anchor="w", pady=(0, 4))

        list_frame = tk.Frame(main, bg="white", highlightbackground="#d9dde3", highlightthickness=1)
        list_frame.pack(fill="both", expand=True)

        self.listbox = tk.Listbox(
            list_frame,
            height=7,
            font=FONT,
            bg="white",
            fg=FG,
            bd=0,
            highlightthickness=0,
            activestyle="none",
            selectmode="browse",
            exportselection=False,
            selectbackground="#dbe7ff",
            selectforeground=FG,
        )
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        scrollbar.pack(side="right", fill="y", pady=4, padx=(0, 2))

        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        self.listbox.bind("<Double-Button-1>", self._open_folder)

        buttons = tk.Frame(main, bg=BG)
        buttons.pack(fill="x", pady=(8, 14))
        self._flat_button(buttons, "添加文件夹", self.on_add).pack(side="left")
        self._flat_button(buttons, "删除", self.on_delete).pack(side="left", padx=(8, 0))

        name_row = tk.Frame(main, bg=BG)
        name_row.pack(fill="x", pady=(0, 12))
        tk.Label(name_row, text="人名", font=FONT_BOLD, bg=BG, fg=FG).pack(side="left")
        self.name_var = tk.StringVar()
        self.name_entry = tk.Entry(
            name_row,
            textvariable=self.name_var,
            font=FONT,
            bg="white",
            fg=FG,
            relief="solid",
            bd=1,
            highlightthickness=0,
            insertbackground=FG,
        )
        self.name_entry.pack(side="left", fill="x", expand=True, padx=(12, 16), ipady=4)
        self.name_entry.bind("<KeyRelease>", self._on_name_edit)
        self.name_entry.bind("<Return>", lambda _event: self.on_unify())

        tk.Label(name_row, text="起始序号", font=FONT_BOLD, bg=BG, fg=FG).pack(side="left")
        self.start_var = tk.StringVar(value=str(self.start_value))
        self.start_entry = tk.Entry(
            name_row,
            textvariable=self.start_var,
            font=FONT,
            bg="white",
            fg=FG,
            relief="solid",
            bd=1,
            width=5,
            justify="center",
            highlightthickness=0,
            insertbackground=FG,
        )
        self.start_entry.pack(side="left", padx=(8, 0), ipady=4)
        self.start_entry.bind("<KeyRelease>", self._on_start_edit)

        actions = tk.Frame(main, bg=BG)
        actions.pack(fill="x", pady=(0, 10))
        self.unify_button = self._flat_button(actions, "统一命名", self.on_unify)
        self.unify_button.configure(font=("Microsoft YaHei UI", 10, "bold"), pady=8)
        self.unify_button.pack(side="left", fill="x", expand=True)
        self.start_button = tk.Button(
            actions,
            text="开始随机编号",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=ACCENT,
            fg="white",
            activebackground=ACCENT_ACTIVE,
            activeforeground="white",
            bd=0,
            pady=8,
            cursor="hand2",
            command=self.on_start,
        )
        self.start_button.pack(side="left", fill="x", expand=True, padx=(10, 0))

        bottom = tk.Frame(main, bg=BG)
        bottom.pack(fill="x")
        self.status = tk.Label(
            bottom,
            text="",
            font=FONT,
            bg=BG,
            fg=MUTED,
            justify="left",
            anchor="w",
            wraplength=330,
            height=2,
        )
        self.status.pack(side="left", fill="x", expand=True)
        self.undo_button = tk.Button(
            bottom,
            text="撤销上次",
            font=FONT_SMALL,
            bg=BG,
            fg=MUTED,
            activebackground=BG,
            activeforeground=FG,
            bd=0,
            cursor="hand2",
            command=self.on_undo,
        )
        self.undo_button.pack(side="right", anchor="s", pady=(0, 4))

        self.root.update_idletasks()
        width = 460
        height = self.root.winfo_reqheight()
        x = (self.root.winfo_screenwidth() - width) // 2
        y = (self.root.winfo_screenheight() - height) // 3
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    @staticmethod
    def _flat_button(parent: tk.Misc, text: str, command) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            font=FONT,
            bg="white",
            fg=FG,
            activebackground="#eef1f6",
            activeforeground=FG,
            relief="solid",
            bd=1,
            padx=10,
            pady=3,
            cursor="hand2",
            command=command,
        )

    # ---------- 列表状态 ----------

    def _refresh_list(self) -> None:
        self._refreshing = True
        try:
            self.listbox.delete(0, "end")
            selected_index = None
            for i, folder in enumerate(self.folders):
                marker = "" if Path(folder).is_dir() else "    （路径不存在）"
                self.listbox.insert("end", f" {folder}{marker}")
                if folder == self.selected:
                    selected_index = i
            if selected_index is not None:
                self.listbox.selection_set(selected_index)
                self.listbox.see(selected_index)
        finally:
            self._refreshing = False

    def _select_index(self) -> int | None:
        selection = self.listbox.curselection()
        return int(selection[0]) if selection else None

    def _on_select(self, _event=None) -> None:
        if self._refreshing:
            return
        index = self._select_index()
        if index is None or index >= len(self.folders):
            return
        folder = self.folders[index]
        if folder == self.selected:
            return
        self._store_name()
        self.selected = folder
        self.name_var.set(self.names.get(folder, ""))
        self._save_config()

    def _store_name(self) -> None:
        if self.selected:
            self.names[self.selected] = self.name_var.get().strip()

    def _on_name_edit(self, _event=None) -> None:
        self._store_name()
        self._save_config()

    def _on_start_edit(self, _event=None) -> None:
        value = self._read_start()
        if value is not None:
            self.start_value = value
            self._save_config()

    def _read_start(self) -> int | None:
        raw = self.start_var.get().strip()
        return int(raw) if raw.isdigit() else None

    def _save_config(self) -> None:
        storage.save_config(self.folders, self.selected, self.names, self.start_value)

    def _set_status(self, text: str, color: str = MUTED) -> None:
        self.status.configure(text=text, fg=color)

    # ---------- 操作 ----------

    def on_add(self) -> None:
        self._store_name()
        initial = self.selected if self.selected and Path(self.selected).is_dir() else str(Path.home())
        chosen = filedialog.askdirectory(
            parent=self.root, title="选择视频所在文件夹", initialdir=initial, mustexist=True
        )
        if not chosen:
            return
        folder = str(Path(chosen))
        if folder not in self.folders:
            self.folders.append(folder)
        self.selected = folder
        self.name_var.set(self.names.get(folder, ""))
        self._save_config()
        self._refresh_list()
        self._set_status("")

    def on_delete(self) -> None:
        index = self._select_index()
        if index is None or index >= len(self.folders):
            return
        removed = self.folders.pop(index)
        self.names.pop(removed, None)
        if self.selected == removed:
            self.selected = self.folders[min(index, len(self.folders) - 1)] if self.folders else None
            self.name_var.set(self.names.get(self.selected or "", ""))
        self._save_config()
        self._refresh_list()
        self._set_status("")

    def _open_folder(self, _event=None) -> None:
        index = self._select_index()
        if index is None or index >= len(self.folders):
            return
        folder = self.folders[index]
        if Path(folder).is_dir():
            os.startfile(folder)  # noqa: S606 - Windows 资源管理器

    def on_unify(self) -> None:
        folder = self.selected
        if not folder:
            messagebox.showinfo("提示", "请先添加并选择一个文件夹。", parent=self.root)
            return
        path = Path(folder)
        if not path.is_dir():
            messagebox.showerror("失败", "所选文件夹不存在，请重新选择。", parent=self.root)
            self._set_status("失败：文件夹不存在。", DANGER)
            return

        name = self.name_var.get().strip()
        self._store_name()
        self._save_config()
        if not name:
            messagebox.showinfo("提示", "请先在「人名」中填写名字。", parent=self.root)
            self.name_entry.focus_set()
            return
        if any(ch in INVALID_NAME_CHARS for ch in name) or name.endswith((".", " ")):
            messagebox.showerror(
                "失败",
                '人名不能包含这些字符：< > : " / \\ | ? *，也不能以句点或空格结尾。',
                parent=self.root,
            )
            return

        start = self._read_start()
        if start is None:
            messagebox.showerror("失败", "起始序号必须是 0 或正整数。", parent=self.root)
            self.start_entry.focus_set()
            return
        self.start_value = start
        self._save_config()

        try:
            plan = renamer.build_unify_plan(path, name, start)
        except renamer.RenameError as exc:
            messagebox.showerror("失败", str(exc), parent=self.root)
            self._set_status(f"失败：{exc}", DANGER)
            return
        except OSError as exc:
            messagebox.showerror("失败", f"无法读取文件夹：{exc}", parent=self.root)
            self._set_status("失败：无法读取文件夹。", DANGER)
            return

        if plan.total == 0:
            messagebox.showinfo("提示", "该文件夹内没有视频文件。", parent=self.root)
            self._set_status("没有可处理的视频文件。", DANGER)
            return

        self.unify_button.configure(state="disabled")
        self.root.update_idletasks()
        try:
            result = renamer.apply_renames(plan.renames)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(
                "失败", f"统一命名失败，已尽量回滚到操作前状态。\n\n{exc}", parent=self.root
            )
            self._set_status("失败：统一命名未完成，请检查文件夹后重试。", DANGER)
            return
        finally:
            self.unify_button.configure(state="normal")

        if result.renamed:
            storage.record_history(folder, [(old.name, new) for old, new in plan.renames])
        text = "统一命名成功。"
        self._set_status(text, SUCCESS)
        messagebox.showinfo("成功", text, parent=self.root)

    def on_start(self) -> None:
        folder = self.selected
        if not folder:
            messagebox.showinfo("提示", "请先添加并选择一个文件夹。", parent=self.root)
            return
        path = Path(folder)
        if not path.is_dir():
            messagebox.showerror("失败", "所选文件夹不存在，请重新选择。", parent=self.root)
            self._set_status("失败：文件夹不存在。", DANGER)
            return

        start = self._read_start()
        if start is None:
            messagebox.showerror("失败", "起始序号必须是 0 或正整数。", parent=self.root)
            self.start_entry.focus_set()
            return
        self.start_value = start
        self._save_config()

        try:
            plan = renamer.build_plan(path, start=start)
        except renamer.RenameError as exc:
            messagebox.showerror("失败", str(exc), parent=self.root)
            self._set_status(f"失败：{exc}", DANGER)
            return
        except OSError as exc:
            messagebox.showerror("失败", f"无法读取文件夹：{exc}", parent=self.root)
            self._set_status("失败：无法读取文件夹。", DANGER)
            return

        if plan.total == 0:
            messagebox.showinfo(
                "提示", "该文件夹内没有符合「名称(序号)」格式的视频文件。", parent=self.root
            )
            self._set_status("没有可处理的视频文件。", DANGER)
            return
        if plan.total == 1:
            messagebox.showinfo("提示", "该文件夹只有 1 个视频文件，无需随机排序。", parent=self.root)
            return

        self.start_button.configure(state="disabled")
        self.root.update_idletasks()
        try:
            renamer.apply_renames(plan.renames)
        except Exception as exc:  # noqa: BLE001 - 失败必须如实报给用户
            messagebox.showerror(
                "失败", f"重命名失败，已尽量回滚到操作前状态。\n\n{exc}", parent=self.root
            )
            self._set_status("失败：重命名未完成，请检查文件夹后重试。", DANGER)
            return
        finally:
            self.start_button.configure(state="normal")

        storage.record_history(folder, [(old.name, new) for old, new in plan.renames])
        text = "随机排列成功。"
        self._set_status(text, SUCCESS)
        messagebox.showinfo("成功", text, parent=self.root)

    def on_undo(self) -> None:
        folder = self.selected
        if not folder:
            messagebox.showinfo("提示", "请先添加并选择一个文件夹。", parent=self.root)
            return
        record = storage.load_history(folder)
        if not record:
            messagebox.showinfo("提示", "没有可撤销的操作记录。", parent=self.root)
            return
        pairs = record["pairs"]
        if not messagebox.askyesno(
            "确认撤销",
            f"将把 {len(pairs)} 个文件恢复为上一次操作前的文件名，是否继续？",
            parent=self.root,
        ):
            return

        renames = [(Path(folder) / new_name, old_name) for old_name, new_name in pairs]
        missing = [src.name for src, _ in renames if not src.exists()]
        if missing:
            messagebox.showerror(
                "失败",
                f"以下文件已不在文件夹中，无法撤销：\n\n" + "\n".join(missing[:8]),
                parent=self.root,
            )
            self._set_status("失败：文件已变动，无法撤销。", DANGER)
            return
        try:
            result = renamer.apply_renames(renames)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("失败", f"撤销失败：\n\n{exc}", parent=self.root)
            self._set_status("失败：撤销未完成。", DANGER)
            return

        storage.clear_history(folder)
        text = f"已撤销：{result.renamed} 个文件已恢复原文件名。"
        self._set_status(text, SUCCESS)
        messagebox.showinfo("成功", text, parent=self.root)


def _enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001 - 老系统不支持时忽略
        pass


def main() -> None:
    _enable_dpi_awareness()
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
