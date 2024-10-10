import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import re
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
import pyads
import sys
import threading
import time

__version__ = '2.1.2 Beta 7'
__icon__ = "./plc.ico"

# Variable to hold the current ads connection
current_ads_connection = None

####################################################################################################################################################################
########################################################## Initial data reading from db3 file ######################################################################
####################################################################################################################################################################

def read_db3_file(db3_file_path, table_name):
    try:
        # Connect to the .db3 file
        conn = sqlite3.connect(db3_file_path)
        cursor = conn.cursor()

        # Check if the table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cursor.fetchone():
            # messagebox.showerror("Error", f"Table '{table_name}' does not exist in the database.")
            messagebox.showerror("Error", f"Wrong database format.")
            conn.close()
            return None

        # Query to get all rows from the specified table
        cursor.execute(f"SELECT * FROM {table_name}")
        
        # Fetch all rows
        rows = cursor.fetchall()

        # Get column names
        column_names = [description[0] for description in cursor.description]

        # Convert the rows into a list of dictionaries
        dict_rows = [dict(zip(column_names, row)) for row in rows]

        # Close the connection
        conn.close()

        return dict_rows
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")
        return None


def populate_table_from_db3():
    db3_path = filedialog.askopenfilename(title="Select config.db3 file", 
                                          initialdir="C:\\Program Files (x86)\\Elettric80",
                                          filetypes=[("DB3 files", "*.db3")])
    if not db3_path:
        return
    
    table_agvs = "tbl_AGVs"
    rows_agvs = read_db3_file(db3_path, table_agvs)
    if rows_agvs is None:
        return
    
    table_param = "tbl_Parameter"
    rows_param = read_db3_file(db3_path, table_param)
    if rows_param is None:
        return
    
    # # print(columns, rows)
    
    # Clear the existing table data
    for i in treeview.get_children():
        treeview.delete(i)
    
    # Default type_tc based on the transfer mode
    default_type_tc = "TC2"  # Assume TC2 unless specified otherwise
    for row_param in rows_param:
        if row_param['dbf_Name'] == "agvlayoutloadmethod" and row_param['dbf_Value'] == "SFTP":
            default_type_tc = "TC3" # If SFTP, set all to TC3

    # Initialize an empty list to hold the data
    routes_data = []
    # Iterate through each <Route> element in the XML
    for route in rows_agvs:
        if route['dbf_Enabled']: 
        # if None in (name, address, net_id):
        #     messagebox.showwarning("Warning", "One or more routes are missing required fields (Name, Address, NetId).")
        #     continue  # Skip this route and move to the next

            name = f"LGV{str(route['dbf_ID']).zfill(2)}"
            address = route['dbf_IP']
            net_id = f"{address}.1.1"
            
            # if route['Dbf_Comm_Library']>20 or 
            if route['LayoutCopy_Protocol']=="SFTP":
                type_tc = "TC3" 
            elif route['LayoutCopy_Protocol']=="FTP" or route['LayoutCopy_Protocol']=="NETFOLDER":
                type_tc = "TC2" 
            else:
                type_tc = default_type_tc 
        
            # Append the tuple to the list
            routes_data.append((name, net_id, type_tc))
    
    # Populate the Treeview with the data
    for item in routes_data:
        treeview.insert("", "end", values=item)

    # Save data to custom xml to avoid reloading .db3 everytime app is open
    save_table_data_to_xml(treeview)


# Save data to XML
def save_table_data_to_xml(tree, filename="lgv_data.xml"):
    lgv_list = ET.Element("LGVData")
    for row in tree.get_children():
        lgv = ET.SubElement(lgv_list, "LGV")
        lgv_data = tree.item(row)["values"]
        ET.SubElement(lgv, "Name").text = lgv_data[0]
        ET.SubElement(lgv, "AMSNetId").text = lgv_data[1]
        ET.SubElement(lgv, "Type").text = lgv_data[2]
    
    # Convert to a pretty XML string
    xmlstr = minidom.parseString(ET.tostring(lgv_list, 'utf-8')).toprettyxml(indent="    ")

    # Write to a file
    with open(filename, "w", encoding='utf-8') as f:
        f.write(xmlstr)

