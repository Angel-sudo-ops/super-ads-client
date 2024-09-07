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
        
        # IP Address entry
        self.ip_label = ttk.Label(root, text="PLC IP Address:")
        self.ip_label.grid(row=1, column=0, padx=10, pady=10)
        
        self.ip_entry = ttk.Entry(root, width=20)
        self.ip_entry.grid(row=1, column=1, padx=10, pady=10)
        
        # Connection Button
        self.connect_button = ttk.Button(root, text="Connect", command=self.connect_to_plc)
        self.connect_button.grid(row=2, column=0, padx=10, pady=10)
        
        # Connection Status Label
        self.status_label = ttk.Label(root, text="Not Connected", foreground="red")
        self.status_label.grid(row=2, column=1, padx=10, pady=10)

        # Control Buttons (Initially disabled)
        self.reset_button = ttk.Button(root, text="Reset", command=self.reset_plc, state=tk.DISABLED)
        self.reset_button.grid(row=3, column=0, padx=10, pady=10)
        
        self.run_button = ttk.Button(root, text="Run", command=self.run_plc, state=tk.DISABLED)
        self.run_button.grid(row=3, column=1, padx=10, pady=10)
        
        self.stop_button = ttk.Button(root, text="Stop", command=self.stop_plc, state=tk.DISABLED)
        self.stop_button.grid(row=3, column=2, padx=10, pady=10)
        
        # Initialize connection variables
        self.ads_port = 851
        self.plc = None

    def connect_to_plc(self):
        ams_net_id = self.ams_entry.get()
        ip_address = self.ip_entry.get()
        
        if ams_net_id and ip_address:
            self.plc = pyads.Connection(ams_net_id, self.ads_port, ip_address)
            
            try:
                # Open the connection
                self.plc.open()

                # Read PLC state
                state = self.plc.read_state()
                print(f"PLC Status: {state}")

                # Check if the PLC is in RUN state (state[0] == 5)
                if state[0] == 5:
                    self.status_label.config(text="Connected (PLC in RUN)", foreground="green")
                    print("Connection to PLC established successfully.")
                    
                    # Enable the control buttons
                    self.reset_button.config(state=tk.NORMAL)
                    self.run_button.config(state=tk.NORMAL)
                    self.stop_button.config(state=tk.NORMAL)
                else:
                    self.status_label.config(text="PLC is not in RUN state", foreground="orange")
                    print("PLC is not in RUN state.")
                    self.reset_button.config(state=tk.DISABLED)
                    self.run_button.config(state=tk.DISABLED)
                    self.stop_button.config(state=tk.DISABLED)

            except pyads.ADSError as ads_error:
                self.status_label.config(text="Connection Failed (ADS Error)", foreground="red")
                print(f"ADS Error: {ads_error}")
        else:
            self.status_label.config(text="Invalid AMS or IP", foreground="orange")

    def reset_plc(self):
        self.write_variable("MAIN.Reset", True)

    def run_plc(self):
        self.write_variable("MAIN.Run", True)

    def stop_plc(self):
        self.write_variable("MAIN.Stop", True)

    def write_variable(self, variable_name, value):
        try:
            if self.plc and self.plc.is_open:
                self.plc.write_by_name(variable_name, value, pyads.PLCTYPE_BOOL)
                print(f"Successfully wrote {value} to {variable_name}")
            else:
                print("PLC connection not open")
        except Exception as e:
            print(f"Error writing to PLC: {e}")

# Create the Tkinter root window
root = tk.Tk()
app = PLCControlApp(root)
root.mainloop()
