import tkinter as tk
from tkinter import font

class ToolTip:
    def __init__(self, widget, separator=","):
        self.widget = widget
        self.tipwindow = None
        self.text = ""
        self.separator = separator

    def format_text(self, raw_text):
        # Break at separators
        chunks = [chunk.strip() for chunk in raw_text.split(self.separator)]
        return "\n".join(chunks)

    def showtip(self, raw_text):
        if self.tipwindow or not raw_text:
            return
        
        formatted_text = self.format_text(raw_text)

        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=formatted_text,
            justify=tk.LEFT,
            background="white",
            relief=tk.SOLID,
            borderwidth=1,
            font=("Segoe UI", 9),
            padx=4,
            pady=2
        )
        label.pack()

    def hidetip(self):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None


def attach_tooltip_on_overflow(widget, text_var, separator=","):
    tooltip = ToolTip(widget, separator=separator)

    def check_overflow():
        f = font.Font(font=str(widget.cget("font")))
        text_width = f.measure(text_var.get())
        widget_width = widget.winfo_width() - 4  # small padding for borders
        tooltip.text = text_var.get() if text_width > widget_width else ""

    def on_enter(event):
        check_overflow()
        if tooltip.text:
            tooltip.showtip(tooltip.text)

    def on_leave(event):
        tooltip.hidetip()

    def on_update(*args):
        if tooltip.tipwindow:
            check_overflow()
            if tooltip.text:
                tooltip.showtip(tooltip.text)
            else:
                tooltip.hidetip()

    def on_resize(event):
        on_update()

    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)
    widget.bind("<Configure>", on_resize)
    text_var.trace_add("write", on_update)

    widget.after(100, check_overflow)



def show_status_message(
    root,
    status_label,
    message,
    duration=3000,
    fade_steps=10,
    start_color="#00aa00",
    end_color="#aaaaaa"
):
    """Show a temporary status message that fades from start_color to end_color before disappearing."""
    status_label.config(text=message, foreground=start_color)

    step_duration = duration // fade_steps

    # Helper to convert hex to RGB tuple
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    # Helper to convert RGB tuple to hex
    def rgb_to_hex(rgb_tuple):
        return "#{:02x}{:02x}{:02x}".format(*rgb_tuple)

    start_rgb = hex_to_rgb(start_color)
    end_rgb = hex_to_rgb(end_color)

    def fade(step=0):
        if step >= fade_steps:
            status_label.config(text="")
            return

        # Interpolate between start and end RGB values
        current_rgb = tuple(
            int(start + (end - start) * (step / fade_steps))
            for start, end in zip(start_rgb, end_rgb)
        )

        faded_color = rgb_to_hex(current_rgb)
        status_label.config(foreground=faded_color)

        root.after(step_duration, lambda: fade(step + 1))

    root.after(duration, fade)
