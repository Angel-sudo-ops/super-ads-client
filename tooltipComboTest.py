import tkinter as tk
from tkinter import ttk, font

class ToolTip:
    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None

    def showtip(self, text, x, y):
        if self.tipwindow or not text:
            return
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

    # ----- COMBOBOX SELECTED TEXT TOOLTIP -----
    def check_selected_truncation(event=None):
        text = combobox.get()
        if not text:
            combobox.tooltip_text = ""
            return
        f = font.Font(font=combobox.cget("font"))
        text_width = f.measure(text)
        widget_width = combobox.winfo_width() - 30
        combobox.tooltip_text = text if text_width > widget_width else ""

    def on_enter(event):
        if getattr(combobox, "tooltip_text", ""):
            tooltip.showtip(combobox.tooltip_text, event.x_root + 20, event.y_root + 20)

    def on_leave(event):
        tooltip.hidetip()

    combobox.bind("<Enter>", on_enter)
    combobox.bind("<Leave>", on_leave)
    combobox.bind("<Configure>", check_selected_truncation)
    combobox.bind("<<ComboboxSelected>>", check_selected_truncation)
    combobox.bind("<KeyRelease>", check_selected_truncation)
    combobox.after(100, check_selected_truncation)

    # ----- DROPDOWN LIST TOOLTIP -----
    def hook_listbox(event=None):
        try:
            popdown = combobox.tk.call("ttk::combobox::PopdownWindow", combobox)
            listbox = combobox.nametowidget(popdown + ".f.l")
        except Exception as e:
            print("❌ Popdown not ready, retrying in 50ms")
            combobox.after(50, hook_listbox)
            return  # popup not ready yet

        def on_listbox_motion(ev):
            idx = listbox.nearest(ev.y)
            if idx < 0:
                tooltip.hidetip()
                return
            text = listbox.get(idx)
            f = font.Font(font=combobox.cget("font"))
            if f.measure(text) > combobox.winfo_width() - 30:
                tooltip.hidetip()
                tooltip.showtip(text, ev.x_root + 20, ev.y_root + 20)
            else:
                tooltip.hidetip()

        def on_listbox_leave(ev):
            tooltip.hidetip()

        def on_listbox_click(ev):
            tooltip.hidetip()

        # Attach once
        listbox.bind("<Motion>", on_listbox_motion, add="+")
        listbox.bind("<Leave>", on_listbox_leave, add="+")
        # listbox.bind("<Button-1>", on_listbox_click, add="+")

    def delayed_hook(event=None):
        combobox.after(100, hook_listbox)

    # Delay hooking the dropdown list until it's opened
    combobox.bind("<Button-1>", delayed_hook, add="+")
    combobox.bind("<Alt-Down>", delayed_hook, add="+")


# -------- Example Usage --------
if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("420x250")

    values = [
        "Short",
        "LibraryInterfaces.LGV.Guid.Odom.Cur_Spd",
        "InfoMovements.Mov.opCl4.curGroupsInterax[1].InfoMovements",
        "CoreGVL.LoadHandling.ADS_Reset_Some_Extra_Long_Variable_Name_With_Stuff",
        "Tiny"
    ]

    combo = ttk.Combobox(root, values=values, width=25)
    combo.pack(padx=20, pady=50)
    combo.set(values[2])

    attach_conditional_tooltip(combo)

    root.mainloop()
