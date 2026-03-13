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


DEFAULT_JSON_FILE_TYPES: tuple[tuple[str, str], ...] = (
    ("JSON files", "*.json"),
    ("All files", "*.*"),
)


def _normalize_initial_directory(initial_directory: str | Path | None) -> str:
    if initial_directory is None:
        return str(Path.home())
    path = Path(initial_directory).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


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


def pick_open_file(
    *,
    title: str,
    initial_directory: str | Path | None = None,
    file_types: tuple[tuple[str, str], ...] = DEFAULT_JSON_FILE_TYPES,
) -> str | None:
    from tkinter import filedialog

    root = _build_root()
    try:
        selected = filedialog.askopenfilename(
            title=title,
            initialdir=_normalize_initial_directory(initial_directory),
            filetypes=file_types,
        )
        if not selected:
            return None
        return str(Path(selected).resolve())
    finally:
        root.destroy()


def pick_save_file(
    *,
    title: str,
    initial_directory: str | Path | None = None,
    initial_file_name: str = "",
    file_types: tuple[tuple[str, str], ...] = DEFAULT_JSON_FILE_TYPES,
    default_extension: str = ".json",
) -> str | None:
    from tkinter import filedialog

    root = _build_root()
    try:
        selected = filedialog.asksaveasfilename(
            title=title,
            initialdir=_normalize_initial_directory(initial_directory),
            initialfile=initial_file_name,
            filetypes=file_types,
            defaultextension=default_extension,
        )
        if not selected:
            return None
        path = Path(selected).expanduser()
        return str(path.resolve())
    finally:
        root.destroy()
