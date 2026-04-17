"""PDF 20장씩 자르기 - textbook-pro-editor

사용자가 시작 페이지를 지정하면 그 지점부터 20페이지씩 PDF를 분할한다.
GUI는 tkinter(표준 라이브러리), 분할은 pypdf로 처리한다.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

APP_TITLE = "PDF 20장씩 자르기 v1.0"
CHUNK = 20


def split_pdf(input_path: Path, start_page: int, output_dir: Path,
              progress_cb=None) -> list[Path]:
    """지정 시작 페이지부터 CHUNK(20)장 단위로 PDF를 분할한다.

    Args:
        input_path: 원본 PDF 경로
        start_page: 1-indexed 시작 페이지
        output_dir: 출력 폴더 (없으면 생성)
        progress_cb: (current, total) 형태로 호출되는 콜백

    Returns:
        생성된 파일 경로 목록
    """
    reader = PdfReader(str(input_path))
    if reader.is_encrypted:
        raise PdfReadError("암호화된 PDF는 지원하지 않습니다.")

    total = len(reader.pages)
    if start_page < 1 or start_page > total:
        raise ValueError(
            f"시작 페이지({start_page})가 전체 페이지 범위(1~{total})를 벗어났습니다."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem
    start_idx = start_page - 1
    outputs: list[Path] = []

    cursor = start_idx
    while cursor < total:
        end = min(cursor + CHUNK, total)
        writer = PdfWriter()
        for i in range(cursor, end):
            writer.add_page(reader.pages[i])

        out_name = f"{stem}_p{cursor + 1:03d}-{end:03d}.pdf"
        out_path = output_dir / out_name
        with open(out_path, "wb") as f:
            writer.write(f)
        outputs.append(out_path)

        if progress_cb:
            progress_cb(end - start_idx, total - start_idx)

        cursor = end

    return outputs


def open_folder(path: Path) -> None:
    """OS별 탐색기로 폴더를 연다."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception:
        pass


class SplitterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title(APP_TITLE)
        root.geometry("440x240")
        root.resizable(False, False)

        self.input_path: Path | None = None
        self.output_dir: Path | None = None

        main = ttk.Frame(root, padding=14)
        main.pack(fill="both", expand=True)

        # PDF 선택
        ttk.Label(main, text="PDF 파일").grid(row=0, column=0, sticky="w", pady=4)
        self.input_label = ttk.Label(main, text="(선택 안 됨)", foreground="#666", width=38)
        self.input_label.grid(row=0, column=1, sticky="w", padx=6)
        ttk.Button(main, text="찾기…", command=self.pick_input, width=8).grid(row=0, column=2)

        # 시작 페이지
        ttk.Label(main, text="시작 페이지").grid(row=1, column=0, sticky="w", pady=4)
        self.start_var = tk.IntVar(value=1)
        ttk.Spinbox(main, from_=1, to=9999, textvariable=self.start_var, width=8).grid(
            row=1, column=1, sticky="w", padx=6
        )
        ttk.Label(main, text="(예: 초교 20, 재교 30)", foreground="#888").grid(
            row=1, column=1, sticky="w", padx=(90, 0)
        )

        # 출력 폴더
        ttk.Label(main, text="출력 폴더").grid(row=2, column=0, sticky="w", pady=4)
        self.output_label = ttk.Label(
            main, text="(원본 폴더 / split)", foreground="#666", width=38
        )
        self.output_label.grid(row=2, column=1, sticky="w", padx=6)
        ttk.Button(main, text="변경…", command=self.pick_output, width=8).grid(row=2, column=2)

        # 실행 버튼
        self.run_btn = ttk.Button(main, text="분할 실행", command=self.run)
        self.run_btn.grid(row=3, column=0, columnspan=3, pady=(16, 4), sticky="ew")

        # 상태
        self.status_var = tk.StringVar(value="대기 중")
        ttk.Label(main, textvariable=self.status_var, foreground="#0a7").grid(
            row=4, column=0, columnspan=3, sticky="w"
        )

        for i in range(3):
            main.columnconfigure(i, weight=0)
        main.columnconfigure(1, weight=1)

    def pick_input(self) -> None:
        path = filedialog.askopenfilename(
            title="PDF 선택",
            filetypes=[("PDF 파일", "*.pdf"), ("모든 파일", "*.*")],
        )
        if not path:
            return
        self.input_path = Path(path)
        self.input_label.config(text=self.input_path.name, foreground="#000")
        if self.output_dir is None:
            default_out = self.input_path.parent / "split"
            self.output_label.config(text=str(default_out), foreground="#000")

    def pick_output(self) -> None:
        path = filedialog.askdirectory(title="출력 폴더 선택")
        if not path:
            return
        self.output_dir = Path(path)
        self.output_label.config(text=str(self.output_dir), foreground="#000")

    def run(self) -> None:
        if self.input_path is None:
            messagebox.showwarning(APP_TITLE, "PDF 파일을 먼저 선택하세요.")
            return
        try:
            start = int(self.start_var.get())
        except (tk.TclError, ValueError):
            messagebox.showwarning(APP_TITLE, "시작 페이지는 숫자여야 합니다.")
            return

        out_dir = self.output_dir or (self.input_path.parent / "split")

        self.run_btn.config(state="disabled")
        self.status_var.set("분할 중…")
        thread = threading.Thread(
            target=self._do_split, args=(self.input_path, start, out_dir), daemon=True
        )
        thread.start()

    def _do_split(self, input_path: Path, start: int, out_dir: Path) -> None:
        def on_progress(done: int, total: int) -> None:
            self.root.after(0, self.status_var.set, f"진행 {done}/{total} 페이지")

        try:
            outputs = split_pdf(input_path, start, out_dir, progress_cb=on_progress)
        except (PdfReadError, ValueError) as e:
            self.root.after(0, self._on_error, str(e))
            return
        except Exception as e:  # noqa: BLE001
            self.root.after(0, self._on_error, f"오류가 발생했습니다: {e}")
            return

        self.root.after(0, self._on_done, outputs, out_dir)

    def _on_error(self, msg: str) -> None:
        self.status_var.set("실패")
        self.run_btn.config(state="normal")
        messagebox.showerror(APP_TITLE, msg)

    def _on_done(self, outputs: list[Path], out_dir: Path) -> None:
        self.status_var.set(f"완료: {len(outputs)}개 파일 생성")
        self.run_btn.config(state="normal")
        messagebox.showinfo(
            APP_TITLE,
            f"{len(outputs)}개 파일을 만들었습니다.\n\n출력 폴더:\n{out_dir}",
        )
        open_folder(out_dir)


def main() -> None:
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except tk.TclError:
        pass
    SplitterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