# Load data from XML
def load_table_data_from_xml(tree, filename="lgv_data.xml"):
    if os.path.exists(filename):
        tree_xml = ET.parse(filename)
        lgv_list = tree_xml.getroot()
        for lgv in lgv_list.findall("LGV"):
            lgv_name = lgv.find("Name").text
            ams_net_id = lgv.find("AMSNetId").text
            tc_type = lgv.find("Type").text
            tree.insert("", "end", values=(lgv_name, ams_net_id, tc_type))
    else:
        print("No saved XML data found, loading default table.")


####################################################################################################################################################################
################################################################# ADS connection setup #############################################################################
####################################################################################################################################################################
def monitor_connection_status():
    global current_ads_connection

    if current_ads_connection is None:
        return
    
    try:
        if check_plc_status(current_ads_connection):
            root.after(0, update_ui_connection_status, "Connected", "green", status_label)
        else:
            raise Exception("PLC not in valid state")
    except Exception as e:
        # assume connection is lost if not status 5 is read
        disable_control_buttons()
        root.after(0, update_ui_connection_status, "Disconnected", "red", status_label)
        close_current_connection()

    t = threading.Timer(1.0, monitor_connection_status)
    t.daemon = True
    t.start()  

    
def check_plc_status(ads_connection):
    status = ads_connection.read_state()[0]
    if status == 5:
        return True
    return False

# Close the current connection if it exists
def close_current_connection():
    global current_ads_connection, dis_horn_state, connection_in_progress
    # with read_lock:
    connection_in_progress = False
    update_ui_connection_status("Disconnected", "red", status_label)
    if current_ads_connection:
        current_ads_connection.close()
        current_ads_connection = None
        dis_horn_state = False #reset horn state

# Background connection handler (runs in a separate thread)
def background_connect(plc_data, label):
    global current_ads_connection, connection_in_progress

    # If already connected, don't try to reconnect
    if current_ads_connection is not None:
        return
    
    lgv_name, ams_net_id, tc_type = plc_data
    port = 851 if tc_type == 'TC3' else 801

    update_ui_connection_status("Connecting...", "orange", label)

    try:        
        # Attempt to open a new connection
        current_ads_connection = pyads.Connection(ams_net_id, port)
        current_ads_connection.open()

        # Check PLC status
        if check_plc_status(current_ads_connection):
            update_ui_connection_status("Connected", "green", label)
            enable_control_buttons()

            # Call update_buttons once to start the loop
            # update_buttons()
            update_buttons_from_plc_thread()

            # Start monitoring the connection after connecting
            monitor_connection_status()

        else:
            raise Exception("PLC not in a valid state")

    except Exception as e:
        current_ads_connection = None
        disable_control_buttons()
        update_ui_connection_status("Disconnected", "red", label)
        messagebox.showerror("Connection Error", f"Failed to connect to {lgv_name}: {str(e)}")
        treeview.selection_remove(treeview.selection())

    finally:
        connection_in_progress = False
        if current_ads_connection is None:
            update_ui_connection_status("Disconnected", "red", label)

# Update the UI status label (called from the main thread)
def update_ui_connection_status(text, color, label):
    label.config(text=text, foreground=color)

# Attempt to connect to the selected PLC (starts in a new thread)
def connect_to_plc(tree, label):
    global connection_in_progress, current_ads_connection
    
    if connection_in_progress:
        print("Connection in progress. Waiting for it to finish. Triggered on connect")
        messagebox.showinfo("Attention", "Connection in progress. Waiting for it to finish. Triggered on connect")
        return
    
    # If already connected, don't try to reconnect
    if current_ads_connection is not None:
        print("Target already connected")
        messagebox.showinfo("Attention", "Target already connected")
        return
    
    # Get the selected PLC data
    selected_item = tree.selection()
    if not selected_item:
        # messagebox.showinfo("Attention", "Select LGV")
        print("No LGV selected")
        return

    lgv_data = tree.item(selected_item)["values"]

    # Start the connection in a new thread
    connection_thread = threading.Thread(target=background_connect, args=(lgv_data, label))
    connection_thread.start()
    connection_in_progress = True


