import tkinter as tk
from tkinter import ttk, font

class ToolTip:
    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None

    def showtip(self, text, x, y):
        """Show tooltip with given text at screen coords (x,y)."""
        if self.tipwindow or not text:
            return
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw, text=text, 
            justify=tk.LEFT,
            background="white", 
            relief=tk.SOLID, borderwidth=1,
            font=("Segoe UI", 9)
        )
        label.pack(ipadx=1)

    def hidetip(self):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None


def attach_conditional_tooltip(combobox):
    tooltip = ToolTip(combobox)

    def check_selected_truncation(event=None):
        """Check truncation for combobox *selected* text."""
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

    def hook_listbox(event=None):
        """Hook the listbox inside the dropdown after it is created."""
        try:
            popdown = combobox.tk.call("ttk::combobox::PopdownWindow", combobox)
            listbox = combobox.nametowidget(popdown + ".f.l")
        except Exception as e:
            return  # dropdown not ready yet

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

        # Bind once
        listbox.bind("<Motion>", on_listbox_motion, add="+")
        listbox.bind("<Leave>", on_listbox_leave, add="+")
    
    # Run hook when dropdown is first opened
    combobox.bind("<Button-1>", hook_listbox, add="+")
    combobox.bind("<Alt-Down>", hook_listbox, add="+")


# Example usage
if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("400x250")

    values = [
        "LibraryInterfaces.LGV.guid.info.pos.x",
        "InfoMovements.Mov.opCl4.curGroupsInterax[1].InfoMovements",
        "LibraryInterfaces.LGV.Guid.Odom.Cur_Spd",
        "CoreGVL.LoadHandling.ADS_Reset_Some_Very_Long_Variable_Name",
        "ShortName"
    ]

    combo = ttk.Combobox(root, values=values, width=25)
    combo.grid(row=0, column=0, padx=5, pady=5, sticky='nsew')
    combo.set(values[1])

    combo.grid_columnconfigure(0, weight=1)
    # combo.grid_rowconfigure(0, weight=1)

    attach_conditional_tooltip(combo)

    root.mainloop()
