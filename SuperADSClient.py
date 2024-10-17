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
import json
from queue import Queue, Empty

__version__ = '2.1.2 Beta 13'
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

monitor_timer = None

def monitor_connection_status():
    global current_ads_connection, monitor_timer

    if current_ads_connection is None:
        return
    
    try:
        if check_plc_status(current_ads_connection):
            update_status_in_queue("Connected", "green")
        else:
            raise Exception("PLC not in valid state")
    except Exception as e:
        # assume connection is lost if not status 5 is read
        disable_control_buttons()
        update_status_in_queue("Disconnected", "red")
        close_current_connection()

    if monitor_timer:
        monitor_timer.cancel()

    monitor_timer = threading.Timer(1.0, monitor_connection_status)
    monitor_timer.daemon = True
    monitor_timer.start()  

    
def check_plc_status(ads_connection):
    status = ads_connection.read_state()[0]
    if status == 5:
        return True
    return False

# Close the current connection if it exists
def close_current_connection():
    global current_ads_connection, dis_horn_state, connection_in_progress, is_core, monitor_timer
    with connection_lock:
        connection_in_progress = False
        if current_ads_connection:
            current_ads_connection.close()
            current_ads_connection = None
            dis_horn_state = False #reset horn state
            is_core = False
            core_status_label.config(text="No Core Lib")
        
        if monitor_timer:
            monitor_timer.cancel()
            monitor_timer = None

        update_status_in_queue("Disconnected", "red")

# Background connection handler (runs in a separate thread)
def background_connect(plc_data):
    global current_ads_connection, connection_in_progress

    # If already connected, don't try to reconnect
    if current_ads_connection is not None:
        return
    
    try:        
        lgv_name, ams_net_id, tc_type = plc_data
        port = 851 if tc_type == 'TC3' else 801
        # ip_address = ".".join(str(ams_net_id).split(".")[:4])
        update_status_in_queue("Connecting...", "orange")

        # Attempt to open a new connection
        current_ads_connection = pyads.Connection(ams_net_id, port)
        current_ads_connection.open()

        # Check PLC status
        if check_plc_status(current_ads_connection):
            update_status_in_queue("Connected", "green")
            enable_control_buttons()

            # Automatically detect core variable
            check_for_core_variable()
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
        update_status_in_queue("Disconnected", "red")
        messagebox.showerror("Connection Error", f"Failed to connect to {lgv_name}: {str(e)}")
        treeview.selection_remove(treeview.selection())

    finally:
        with connection_lock:
            connection_in_progress = False
            if current_ads_connection is None:
                update_status_in_queue("Disconnected", "red")


current_status = None

# Update the UI status label (called from the main thread)
def update_ui_connection_status(text, color):
    global current_status
    if current_status != text:
        current_status = text
        status_label.config(text=text, foreground=color)

status_queue = Queue()

def process_status_updates():
    try:
        status, color = status_queue.get_nowait()
        update_ui_connection_status(status, color)
    except Empty:
        pass
    root.after(100, process_status_updates)

status_lock = threading.Lock()
# Use the queue for updating the status
def update_status_in_queue(status, color):
    with status_lock:
        status_queue.put((status, color))


connection_lock = threading.Lock()
# Attempt to connect to the selected PLC (starts in a new thread)
def connect_to_plc(tree):
    global connection_in_progress, current_ads_connection
    
    with connection_lock:
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
        connection_in_progress = True
        connection_thread = threading.Thread(target=background_connect, args=(lgv_data,))
        connection_thread.start()


previous_selection = None # track previous connection

connection_in_progress = False
# Close the current connection when selection changes
def on_treeview_select(event):
    global current_ads_connection, previous_selection, connection_in_progress, dis_horn_state
    # Get the currently selected LGV
    
    try:
        selected_item = treeview.selection()
        if not selected_item:
            return
        
        if connection_in_progress:
            print("Connection in progress. Waiting for it to finish. Triggered on select")
            messagebox.showinfo("Attention", "Connection in progress. Waiting for it to finish. Triggered on select")
            treeview.selection_remove(treeview.selection())
            return

        # If the same item is selected, do nothing
        if (previous_selection == selected_item) and current_ads_connection:
            print("Target already connected")
            messagebox.showinfo("Attention", "Target already connected")
            return
        
        old_selection = previous_selection

        previous_selection = selected_item  # Update the previously selected item
        
        # Close any existing connection when the selection changes
        if  current_ads_connection:
            # status_label.update_idletasks()
            
            # messagebox.showinfo("Attention", "Connection Closed")
            if read_variable('disable_horn'):
                old_lgv_name = treeview.item(old_selection)["values"][0]
                messagebox.showwarning("Attention", f"Horn in {old_lgv_name} is disabled!")

            disable_control_buttons()
            close_current_connection()
            
    finally:
        update_status_in_queue("Disconnected", "red")

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
    if is_core:
        print("Core library present")
    else:
        print("Normal library")