previous_selection = None # track previous connection

connection_in_progress = False
# Close the current connection when selection changes
def on_treeview_select(event):
    global current_ads_connection, previous_selection, connection_in_progress
    # Get the currently selected LGV
    
    selected_item = treeview.selection()
    if not selected_item:
        return
    
    if connection_in_progress:
        print("Connection in progress. Waiting for it to finish. Triggered on select")
        messagebox.showinfo("Attention", "Connection in progress. Waiting for it to finish. Triggered on select")
        return

    # If the same item is selected, do nothing
    if (previous_selection == selected_item) and current_ads_connection:
        print("Target already connected")
        messagebox.showinfo("Attention", "Target already connected")
        return

    previous_selection = selected_item  # Update the previously selected item
    
    # Close any existing connection when the selection changes
    if  current_ads_connection:
        # status_label.update_idletasks()
        disable_control_buttons()
        close_current_connection()
        messagebox.showinfo("Attention", "Connection Closed")
    
    update_ui_connection_status("Disconnected", "red", status_label)

    tc_type = get_lgv_data()[2]

    if tc_type == 'TC3':
        core_check.config(state='normal')
    else:
        core_check.config(state='disabled')

# Enable control buttons after a successful connection
def enable_control_buttons():
    lgv_buttons = (reset_button, run_button, stop_button, man_auto_button, dis_horn_button)

    for button in lgv_buttons:
        button.config(state="normal")
    stop_button.config(style="LGV.Pressed.TButton")

def disable_control_buttons():
    lgv_buttons = (reset_button, run_button, stop_button, man_auto_button, dis_horn_button)
    
    for button in lgv_buttons:
        button.config(style="LGV.TButton")
        button.config(state="disabled")

def on_core_check():
    if is_core.get():
        print("Core library present")
    else:
        print("Normal library")


####################################################################################################################################################################
#################################################################### Write variables ###############################################################################
####################################################################################################################################################################
# Dictionary to map variable names for each action based on conditions
variable_write = {
    'reset': {
        'TC2': ".ADS_Reset",
        ('TC3', False): "Load_Handling.ADS_Reset",
        ('TC3', True): "CoreGVL.ADS_Reset"
    },
    'run': {
        'TC2': ".ADS_Run",
        ('TC3', False): "Load_Handling.ADS_Run",
        ('TC3', True): "CoreGVL.ADS_Run"
    },
    'stop': {
        'TC2': ".ADS_Stop",
        ('TC3', False): "Load_Handling.ADS_Stop",
        ('TC3', True): "CoreGVL.ADS_Stop"
    },
    'man_auto': {
        'TC2': ".ADS_MCD_Mode",
        ('TC3', False): "Load_Handling.ADS_MCD_Mode",
        ('TC3', True): "CoreGVL.ADS_MCD_Mode"
    },
    'dis_horn': {
        'TC2': ".ADS_DisableHorn",
        ('TC3', False): "Output.DisableHorn",
        ('TC3', True): "Output.disableHorn"
    }
}


def write_variable(action, tc_type, is_core, value):
    global current_ads_connection

    # Select the appropriate variable name for the action, based on tc_type and is_core
    if tc_type == 'TC2':
        variable_name = variable_write[action]['TC2']  # For TC2, ignore is_core
    else:
        variable_name = variable_write[action][('TC3', is_core)]  # For TC3, consider is_core

    if current_ads_connection is not None:
        try:
            # Write the value to the PLC
            current_ads_connection.write_by_name(variable_name, value, pyads.PLCTYPE_BOOL)
            print(f"Successfully wrote {value} to {variable_name} for action: {action}")
            return True
        except Exception as e:
            messagebox.showerror("Write Error", f"Failed to write to {variable_name}: {str(e)}")
            print(f"Failed to write to {variable_name}: {str(e)}")
    else:
        print("Connection Error", "No active connection to write to.")
        # messagebox.showerror("Connection Error", "No active connection to write to.")
    return False
    

