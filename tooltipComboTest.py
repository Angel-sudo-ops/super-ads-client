import tkinter as tk
from tkinter import ttk, font

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



if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("420x300")

    items = [
        "Short",
        "Some.Very.Long.Variable.Name.That.Does.Not.Fit",
        "MediumLengthVar",
        "Another.Really.Really.Long.Variable.Name",     
        "InfoMovements.Mov.opCl4.curGroupsInterax[1];InfoMovements.Mov.opCl4.curGroupsInterax[2];InfoMovements.Mov.shift.curPosition;InfoMovements.Mov.tilt.curPosition;InfoMovements.Mov.lift.curPosition; LibraryInterfaces.LGV.Guid.Rout.remDistToPreOP; LibraryInterfaces.LGV.Guid.Rout.remDistToOP; Devices.Pressure.tilt.weight; Devices.Pressure.lift.weight; FlexSegPhaseHandler.preOpDistFromTheEnd; FlexSegPhaseHandler.segDistAvailable",

    ]

    selected_var = tk.StringVar()

    combo = ttk.Combobox(root, values=items, textvariable=selected_var, width=30)
    combo.pack(pady=80)
    combo.set(items[1])

    attach_tooltip_on_overflow(combo, selected_var, separator=";")

    root.mainloop()
