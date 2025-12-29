import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import threading
import re
import json
import os

CONFIG_FILE = "cutter.cfg"

# ---------------- CONFIG ---------------- #

def load_settings():
    """Load saved settings from the configuration file."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print("Error loading config:", e)
        return {}

def save_settings_file(settings):
    """Save settings to the configuration file."""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        print("Error saving config:", e)

# ---------------- TIME PARSING ---------------- #

def parse_time_to_seconds(time_str):
    """Convert a user-provided time string to total seconds."""
    time_str = time_str.strip()
    if not time_str:
        return None
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
    match = re.fullmatch(r"(?:(\d+)m)?(?:(\d+)s)?", time_str)
    if match:
        m, s = match.groups()
        total = (int(m) * 60 if m else 0) + (int(s) if s else 0)
        return total if total > 0 else None
    if time_str.isdigit():
        return int(time_str)
    return None

def seconds_to_ffmpeg_time(seconds):
    """Convert seconds to FFmpeg-compatible time format (hh:mm:ss)."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:02}"

# ---------------- FILE PICKERS ---------------- #

def supported_video_patterns():
    """Provide a list of patterns for common video file types."""
    formats = ["mp4", "mkv", "avi", "webm", "mov", "flv", "wmv", "m4v"]
    patterns = []
    for fmt in formats:
        patterns.append(f"*.{fmt.lower()}")
        patterns.append(f"*.{fmt.upper()}")
    return patterns

def select_input():
    """Open file dialog to select input video file."""
    supported_formats = supported_video_patterns()
    filename = filedialog.askopenfilename(
        title="Select Video File",
        filetypes=[
            ("All Supported Video File Types", tuple(supported_formats)),
            ("All Files", "*.*")
        ]
    )
    if filename:
        entry_input.delete(0, tk.END)
        entry_input.insert(0, filename)

def select_output():
    """Open file dialog to select where to save the output video."""
    supported_formats = supported_video_patterns()
    filename = filedialog.asksaveasfilename(
        title="Save Clip As",
        defaultextension=".mp4",
        filetypes=[
            ("All Supported Video File Types", tuple(supported_formats)),
            ("All Files", "*.*")
        ]
    )
    if filename:
        entry_output.delete(0, tk.END)
        entry_output.insert(0, filename)

# ---------------- FFMPEG ---------------- #

def update_progress(progress):
    """Update the progress label to indicate completion percentage."""
    progress_label.config(text=f"{progress}%", anchor="w")
    app.update_idletasks()

def run_ffmpeg(cmd):
    """Run FFmpeg command to process video cutting."""
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for i in range(1, 101, 10):  # Simulate a progress bar
            update_progress(i)
            app.after(100)
        process.wait()
        if process.returncode == 0:
            messagebox.showinfo("Success", "Video clip saved successfully!")
            progress_label.config(text="Done")
        else:
            error_msg = process.stderr.read().strip() or "FFmpeg processing failed."
            messagebox.showerror("Error", error_msg)
            progress_label.config(text="Error")
    except Exception as e:
        print("Error running FFmpeg:", e)
        progress_label.config(text="Error")

def cut_video():
    """Validate entries and run the FFmpeg command to cut the video."""
    input_file = entry_input.get().strip()
    output_file = entry_output.get().strip()

    if not input_file or not output_file:
        messagebox.showerror("Error", "Please select both an input and output file.")
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
    """Save settings to a configuration file."""
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
    """Load previously saved settings."""
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
    """Enable or disable duration/end time fields based on toggle."""
    if end_time_var.get():
        entry_end.config(state="normal")
        entry_duration.config(state="disabled")
    else:
        entry_end.config(state="disabled")
        entry_duration.config(state="normal")

# ---------------- GUI ---------------- #

app = tk.Tk()
app.title("Video Cutter (ffmpeg)")

style = ttk.Style()
style.theme_use("clam")

save_settings_var = tk.BooleanVar()
end_time_var = tk.BooleanVar()
accurate_var = tk.BooleanVar()

# Input Components
ttk.Label(app, text="Input Video:").grid(row=0, column=0, sticky="e")
entry_input = ttk.Entry(app, width=50)
entry_input.grid(row=0, column=1)
ttk.Button(app, text="Browse", command=select_input).grid(row=0, column=2)

ttk.Label(app, text="Output File:").grid(row=1, column=0, sticky="e")
entry_output = ttk.Entry(app, width=50)
entry_output.grid(row=1, column=1)
ttk.Button(app, text="Save As", command=select_output).grid(row=1, column=2)

ttk.Label(app, text="Start Time: (e.g. 2m10s, 2m)").grid(row=2, column=0, sticky="e")
entry_start = ttk.Entry(app)
entry_start.grid(row=2, column=1)

ttk.Checkbutton(
    app, text="Specify End Time:",
    variable=end_time_var, command=toggle_end_time
).grid(row=3, column=0, sticky="w")

ttk.Label(app, text="End Time: (e.g. 6m13s, 6m)").grid(row=4, column=0, sticky="e")
entry_end = ttk.Entry(app, state="disabled")
entry_end.grid(row=4, column=1)

ttk.Label(app, text="Duration: (e.g. 5m10s, 5m)").grid(row=5, column=0, sticky="e")
entry_duration = ttk.Entry(app)
entry_duration.grid(row=5, column=1)

ttk.Checkbutton(
    app, text="Frame-accurate cut (re-encode)",
    variable=accurate_var
).grid(row=6, column=0, sticky="w")

ttk.Checkbutton(
    app, text="Save Settings",
    variable=save_settings_var, command=save_settings_checkbox
).grid(row=7, column=0, sticky="w")

ttk.Button(app, text="Cut Video", command=cut_video).grid(row=8, column=0, columnspan=3, pady=10)

progress_label = ttk.Label(app, text="")
progress_label.grid(row=9, column=2, pady=5, sticky="e")

load_last_settings()
app.mainloop()