# Variable to track toggle state for dis_horn
dis_horn_state = False

def on_dis_horn_button_click(button):
    global dis_horn_state
    lgv_data = get_lgv_data()
    
    if lgv_data is None:
        return
    tc_type = lgv_data[2]

    # Toggle the state of dis_horn
    dis_horn_state = not dis_horn_state
    success_write = write_variable('dis_horn', tc_type, is_core.get(), dis_horn_state)
    if success_write:   
        print(f"Disable Horn pressed, value: {dis_horn_state}")
    else:
        dis_horn_state= False
        print(f"Disable Horn presse unsuccessful, value: {dis_horn_state}")

press_successful = False
cooldown_active = False  # Variable to track cooldown state
interaction_in_progress = False # Track pres-release cycle

def on_button_action(action, value, button, is_release=False):
    global press_successful, cooldown_active, interaction_in_progress

    if cooldown_active:
        return
    
    if not is_release:
        interaction_in_progress = True
    
    button_state = button.cget("state").string
    if  button_state != 'normal':
        return
    
    lgv_data = get_lgv_data()
    
    if lgv_data is None:
        # messagebox.showerror("Error", "No LGV selected or invalid data.")
        press_successful = False
        return
    tc_type = lgv_data[2]

    # Write the value (True or False) for the specific action
    press_successful = write_variable(action, tc_type, is_core.get(), value)

    # press_successful = True

    # Change button color only for reset, stop, and man_auto actions
    if action in ['reset', 'stop', 'man_auto']:
        # Change button color based on press/release value
        if value and press_successful:  # If pressed (True)
            button.config(style="LGV.Pressed.TButton")
        else:  # If released (False)
            button.config(style="LGV.TButton")
    
    if is_release and interaction_in_progress:
        interaction_in_progress = False
        cooldown_active = True
        button.after(100, lambda: end_cooldown())  # End cooldown after 500ms

    if press_successful:    
        print(f"Button {action} is pressed and value is {value}")
    else:
        print(f"Press {action} unsuccessful")

def end_cooldown():
    global cooldown_active
    cooldown_active = False  # Cooldown ended, button can be pressed again


def bind_button_actions(button, action, press_value=True, release_value=False):
    global press_successful

    def on_button_press(event):
        on_button_action(action, press_value, button)
    
    def on_button_release(event):
        if press_successful:
            on_button_action(action, release_value, button, is_release=True)
        else:
            button.config(state="normal")
            # Delay resetting the button's visual state to avoid it appearing pressed
            button.after(50, lambda: button.state(['!pressed', '!active']))  # Slight delay
        # Shift focus away after a small delay
        # button.after(50, lambda: button.winfo_toplevel().focus_force())

    button.bind("<ButtonPress>", lambda event: on_button_press(event))
    button.bind("<ButtonRelease>", lambda event: on_button_release(event))

# def on_button_action_wrapper(action, press_value, release_value, button):
#     global press_successful
#     on_button_action(action, press_value, button)

#     if press_successful:
#         # Attempt write release value only if press value was successful
#         on_button_action(action, release_value, button, is_release=True)


# release_bound = False # Track is released event was bound

def on_button_action_wrapper(action, press_value, release_value, button):
    global press_successful

    on_button_action(action, press_value, button)

    if press_successful:
        # Wait for the user to release the button to send the release value
        button.bind("<ButtonRelease>", lambda event: on_button_release(action, release_value, button))

def on_button_release(action, release_value, button):
    global press_successful

    # try:    
        # if press_successful:
            # Release action: simulate releasing the button and sending the value
    on_button_action(action, release_value, button, is_release=True)
 
    # finally:
            # Unbind the release event to prevent multiple triggers
    button.unbind("<ButtonRelease>")
            # release_bound = False



