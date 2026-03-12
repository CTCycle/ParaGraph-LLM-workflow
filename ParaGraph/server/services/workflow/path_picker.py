from __future__ import annotations

from pathlib import Path


def _build_root():
    try:
        import tkinter as tk
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Native file dialogs are unavailable in this environment") from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    return root


def pick_files(*, multiple: bool) -> list[str]:
    from tkinter import filedialog

    root = _build_root()
    try:
        if multiple:
            selected = filedialog.askopenfilenames(title="Select files for ParaGraph")
            return [str(Path(path).resolve()) for path in selected if path]
        selected = filedialog.askopenfilename(title="Select a file for ParaGraph")
        return [str(Path(selected).resolve())] if selected else []
    finally:
        root.destroy()


def pick_directory() -> str | None:
    from tkinter import filedialog

    root = _build_root()
    try:
        selected = filedialog.askdirectory(title="Select a folder for ParaGraph", mustexist=True)
        if not selected:
            return None
        return str(Path(selected).resolve())
    finally:
        root.destroy()