####################################################################################################################################################################
#################################################################### Write variables ###############################################################################
####################################################################################################################################################################
# Dictionary to map variable names for each action based on conditions
default_variable_write = {
    'reset': {
        'TC2': ".ADS_Reset",
        'TC3': {
            'core': "CoreGVL.ADS_Reset",
            'no_core': "Load_Handling.ADS_Reset"
        }
    },
    'run': {
        'TC2': ".ADS_Run",
        'TC3': {
            'core': "CoreGVL.ADS_Run",
            'no_core': "Load_Handling.ADS_Run"
        }
    },
    'stop': {
        'TC2': ".ADS_Stop",
        'TC3': {
            'core': "CoreGVL.ADS_Stop",
            'no_core': "Load_Handling.ADS_Stop"
        }
    },
    'man_auto': {
        'TC2': ".ADS_MCD_Mode",
        'TC3': {
            'core': "CoreGVL.ADS_MCD_Mode",
            'no_core': "Load_Handling.ADS_MCD_Mode"
        }
    },
    'disable_horn': {
        'TC2': ".ADS_DisableHorn",
        'TC3': {
            'core': "Output.disableHorn",
            'no_core': "Output.DisableHorn"
        }
    }
}

def reset_to_defaults():
    global variable_write
    if os.path.exists("variables_config.json"):
        os.remove("variables_config.json")
        messagebox.showinfo("Reset", "Variables have been reset to defaults.")
        update_menu()

    # else:
        # messagebox.showinfo("Reset", "No saved configuration found.")

# Function to update the menu item based on whether the JSON file exists
def update_menu():
    if os.path.exists("variables_config.json"):
        options_menu.entryconfig("Reset to Defaults ", state="normal")  # Enable if file exists
    else:
        options_menu.entryconfig("Reset to Defaults ", state="disabled")  # Disable if file doesn't exist


# Load variables from JSON or fall back to defaults
def load_variables():
    # Load variables from JSON and override the defaults with user values if available
    variables = default_variable_write.copy()

    if os.path.exists("variables_config.json"):
        with open("variables_config.json", "r") as json_file:
            user_variables = json.load(json_file)

        # Overwrite defaults with the ones from the user
        for key, user_value in user_variables.items():
            if key in variables:
                variables[key].update(user_value) 
    
    return variables


def save_user_input(plc_type, is_core, variables):
    global variable_write

    # Load the existing variables from the JSON file if it exists
    existing_vars = {}
    if os.path.exists("variables_config.json"):
        with open("variables_config.json", "r") as json_file:
            existing_vars = json.load(json_file)

    non_empty_found = False  # Track if the user has entered valid input
    user_variables = {}  # Store only user-modified variables

    # Iterate through user input and process based on selection
    for key, value in variables.items():
        if value.strip():  # Ignore empty values
            non_empty_found = True

            if plc_type == "TC2":
                # Save only if the new value differs from the current one
                if existing_vars.get(key, {}).get('TC2') != value:
                    user_variables.setdefault(key, {})['TC2'] = value

            elif plc_type == "TC3":
                core_key = 'core' if is_core else 'no_core'
                # Save only if the new value differs from the current one
                if existing_vars.get(key, {}).get('TC3', {}).get(core_key) != value:
                    user_variables.setdefault(key, {}).setdefault('TC3', {})[core_key] = value

    # If no valid input was provided, do not save anything
    if not non_empty_found:
        print("No non-empty values found, skipping save.")
        messagebox.showwarning("Attention", "Add a value to save.")
        return

   # Recursively merge existing variables with user-modified variables
    merged_vars = merge_dicts(existing_vars, user_variables)

    # Save only if there are new or modified variables
    if user_variables:  # Save only user-modified content, no defaults
        with open("variables_config.json", "w") as json_file:
            json.dump(merged_vars, json_file, indent=4)  # Save the final state
        print(f"Variables saved for {plc_type} {'' if plc_type == 'TC2' else 'with core' if is_core else 'with no core'}")
        messagebox.showinfo("Success", f"Variables saved for {plc_type} {'' if plc_type == 'TC2' else 'with core' if is_core else 'with no core'}")
    else:
        print("No changes detected, nothing to save.")

    # Reload variables after saving to reflect the latest state
    variable_write = load_variables()
    update_menu()  # Update the reset button state


def merge_dicts(existing, new):
    """Recursively merge two dictionaries."""
    for key, value in new.items():
        if isinstance(value, dict) and key in existing:
            # Recursively merge nested dictionaries
            existing[key] = merge_dicts(existing.get(key, {}), value)
        else:
            # Update or add the new value
            existing[key] = value
    return existing