####################################################################################################################################################################
##################################################################### Read variables ###############################################################################
####################################################################################################################################################################
variable_read = {
    'reset': {  
        'TC2': ".Button_Reset",
        ('TC3', False): "LGV.Status.manReset",
        ('TC3', True): "LibraryInterfaces.LGV.Status.manReset"
    },
    'run': {
        'TC2': ".OUT_Lamp_Top_Auto",
        ('TC3', False): "SafetyControls.alert.out.lampRunButton",
        ('TC3', True): "SafetyControls.alert.out.lampRunButton"
    },
    'stop': {
        'TC2': "Input.Button_Stop",
        ('TC3', False): "LGV.Status.ButtonStop",
        ('TC3', True): "LibraryInterfaces.LGV.Status.ButtonStop"
    },
    'man_auto': {
        'TC2': ".Sys_Mcd_Mode",
        ('TC3', False): "LGV.Status.MCD_Mode",
        ('TC3', True): "LibraryInterfaces.LGV.Status.MCD_Mode"
    },
    'dis_horn': {
        'TC2': ".ADS_DisableHorn",
        ('TC3', False): "Output.DisableHorn",
        ('TC3', True): "Output.disableHorn"
    }
}

def read_variable(action):
    lgv_data = get_lgv_data()
    tc_type = lgv_data[2]
    is_core_value = is_core.get()

    # Fetch the variable name based on the TC type and is_core flag
    var_name = variable_read[action].get(tc_type) if tc_type == "TC2" else variable_read[action].get((tc_type, is_core_value))

    if var_name and current_ads_connection is not None:
        # Read the value from the PLC
        try:
            return current_ads_connection.read_by_name(var_name, pyads.PLCTYPE_BOOL)
        except Exception as e:
            print(f"Error reading variable {var_name}: {e}")
            return None
    return None

def update_button_color(action, button, read_value):
    if read_value is None:
        return
    # Change the button's foreground color based on the read_value
    if read_value:  # If the PLC variable is True
        button.configure(style='LGV.Connected.TButton')
    else:  # If the PLC variable is False
        button.configure(style='LGV.Disconnected.TButton')

def update_buttons():
    if current_ads_connection is None:
        return
    # Read variables and update button colors for all actions
    actions = ['reset', 'run', 'stop', 'man_auto', 'dis_horn']
    
    # Mapping actions to buttons
    button_mapping = {
        'reset': reset_button,
        'run': run_button,
        'stop': stop_button,
        'man_auto': man_auto_button,
        'dis_horn': dis_horn_button
    }
    
    for action in actions:
        read_value = read_variable(action)  # Read value from PLC
        button = button_mapping[action]
        update_button_color(action, button, read_value)
    
    # Schedule the function to run again after 2s
    root.after(50, update_buttons)

read_lock = threading.Lock()

def update_buttons_from_plc_thread():
    global current_ads_connection

    # if current_ads_connection is None:
    #     return
        
    # Read variables and update button colors for all actions
    # actions = ['reset', 'run', 'stop', 'man_auto', 'dis_horn']
    actions = ['run', 'dis_horn']
    
    # Mapping actions to buttons
    button_mapping = {
        # 'reset': reset_button,
        'run': run_button,
        # 'stop': stop_button,
        # 'man_auto': man_auto_button,
        'dis_horn': dis_horn_button
    }
    
    # with read_lock:
    for action in actions:
        if current_ads_connection is None:
            return
        read_value = read_variable(action)  # Read value from PLC
        button = button_mapping[action]
    
        root.after(0, update_button_color, action, button, read_value)
    

    t = threading.Timer(0.1, update_buttons_from_plc_thread)
    t.daemon = True 
    t.start()

####################################################################################################################################################################
############################################################## Treeview setup and sorting ##########################################################################
####################################################################################################################################################################

# Read the tc_type from the current selection
def get_lgv_data():
    selected_item = treeview.selection()
    if not selected_item:
        # messagebox.showerror("Error", "No LGV selected")
        return None

    lgv_data = treeview.item(selected_item)["values"]
    # tc_type = lgv_data[2]
    return lgv_data


# Dictionary to maintain custom headings
headings = {
    'Name': 'Name',
    'NetId': 'AMS Net Id',
    'Type': 'Type'
}

