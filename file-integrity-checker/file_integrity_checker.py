import os
import hashlib
import json
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

BASELINE_FILENAME = "file_hashes_baseline.json"
# Store the baseline outside any folder the user might scan, so re-running
# a baseline creation/check never hashes the baseline file itself.
BASELINE_FILE = os.path.join(os.path.abspath(os.path.dirname(__file__)), BASELINE_FILENAME)


def calculate_sha256(file_path):
    """Calculates SHA-256 hash of a file, reading in 8KB chunks.

    Returns the hex digest, or None if the file could not be read
    (permission denied, deleted mid-scan, broken symlink, etc.).
    """
    sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()
    except (PermissionError, FileNotFoundError, OSError):
        return None


def iter_target_files(folder_path):
    """Walks folder_path, yielding full file paths, skipping the baseline file itself."""
    baseline_abspath = os.path.abspath(BASELINE_FILE)
    for root_dir, _, files in os.walk(folder_path):
        for file in files:
            full_path = os.path.join(root_dir, file)
            if os.path.abspath(full_path) == baseline_abspath:
                continue
            yield full_path


class IntegrityCheckerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Local File Integrity Checker")
        self.root.geometry("680x520")
        self.root.resizable(True, True)

        self.style = ttk.Style()
        self.style.theme_use('clam')

        self._scan_lock = threading.Lock()
        self._scan_running = False

        self.setup_ui()

    def setup_ui(self):
        path_frame = ttk.LabelFrame(self.root, text=" Target Directory ", padding=10)
        path_frame.pack(fill="x", padx=15, pady=10)

        self.path_entry = ttk.Entry(path_frame, font=("Segoe UI", 10))
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        browse_btn = ttk.Button(path_frame, text="Browse Folder", command=self.browse_folder)
        browse_btn.pack(side="right")

        action_frame = ttk.Frame(self.root, padding=5)
        action_frame.pack(fill="x", padx=15)

        self.baseline_btn = ttk.Button(action_frame, text="1. Create Baseline", command=self.create_baseline)
        self.baseline_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.check_btn = ttk.Button(action_frame, text="2. Run Integrity Check", command=self.check_integrity)
        self.check_btn.pack(side="left", fill="x", expand=True, padx=(5, 0))

        self.status_label = ttk.Label(self.root, text="Idle", padding=(15, 0))
        self.status_label.pack(fill="x")

        log_frame = ttk.LabelFrame(self.root, text=" Integrity Log Window ", padding=10)
        log_frame.pack(fill="both", expand=True, padx=15, pady=10)

        self.log_area = ScrolledText(log_frame, wrap="word", font=("Consolas", 10), state="disabled")
        self.log_area.pack(fill="both", expand=True)

        self.log_area.tag_config("INFO", foreground="#1D4ED8")       # Blue
        self.log_area.tag_config("SUCCESS", foreground="#15803D")    # Green
        self.log_area.tag_config("MODIFIED", foreground="#B91C1C")   # Red
        self.log_area.tag_config("NEW", foreground="#D97706")        # Orange
        self.log_area.tag_config("DELETED", foreground="#6B21A8")    # Purple
        self.log_area.tag_config("UNREADABLE", foreground="#78716C") # Gray

    # -- logging helpers (safe to call from a background thread) --

    def log(self, message, tag="INFO"):
        self.root.after(0, self._log_ui, message, tag)

    def _log_ui(self, message, tag):
        self.log_area.config(state="normal")
        self.log_area.insert("end", message + "\n", tag)
        self.log_area.see("end")
        self.log_area.config(state="disabled")

    def clear_log(self):
        self.log_area.config(state="normal")
        self.log_area.delete("1.0", tk.END)
        self.log_area.config(state="disabled")

    def set_status(self, text):
        self.root.after(0, lambda: self.status_label.config(text=text))

    def set_buttons_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        self.root.after(0, lambda: self.baseline_btn.config(state=state))
        self.root.after(0, lambda: self.check_btn.config(state=state))

    def browse_folder(self):
        selected_dir = filedialog.askdirectory()
        if selected_dir:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, selected_dir)

    # -- validation shared by both actions --

    def _get_valid_folder_or_warn(self):
        folder_path = self.path_entry.get().strip()
        if not folder_path or not os.path.isdir(folder_path):
            messagebox.showwarning("Warning", "Please select a valid folder first.")
            return None
        return folder_path

    def _start_scan_thread(self, target):
        with self._scan_lock:
            if self._scan_running:
                messagebox.showinfo("Busy", "A scan is already running.")
                return
            self._scan_running = True
        self.set_buttons_enabled(False)

        def runner():
            try:
                target()
            finally:
                with self._scan_lock:
                    self._scan_running = False
                self.set_buttons_enabled(True)
                self.set_status("Idle")

        threading.Thread(target=runner, daemon=True).start()

    # -- baseline creation --

    def create_baseline(self):
        folder_path = self._get_valid_folder_or_warn()
        if not folder_path:
            return

        if os.path.exists(BASELINE_FILE):
            if not messagebox.askyesno(
                "Overwrite baseline?",
                f"A baseline already exists at:\n{BASELINE_FILE}\n\nOverwrite it?",
            ):
                return

        self.clear_log()
        self._start_scan_thread(lambda: self._create_baseline_worker(folder_path))

    def _create_baseline_worker(self, folder_path):
        self.log(f"[*] Scanning target directory: {folder_path}...", "INFO")
        self.set_status("Creating baseline...")

        baseline_data = {}
        unreadable = []

        for full_path in iter_target_files(folder_path):
            file_hash = calculate_sha256(full_path)
            if file_hash:
                baseline_data[full_path] = file_hash
            else:
                unreadable.append(full_path)

        with open(BASELINE_FILE, "w") as f:
            json.dump(baseline_data, f, indent=4, sort_keys=True)

        if unreadable:
            self.log(f"[!] Skipped {len(unreadable)} unreadable file(s) (not included in baseline):", "UNREADABLE")
            for path in unreadable:
                self.log(f"    - {path}", "UNREADABLE")

        self.log(f"[+] SUCCESS: Baseline created for {len(baseline_data)} files.", "SUCCESS")
        self.log(f"[+] Saved baseline to: {BASELINE_FILE}", "SUCCESS")

    # -- integrity check --

    def check_integrity(self):
        folder_path = self._get_valid_folder_or_warn()
        if not folder_path:
            return

        if not os.path.exists(BASELINE_FILE):
            messagebox.showerror("Error", f"No baseline found at '{BASELINE_FILE}'! Create a baseline first.")
            return

        self.clear_log()
        self._start_scan_thread(lambda: self._check_integrity_worker(folder_path))

    def _check_integrity_worker(self, folder_path):
        with open(BASELINE_FILE, "r") as f:
            baseline_data = json.load(f)

        current_files = set()
        issues_detected = 0
        unreadable_count = 0

        self.log(f"[*] Running Integrity Check on: {folder_path}...\n", "INFO")
        self.set_status("Checking integrity...")

        for full_path in iter_target_files(folder_path):
            current_files.add(full_path)
            current_hash = calculate_sha256(full_path)

            if current_hash is None:
                # Could not read the file this time around; report distinctly
                # rather than silently flagging it as "modified".
                self.log(f"[UNREADABLE]    -> {full_path}", "UNREADABLE")
                unreadable_count += 1
                continue

            if full_path not in baseline_data:
                self.log(f"[NEW FILE]      -> {full_path}", "NEW")
                issues_detected += 1
            elif current_hash != baseline_data[full_path]:
                self.log(f"[MODIFIED FILE] -> {full_path}", "MODIFIED")
                issues_detected += 1

        for baseline_file in baseline_data:
            if baseline_file not in current_files:
                self.log(f"[DELETED FILE]  -> {baseline_file}", "DELETED")
                issues_detected += 1

        self.log("\n-------------------------------------------", "INFO")
        if unreadable_count:
            self.log(f"[!] {unreadable_count} file(s) could not be read during this check.", "UNREADABLE")

        if issues_detected == 0:
            self.log("[OK] INTEGRITY VERIFIED: All files match baseline!", "SUCCESS")
        else:
            self.log(f"[!] COMPLETE: Found {issues_detected} file state change(s).", "MODIFIED")


if __name__ == "__main__":
    root = tk.Tk()
    app = IntegrityCheckerApp(root)
    root.mainloop()