def write_variable(action, tc_type, is_core, value, button):
    global current_ads_connection

    # Select the appropriate variable name for the action, based on tc_type and is_core
    if tc_type == 'TC2':
        variable_name = variable_write[action]['TC2']  # For TC2, ignore is_core
    else:
        core_key = 'core' if is_core else 'no_core'
        variable_name = variable_write[action]['TC3'][core_key]  # For TC3, use core/no_core

    if current_ads_connection is not None:
        try:
            # Write the value to the PLC
            current_ads_connection.write_by_name(variable_name, value, pyads.PLCTYPE_BOOL)
            print(f"Successfully wrote {value} to {variable_name} for action: {action}")
            return True
        except Exception as e:
            messagebox.showerror("Write Error", f"Failed to write to {variable_name}: {str(e)}")
            print(f"Failed to write to {variable_name}: {str(e)}")
        finally:
            button.config(state="normal")
            # Delay resetting the button's visual state to avoid it appearing pressed
            button.after(0, lambda: button.state(['!pressed', '!active']))  # Slight delay

    else:
        print("Connection Error", "No active connection to write to.")
        # messagebox.showerror("Connection Error", "No active connection to write to.")
    return False
    

# Variable to track toggle state for disable_horn

def on_dis_horn_button_click(button):
    global dis_horn_state

    # Get initial state of disable_horn variable to toggle it
    dis_horn_state = read_variable('disable_horn') 

    lgv_data = get_lgv_data()
    
    if lgv_data is None:
        return
    tc_type = lgv_data[2]

    # Toggle the state of disable_horn
    dis_horn_state = not dis_horn_state
    success_write = write_variable('disable_horn', tc_type, is_core, dis_horn_state, button)
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
    press_successful = write_variable(action, tc_type, is_core, value, button)

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
        # else:
        #     button.config(state="normal")
        #     # Delay resetting the button's visual state to avoid it appearing pressed
        #     button.after(10, lambda: button.state(['!pressed', '!active']))  # Slight delay
        # # Shift focus away after a small delay
        # # button.after(50, lambda: button.winfo_toplevel().focus_force())

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
    'disable_horn': {
        'TC2': ".ADS_DisableHorn",
        ('TC3', False): "Output.DisableHorn",
        ('TC3', True): "Output.disableHorn"
    }
}

# Variable to store core status
is_core = False

def check_for_core_variable():
    global is_core 
    try:
        # Attempt to read the core variable
        core_value = current_ads_connection.read_by_name("CoreGVL.ADS_Run", pyads.PLCTYPE_BOOL)
        
        # If the core variable is read successfully, set the variable and update the label
        if core_value is not None:
            is_core = True  # Set the variable to True (core detected)
            core_status_label.config(text="      Core Lib")
        else:
            is_core = False  # Set the variable to False (core not detected)
            core_status_label.config(text="No Core Lib")
            
    except Exception as e:
        is_core = False  # Handle error, set core status to "not detected"
        core_status_label.config(text="No Core Lib")