def setup_treeview():
    for col in treeview['columns']:
        treeview.heading(col, text=headings[col], command=lambda _col=col: treeview_sort_column(treeview, _col, False), anchor='w')

def treeview_sort_column(tv, col, reverse):
    # Retrieve all data from the treeview
    l = [(tv.set(k, col), k) for k in tv.get_children('')]
    
    # Sort the data
    l.sort(reverse=reverse, key=lambda t: natural_keys(t[0]))

    # Rearrange items in sorted positions
    for index, (val, k) in enumerate(l):
        tv.move(k, '', index)

    # Change the heading to show the sort direction
    for column in tv['columns']:
        heading_text = headings[column] + (' ↓' if reverse and column == col else ' ↑' if not reverse and column == col else '')
        tv.heading(column, text=heading_text, command=lambda _col=column: treeview_sort_column(tv, _col, not reverse))

def natural_keys(text):
    """
    Alphanumeric (natural) sort to handle numbers within strings correctly
    """
    return [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', text)]


####################################################################################################################################################################
####################################################################### Create UI ##################################################################################
####################################################################################################################################################################

############################# Set GUI icon ##########################
def set_icon():
    if os.path.exists(icon_path):
        root.iconbitmap(icon_path)
    else:
        print("Icon file not found.")


# Create the root window
root = tk.Tk()
root.title(f"Super ADS Client {__version__}")
# root.geometry("600x400")  # Adjust the window size

# Check if running as a script or frozen executable
if getattr(sys, 'frozen', False):
    icon_path = os.path.join(sys._MEIPASS, __icon__)
else:
    icon_path = os.path.abspath(__icon__)
# root.iconbitmap(icon_path)

# Apply the icon after the window is initialized
root.after(100, set_icon)

style = ttk.Style()

style.configure("LGV.TButton", 
                padding=(4,4),
                anchor="center",
                foreground='black', 
                font=("Segoe UI", 18))

style.configure("LGV.Pressed.TButton", 
                padding=(4,4),
                anchor="center",
                foreground='#2D68C4', 
                font=("Segoe UI", 18, "bold"))
# #1E90FF, #1560bd, #005A9C, #1877F2, #0071c5, #1C39BB, #2D68C4

style.configure("LGV.Connected.TButton", 
                padding=(4,4),
                anchor="center",
                foreground='green', 
                font=("Segoe UI", 18, "bold"))

style.configure("LGV.Disconnected.TButton", 
                padding=(4,4),
                anchor="center",
                foreground='red',  
                font=("Segoe UI", 18))

style.configure("Connect.TButton",
                padding=2,
                font=("Segoe UI", 13))


# menu_bar = tk.Menu(root)
# file_menu = tk.Menu(menu_bar, 
#                     tearoff=0)
# file_menu.add_command(label="Load Config.db3", command=populate_table_from_db3)
# menu_bar.add_cascade(label="File", menu=file_menu)
# root.config(menu=menu_bar)


# load_config_button = ttk.Button(root, text="Load Config.db3", command=populate_table_from_db3)
# load_config_button.grid(row=0, column=0, padx=5, pady=5)

footer_frame = ttk.Frame(root)
footer_frame.grid(row=0, column=0, sticky='nsw', padx=5, pady=5)
load_config_button = ttk.Button(footer_frame, text="     Load \nconfig.db3", command=populate_table_from_db3)
load_config_button.pack()

separator = ttk.Separator(root, orient='vertical')
separator.grid(row=0, column=0, sticky='ns', pady=10)

frame_connect = ttk.Frame(root)
frame_connect.grid(row=0, column=0, padx=0, pady=0, sticky='e')
# Add a button to connect to the PLC
connect_button = ttk.Button(frame_connect, text="Connect", command=lambda: connect_to_plc(treeview, status_label), style='Connect.TButton')
connect_button.grid(row=0, column=1, padx=5, ipady=4, sticky='e')

is_core = tk.IntVar()
core_check = ttk.Checkbutton(frame_connect, text="IsCore", variable=is_core, command=on_core_check)
core_check.grid(row=0, column=0, padx=0, pady=0)
core_check.config(state='disabled')



# Connection status label
status_label = ttk.Label(root, text="Disconnected", foreground="red", font=("Segoe UI", 13))
status_label.grid(row=0, column=1, padx=5, pady=5)




# Create a frame for the table (Treeview)
table_frame = ttk.Frame(root)
table_frame.grid(row=1, column=0, padx=15, pady=25, sticky='nsew')

treeview_style = ttk.Style()
treeview_style.configure("Treeview", rowheight=23)  # Increase row height for more space between items
treeview_style.configure("Treeview", font=("Segoe UI", 10))  # Adjust font size if necessary
treeview_style.configure("Treeview", padding=(5, 5))  # Add padding to rows (optional)

# Create the Treeview (table)
columns = ("Name", "NetId", "Type")
treeview = ttk.Treeview(table_frame, columns=columns, show="headings")

# Define the column widths
treeview.column("Name", width=80, anchor='w')
treeview.column("NetId", width=120, anchor='w')
treeview.column("Type", width=50, anchor='w')

setup_treeview()

# Add the treeview to the table frame
treeview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

treeview.bind("<<TreeviewSelect>>", on_treeview_select)

# Create a vertical scrollbar for the table
scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=treeview.yview)
treeview.configure(yscroll=scrollbar.set)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)




