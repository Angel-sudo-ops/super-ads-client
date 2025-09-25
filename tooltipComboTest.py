import tkinter as tk
from tkinter import ttk, font

class ToolTip:
    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None

    def showtip(self, text):
        if self.tipwindow or not text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 10
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw, text=text, justify=tk.LEFT,
            background="#ffffe0", relief=tk.SOLID, borderwidth=1,
            font=("Segoe UI", 9)
        )
        label.pack(ipadx=1)

    def hidetip(self):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None


def attach_conditional_tooltip(combobox):
    tooltip = ToolTip(combobox)

    def check_truncation(event=None):
        text = combobox.get()
        if not text:
            tooltip.text = ""
            return

        f = font.Font(font=combobox.cget("font"))
        text_width = f.measure(text)
        widget_width = combobox.winfo_width() - 30  # subtract arrow button

        tooltip.text = text if text_width > widget_width else ""

    def on_enter(event):
        if getattr(tooltip, "text", ""):
            tooltip.showtip(tooltip.text)

    def on_leave(event):
        tooltip.hidetip()

    combobox.bind("<Enter>", on_enter)
    combobox.bind("<Leave>", on_leave)
    combobox.bind("<Configure>", check_truncation)
    combobox.bind("<<ComboboxSelected>>", check_truncation)
    combobox.bind("<KeyRelease>", check_truncation)
    combobox.after(100, check_truncation)



if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("420x300")

    items = [
        "Short",
        "Some.Very.Long.Variable.Name.That.Does.Not.Fit",
        "MediumLengthVar",
        "Another.Really.Really.Long.Variable.Name"
    ]

    combo = ttk.Combobox(root, values=items, width=30)
    combo.pack(pady=80)
    combo.set(items[1])

    attach_conditional_tooltip(combo)

    root.mainloop()
