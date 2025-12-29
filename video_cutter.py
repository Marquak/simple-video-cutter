import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import threading
import re
import json
import os
import platform

CONFIG_FILE = "cutter.cfg"

# ---------------- CONFIG ---------------- #

def load_settings():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print("Error loading config:", e)
        return {}

def save_settings_file(settings):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        print("Error saving config:", e)

# ---------------- TIME PARSING ---------------- #

def parse_time_to_seconds(time_str):
    time_str = time_str.strip()
    if not time_str:
        return None

    # hh:mm:ss or mm:ss
    if ":" in time_str:
        parts = time_str.split(":")
        if not all(p.isdigit() for p in parts):
            return None
        parts = [int(p) for p in parts]
        if len(parts) == 3:
            h, m, s = parts
        elif len(parts) == 2:
            h = 0
            m, s = parts
        else:
            return None
        return h * 3600 + m * 60 + s

    # XmYs format
    match = re.fullmatch(r"(?:(\d+)m)?(?:(\d+)s)?", time_str)
    if match:
        m, s = match.groups()
        total = (int(m) * 60 if m else 0) + (int(s) if s else 0)
        return total if total > 0 else None

    # Raw seconds
    if time_str.isdigit():
        return int(time_str)

    return None

def seconds_to_ffmpeg_time(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:02}"

# ---------------- FILE PICKERS ---------------- #

def detect_supported_formats():
    try:
        result = subprocess.run(["ffmpeg", "-formats"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=True)
        output = result.stdout
        formats = re.findall(r"(?<=\s)(\w+)(?=\s+DE\s+)", output)  # Find formats with "DE" flag (decode + encode)
        return [(f"{fmt.upper()} files", f"*.{fmt}") for fmt in formats]
    except Exception as e:
        print("Error detecting formats:", e)
        return [("All files", "*.*")]

def select_input():
    filename = filedialog.askopenfilename(
        title="Select Video File",
        filetypes=file_types  # Dynamically determined file types
    )
    if filename:
        entry_input.delete(0, tk.END)
        entry_input.insert(0, filename)

def select_output():
    filename = filedialog.asksaveasfilename(
        title="Save Clip As",
        defaultextension=".mp4",
        filetypes=file_types  # Dynamically determined file types
    )
    if filename:
        entry_output.delete(0, tk.END)
        entry_output.insert(0, filename)

# ---------------- FFMPEG ---------------- #

def update_progress(progress):
    progress_label.config(text=f"{progress}%")

def run_ffmpeg(cmd):
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Update progress bar (basic implementation)
        for i in range(100):
            progress_label.config(text=f"{i + 1}%")
            app.update_idletasks()

        process.wait()
        if process.returncode == 0:
            app.after(0, lambda: messagebox.showinfo("Success", "Video clip saved successfully."))
            progress_label.config(text="Done")
        else:
            error_msg = process.stderr.read().strip() or "ffmpeg failed."
            app.after(0, lambda: messagebox.showerror("ffmpeg Error", error_msg))
            progress_label.config(text="Error")

    except Exception as e:
        print("Error running ffmpeg:", e)
        progress_label.config(text="Error")

def cut_video():
    input_file = entry_input.get().strip()
    output_file = entry_output.get().strip()

    if not input_file or not output_file:
        messagebox.showerror("Error", "Please select input and output files.")
        return

    start_sec = parse_time_to_seconds(entry_start.get())
    if start_sec is None:
        messagebox.showerror("Error", "Invalid start time.")
        return

    if end_time_var.get():
        end_sec = parse_time_to_seconds(entry_end.get())
        if end_sec is None or end_sec <= start_sec:
            messagebox.showerror("Error", "Invalid end time.")
            return
        duration_sec = end_sec - start_sec
    else:
        duration_sec = parse_time_to_seconds(entry_duration.get())
        if duration_sec is None:
            messagebox.showerror("Error", "Invalid duration.")
            return

    start_time = seconds_to_ffmpeg_time(start_sec)
    duration_time = seconds_to_ffmpeg_time(duration_sec)

    accurate = accurate_var.get()

    ffmpeg_cmd = ["ffmpeg", "-y"]

    if not accurate:
        ffmpeg_cmd += ["-ss", start_time]

    ffmpeg_cmd += ["-i", input_file]

    if accurate:
        ffmpeg_cmd += ["-ss", start_time]

    ffmpeg_cmd += ["-t", duration_time]

    if not accurate:
        ffmpeg_cmd += ["-c", "copy"]

    ffmpeg_cmd.append(output_file)

    threading.Thread(
        target=run_ffmpeg,
        args=(ffmpeg_cmd,),
        daemon=True
    ).start()

# ---------------- SETTINGS ---------------- #

def save_settings_checkbox():
    if save_settings_var.get():
        settings = {
            "input": entry_input.get(),
            "start": entry_start.get(),
            "end": entry_end.get(),
            "duration": entry_duration.get(),
            "use_end": end_time_var.get(),
            "accurate": accurate_var.get(),
            "save": True
        }
        save_settings_file(settings)
    else:
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)

def load_last_settings():
    settings = load_settings()
    if not settings.get("save"):
        return

    entry_input.insert(0, settings.get("input", ""))
    entry_start.insert(0, settings.get("start", ""))
    entry_end.insert(0, settings.get("end", ""))
    entry_duration.insert(0, settings.get("duration", ""))
    end_time_var.set(settings.get("use_end", False))
    accurate_var.set(settings.get("accurate", False))
    save_settings_var.set(True)
    toggle_end_time()

# ---------------- UI LOGIC ---------------- #

def toggle_end_time():
    if end_time_var.get():
        entry_end.config(state="normal")
        entry_duration.config(state="disabled")
    else:
        entry_end.config(state="disabled")
        entry_duration.config(state="normal")

# ---------------- GUI ---------------- #

app = tk.Tk()
app.title("Video Cutter (ffmpeg)")

# ttk.Style Configuration File
style = ttk.Style()
style.theme_use("clam")

save_settings_var = tk.BooleanVar()
end_time_var = tk.BooleanVar()
accurate_var = tk.BooleanVar()

file_types = detect_supported_formats()

progress_label = ttk.Label(app, text="")
progress_label.grid(row=9, column=2, pady=5, sticky="w")

# Grid Layout
load_last_settings()
app.mainloop()
