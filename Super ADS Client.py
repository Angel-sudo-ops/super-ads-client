import tkinter as tk
from tkinter import ttk
import pyads

class PLCControlApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PLC Control Interface")
        
        # AMS Net ID entry
        self.ams_label = ttk.Label(root, text="AMS Net ID:")
        self.ams_label.grid(row=0, column=0, padx=10, pady=10)
        
        self.ams_entry = ttk.Entry(root, width=20)
        self.ams_entry.grid(row=0, column=1, padx=10, pady=10)
        
        # IP Address entry (optional, depending on PLC setup)
        self.ip_label = ttk.Label(root, text="PLC IP Address:")
        self.ip_label.grid(row=1, column=0, padx=10, pady=10)
        
        self.ip_entry = ttk.Entry(root, width=20)
        self.ip_entry.grid(row=1, column=1, padx=10, pady=10)
        
        # Control Buttons
        self.reset_button = tk.Button(root, text="Reset", command=self.reset_plc, width=10, bg='gray')
        self.reset_button.grid(row=2, column=0, padx=10, pady=10)
        
        self.run_button = tk.Button(root, text="Run", command=self.run_plc, width=10, bg='gray')
        self.run_button.grid(row=2, column=1, padx=10, pady=10)
        
        self.stop_button = tk.Button(root, text="Stop", command=self.stop_plc, width=10, bg='gray')
        self.stop_button.grid(row=2, column=2, padx=10, pady=10)
        
        # Initialize connection variables
        self.ads_port = 851
        self.plc = None
        
        # Periodically check PLC variable statuses
        self.check_status()

    def connect_to_plc(self):
        ams_net_id = self.ams_entry.get()
        ip_address = self.ip_entry.get()
        
        if ams_net_id and ip_address:
            self.plc = pyads.Connection(ams_net_id, self.ads_port, ip_address)
            self.plc.open()

    def reset_plc(self):
        self.connect_to_plc()
        self.write_variable("MAIN.Reset", True)
        self.plc.close()

    def run_plc(self):
        self.connect_to_plc()
        self.write_variable("MAIN.Run", True)
        self.plc.close()

    def stop_plc(self):
        self.connect_to_plc()
        self.write_variable("MAIN.Stop", True)
        self.plc.close()

    def write_variable(self, variable_name, value):
        try:
            if self.plc and self.plc.is_open:
                self.plc.write_by_name(variable_name, value, pyads.PLCTYPE_BOOL)
                print(f"Successfully wrote {value} to {variable_name}")
            else:
                print("PLC connection not open")
        except Exception as e:
            print(f"Error writing to PLC: {e}")

    def check_status(self):
        self.connect_to_plc()
        if self.plc:
            try:
                # Read the variables to update button colors
                reset_status = self.plc.read_by_name("MAIN.Reset", pyads.PLCTYPE_BOOL)
                run_status = self.plc.read_by_name("MAIN.Run", pyads.PLCTYPE_BOOL)
                stop_status = self.plc.read_by_name("MAIN.Stop", pyads.PLCTYPE_BOOL)
                
                # Update button colors
                self.update_button_color(self.reset_button, reset_status)
                self.update_button_color(self.run_button, run_status)
                self.update_button_color(self.stop_button, stop_status)
            except Exception as e:
                print(f"Error reading from PLC: {e}")
            finally:
                self.plc.close()

        # Call this function again after 1 second to keep checking the status
        self.root.after(1000, self.check_status)

    def update_button_color(self, button, status):
        if status:
            button.config(bg="green")
        else:
            button.config(bg="red")

# Create the Tkinter root window
root = tk.Tk()
app = PLCControlApp(root)
root.mainloop()