def read_variable(action):
    lgv_data = get_lgv_data()
    tc_type = lgv_data[2]
    is_core_value = is_core

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
    actions = ['reset', 'run', 'stop', 'man_auto', 'disable_horn']
    
    # Mapping actions to buttons
    button_mapping = {
        'reset': reset_button,
        'run': run_button,
        'stop': stop_button,
        'man_auto': man_auto_button,
        'disable_horn': dis_horn_button
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
    # actions = ['reset', 'run', 'stop', 'man_auto', 'disable_horn']
    actions = ['run', 'disable_horn']
    
    # Mapping actions to buttons
    button_mapping = {
        # 'reset': reset_button,
        'run': run_button,
        # 'stop': stop_button,
        # 'man_auto': man_auto_button,
        'disable_horn': dis_horn_button
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
################################################################ Window To Set Variables ###########################################################################
####################################################################################################################################################################

variable_window = None 

def open_variable_window_cond():
    global variable_window

    if variable_window is None or not variable_window.winfo_exists():
        open_variable_window()

def open_variable_window():
    global variable_window

    variable_window = tk.Toplevel(root)
    variable_window.title("Set Variables")

    variable_window.resizable(False,False)

    # Radio buttons for TC2 and TC3
    plc_type = tk.StringVar(value="TC2") # Default is TC2

    def toggle_is_core():
        if plc_type.get() == "TC3":
            core_checkbox.config(state="normal")
        else:
            core_checkbox.config(state="disabled")
            is_core.set(False)  # Reset core to False when TC2 is selected

    frame_tc_type = tk.Frame(variable_window)
    frame_tc_type.grid(row=0, column=0, columnspan=3, padx=5, pady=5)
     # PLC Type Selection (TC2 or TC3)
    ttk.Radiobutton(frame_tc_type, text="TC2", variable=plc_type, value="TC2", command=toggle_is_core).grid(row=0, column=0, padx=10)
    ttk.Radiobutton(frame_tc_type, text="TC3", variable=plc_type, value="TC3", command=toggle_is_core).grid(row=0, column=1, padx=10)

    # Core Selection (only enabled for TC3)
    is_core = tk.BooleanVar()
    core_checkbox = ttk.Checkbutton(frame_tc_type, text="Is Core", variable=is_core, state="disabled")
    core_checkbox.grid(row=0, column=3, padx=15)

    entries = {}
    frame_vars = tk.Frame(variable_window)
    frame_vars.grid(row=2, column=0, pady=5, padx=5)
    # Labels and Entries
    labels = ["Reset", "Run", "Stop", "Man Auto", "Disable Horn"]
    for i, label_text in enumerate(labels):
        ttk.Label(frame_vars, text=label_text).grid(row=i, column=0, padx=5, pady=10, sticky='e')
        entry = ttk.Entry(frame_vars, width=50)
        entry.grid(row=i, column=1, padx=10, pady=10)
        entries[label_text] = entry

    # Save button to capture and save the inputs
    def save():
        # Gather variables using the entries dictionary
        variables = {key.lower().replace(" ", "_"): entry.get() for key, entry in entries.items()}

        # Call the function to save user input
        save_user_input(plc_type.get(), is_core.get(), variables)

    frame_setvar = tk.Frame(variable_window)
    frame_setvar.grid(row=3, column=0, padx=5, pady=5)
    ttk.Button(frame_setvar, text="Save", command=save).grid(row=0, column=0, pady=10, padx=10, ipadx=5, ipady=5)
    # ttk.Button(frame_setvar, text="Reset", command=reset_to_defaults).grid(row=0, column=1, pady=10, padx=10, ipadx=5, ipady=5)

    # Handle window close event to reset the reference
    variable_window.protocol("WM_DELETE_WINDOW", on_variable_window_close)

def on_variable_window_close():
    global variable_window
    variable_window.destroy()  # Destroy the window
    variable_window = None  # Reset the reference so it can be reopened
   

####################################################################################################################################################################
######################################################## Window To Read/Write Custom Variables #####################################################################
####################################################################################################################################################################
def open_read_write_window():
    read_write_window = tk.Toplevel(root)
    read_write_window.title("Set Variables")

    read_write_window.resizable(False,False)


    # entry to input LGV range

    # drop down menu to add and save variables

    # frame to add radio buttons for TRUE FALSE or Value (in a entry) when writing

    # Frame with two buttons (read / write)

    # Widget to show results when reading (enable only with reading)

    # Read and write will be multi thread


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


# Create the menu bar
menu_bar = tk.Menu(root)

file_menu = tk.Menu(menu_bar, tearoff=0)
file_menu.add_command(label=" Load Config.db3 ", command=populate_table_from_db3)  # Add Load Config option
file_menu.add_command(label=" Exit ", command=root.quit)  # Add Exit option
menu_bar.add_cascade(label="  File ", menu=file_menu)


options_menu = tk.Menu(menu_bar, tearoff=0)
options_menu.add_command(label="Set Variables    ", command=open_variable_window_cond)
options_menu.add_command(label="Reset to Defaults ", command=reset_to_defaults)

menu_bar.add_cascade(label=" Options  ", menu=options_menu)    

root.config(menu=menu_bar)

# Update the menu based on whether the file exists
update_menu()


frame_connect = ttk.Frame(root, width=100)
# frame_connect.grid_propagate(False)
frame_connect.grid(row=0, column=0, padx=20, pady=5)

# Add a button to connect to the PLC
connect_button = ttk.Button(frame_connect, text="Connect", command=lambda: connect_to_plc(treeview), style='Connect.TButton')
connect_button.grid(row=0, column=1, padx=10, ipady=4, sticky='w')

# Create a label as an indicator
core_status_label = ttk.Label(frame_connect, text="No Core Lib", foreground="#4682B4") # #3CB371, #6495ED, 4682B4
core_status_label.grid(row=0, column=0, padx=20, pady=0, sticky='e')



# Connection status label
status_label = ttk.Label(root, text="Disconnected", foreground="red", font=("Segoe UI", 13))
status_label.grid(row=0, column=1, padx=5, pady=5)




# Create a frame for the table (Treeview)
table_frame = ttk.Frame(root)
table_frame.grid(row=1, column=0, padx=10, pady=20, sticky='nsew')

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

variable_write = load_variables()

root.after(100, process_status_updates)

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