# Create a frame for the buttons
button_frame = ttk.Frame(root, width=170, height=350)
button_frame.pack_propagate(False)
button_frame.grid(row=1, column=1, padx=10, pady=10, sticky='ew')


# Add some buttons to the right frame
reset_button = ttk.Button(button_frame, 
                          text="Reset", 
                          style='LGV.TButton')
                        #   command=lambda: bind_button_actions(reset_button, 'reset'))
                        #   command=lambda: on_button_action_wrapper('reset', True, False, reset_button))
reset_button.pack(pady=5, fill='both', expand=True, ipady=3)
bind_button_actions(reset_button, 'reset')

run_button = ttk.Button(button_frame, 
                        text="Run",
                        style='LGV.TButton')
                        # command=lambda: on_button_action_wrapper('run', True, False, run_button))
run_button.pack(pady=5, fill='both', expand=True, ipady=3)
bind_button_actions(run_button, 'run')

stop_button = ttk.Button(button_frame, 
                         text="Stop", 
                         style='LGV.Pressed.TButton')
                        #  command=lambda: on_button_action_wrapper('stop', False, True, stop_button))
stop_button.pack(pady=5, fill='both', expand=True, ipady=3)
bind_button_actions(stop_button, 'stop', press_value=False, release_value=True)

man_auto_button = ttk.Button(button_frame, 
                             text="Man/Auto",
                             style='LGV.TButton')
                            #  command=lambda: on_button_action_wrapper('man_auto', True, False, man_auto_button))
man_auto_button.pack(pady=5, fill='both', expand=True, ipady=3)
bind_button_actions(man_auto_button, 'man_auto')

dis_horn_button = ttk.Button(button_frame, 
                             text="Disable Horn", 
                             style='LGV.TButton',
                             command=lambda: on_dis_horn_button_click(dis_horn_button))
dis_horn_button.pack(pady=5, fill='both', expand=True, ipady=3)


disable_control_buttons()
# enable_control_buttons()

load_table_data_from_xml(treeview)


def on_closing():
    close_current_connection()  # Close connection before exiting
    root.destroy()  # Close the application

# Bind the window close event to custom close function
root.protocol("WM_DELETE_WINDOW", on_closing)



root.mainloop()


# 1. select LGV, 
# changing lgv drops previous connection


# two inputs, table or manual entry. In manual add just ip, maybe not needed now that table is updated since the beginning

# reset, run, stop, manual/auto and disable horn only needed

# Avoid to enable connection when the user click connect more than once

# Add colors to the buttons, at least for the horn, and reset that variable whenever there's a new connection

# Connected/Disconnedted label doesn't change from conencted to disconnected when another selection is made, maybe set this to default when connection is closed