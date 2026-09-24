import json, os, re, sys
import tkinter as tk
from tkinter import ttk, messagebox

JSON_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), '..', 'story_msg.json')
JSON_PATH = os.path.abspath(JSON_PATH)

MAX_LINE = 26
MAX_LINES = 3
TAG_RE = re.compile(r'(<\d+>|<0>)')


def visible_len(s):
    return len(TAG_RE.sub('', s))


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(f"story_msg.json editor — {JSON_PATH}")
        self.root.geometry("1100x650")

        with open(JSON_PATH, encoding='utf-8') as f:
            self.data = json.load(f)

        self.keys = sorted(k for k, v in self.data.items() if v.get('type') == 'dialogue')
        self.current_key = None
        self.dirty = False

        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        root = self.root
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        top = ttk.Frame(root)
        top.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)
        ttk.Label(top, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *a: self._refresh_list())
        ttk.Entry(top, textvariable=self.search_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.untranslated_var = tk.BooleanVar()
        ttk.Checkbutton(top, text="Untranslated only", variable=self.untranslated_var,
                         command=self._refresh_list).pack(side=tk.LEFT, padx=4)

        body = ttk.Panedwindow(root, orient=tk.HORIZONTAL)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=4)

        left = ttk.Frame(body)
        body.add(left, weight=1)
        self.listbox = tk.Listbox(left, font=('monospace', 10))
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox.bind('<<ListboxSelect>>', self._on_select)
        sb = ttk.Scrollbar(left, command=self.listbox.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=sb.set)

        right = ttk.Frame(body)
        body.add(right, weight=2)

        self.key_label = ttk.Label(right, text="", font=('monospace', 10, 'bold'))
        self.key_label.pack(side=tk.TOP, anchor=tk.W)

        ttk.Label(right, text="Japanese (read-only):").pack(side=tk.TOP, anchor=tk.W, pady=(8, 0))
        self.jp_text = tk.Text(right, height=4, font=('sans-serif', 13), wrap=tk.WORD, state=tk.DISABLED)
        self.jp_text.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(right, text="English (editable):").pack(side=tk.TOP, anchor=tk.W, pady=(8, 0))
        self.en_text = tk.Text(right, height=6, font=('monospace', 13), wrap=tk.WORD)
        self.en_text.pack(side=tk.TOP, fill=tk.X)
        self.en_text.bind('<KeyRelease>', self._on_edit)

        self.status_var = tk.StringVar()
        ttk.Label(right, textvariable=self.status_var, font=('sans-serif', 10)).pack(side=tk.TOP, anchor=tk.W, pady=(4, 0))

        btns = ttk.Frame(right)
        btns.pack(side=tk.TOP, anchor=tk.W, pady=8)
        ttk.Button(btns, text="Save entry (Ctrl+S)", command=self._save_entry).pack(side=tk.LEFT)
        ttk.Button(btns, text="Save file", command=self._save_file).pack(side=tk.LEFT, padx=6)
        root.bind('<Control-s>', lambda e: self._save_entry())

        self.file_status_var = tk.StringVar()
        ttk.Label(root, textvariable=self.file_status_var).pack(side=tk.BOTTOM, anchor=tk.W, padx=6, pady=2)

    def _refresh_list(self):
        q = self.search_var.get().lower()
        only_untranslated = self.untranslated_var.get()
        self.listbox.delete(0, tk.END)
        self.filtered = []
        for k in self.keys:
            v = self.data[k]
            if only_untranslated and v.get('text_en'):
                continue
            if q and q not in k.lower() and q not in (v.get('text') or '').lower() \
                    and q not in (v.get('text_en') or '').lower():
                continue
            self.filtered.append(k)
            mark = ' ' if v.get('text_en') else '*'
            short = k.split('/')[-1]
            self.listbox.insert(tk.END, f"{mark} {short}")
        self._update_file_status()

    def _update_file_status(self):
        total = len(self.keys)
        done = sum(1 for k in self.keys if self.data[k].get('text_en'))
        self.file_status_var.set(f"{done}/{total} translated  |  {len(self.filtered)} shown  |  {JSON_PATH}")

    def _on_select(self, event):
        sel = self.listbox.curselection()
        if not sel:
            return
        if self.dirty:
            self._save_entry()
        key = self.filtered[sel[0]]
        self.current_key = key
        v = self.data[key]

        self.key_label.config(text=key)
        self.jp_text.config(state=tk.NORMAL)
        self.jp_text.delete('1.0', tk.END)
        self.jp_text.insert('1.0', v.get('text') or '')
        self.jp_text.config(state=tk.DISABLED)

        self.en_text.delete('1.0', tk.END)
        self.en_text.insert('1.0', v.get('text_en') or '')
        self.dirty = False
        self._update_status()

    def _on_edit(self, event):
        self.dirty = True
        self._update_status()

    def _update_status(self):
        text = self.en_text.get('1.0', 'end-1c')
        lines = text.split('\n')
        problems = []
        for i, l in enumerate(lines, 1):
            n = visible_len(l)
            if n > MAX_LINE:
                problems.append(f"line {i}: {n}/{MAX_LINE} chars")
        if len(lines) > MAX_LINES:
            problems.append(f"{len(lines)}/{MAX_LINES} lines")
        msg = f"{len(lines)} line(s)"
        if problems:
            msg += "  ⚠ " + "; ".join(problems)
        if self.dirty:
            msg += "   [unsaved]"
        self.status_var.set(msg)

    def _save_entry(self):
        if not self.current_key:
            return
        text = self.en_text.get('1.0', 'end-1c')
        self.data[self.current_key]['text_en'] = text if text else None
        self.dirty = False
        idx = self.listbox.curselection()
        if idx:
            mark = ' ' if text else '*'
            short = self.current_key.split('/')[-1]
            self.listbox.delete(idx[0])
            self.listbox.insert(idx[0], f"{mark} {short}")
            self.listbox.selection_set(idx[0])
        self._update_status()
        self._update_file_status()

    def _save_file(self):
        self._save_entry()
        with open(JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        messagebox.showinfo("Saved", f"Wrote {JSON_PATH}")

    def _on_close(self):
        if self.dirty:
            self._save_entry()
        if messagebox.askyesno("Save before exit?", "Write changes to story_msg.json?"):
            self._save_file()
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()
