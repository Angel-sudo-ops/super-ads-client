import sqlite3
import tkinter as tk
from tkinter import ttk, font, messagebox, filedialog
import tkinter.scrolledtext as scrolledtext
import re
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
import sys
import threading
import time
import json
from queue import Queue, Empty
import copy
import subprocess
import platform
# from ctypes import sizeof

try:
    import pyads
    pyads_available = True
except Exception as e:
    print(f"Error: {e}")
    pyads_available = False
    pyads = None

if not pyads_available:
    # messagebox.showerror("Attention", "No pyads available")
    print("No pyads available")

__version__ = '2.5.1.4'
__icon__ = "./plc.ico"

TAB_NAME = ['Control', 'RW Panel']

MAX_WORKERS = 5
LGV_DATA = "lgv_data.xml"
# Variable to hold the current ads connection
current_ads_connection = None

connection_active = False

####################################################################################################################################################################
########################################################## Initial data reading from xml file ######################################################################
####################################################################################################################################################################
def extract_lgv_name(input_name):
    # Regex pattern to capture 'LGV' followed by numbers
    pattern = r"(LGV\d+)"
    match = re.search(pattern, input_name)
    if match:
        return match.group(1)  # Return the matched 'LGVxx' or 'LGVxxx'
    return None

def populate_table_from_xml_test():
    print("Load StaticRoutes.xml file")

def populate_table_from_xml(path=None):
    if not path:
        # Ask the user to select an XML file
        file_path = filedialog.askopenfilename(title="Select StaticRoutes file",
                                            initialdir="C:\\TwinCAT\\3.1\\Target",
                                            filetypes=[("XML files", "*.xml")])
    else:
        file_path = path

    if file_path and not os.path.exists(file_path):
        print(f"The file {path} does not exist.")
        return

    if file_path:
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except ET.ParseError:
            messagebox.showerror("Error", "The selected file is not a valid XML file.")
            return

        # Check for the expected root elements
        remote_connections = root.find('RemoteConnections')
        if remote_connections is None:
            messagebox.showerror("Error", "XML file does not contain the expected 'RemoteConnections' structure.")
            return

        data = treeview.get_children()
        # Clear the existing table data
        if data is not None:
            for i in data:
                treeview.delete(i)

        # Initialize an empty list to hold the data
        routes_data = []
        seen_lgv_names = set()
        invalid_routes = []

        # Iterate through each <Route> element in the XML
        for route in remote_connections.findall('Route'):
            name = route.find('Name')
            address = route.find('Address')
            net_id = route.find('NetId')

            if None in (name, address, net_id):
                messagebox.showwarning("Warning", "One or more routes are missing required fields (Name, Address, NetId).")
                invalid_routes.append("Missing fields (Name, Address, NetId)")
                continue  # Skip this route and move to the next

            name = name.text
            address = address.text
            net_id = net_id.text

            # Extract the LGV name
            lgv_name = extract_lgv_name(name)
            if not lgv_name:
                invalid_routes.append(f"Invalid name format: {name}")
                continue

            # Check for duplicate LGV names
            if lgv_name in seen_lgv_names:
                messagebox.showerror("Duplicate Entry", f"Duplicate LGV name found: {lgv_name}. File cannot be loaded.")
                return None  # Abort loading the file

            # Mark the LGV name as seen
            seen_lgv_names.add(lgv_name)

            type_tc = "TC3" if route.find('Flags') is not None else "TC2"

            # Append the tuple to the list
            routes_data.append((lgv_name, net_id, type_tc))

        # Warn the user about invalid routes
        if invalid_routes:
            messagebox.showwarning(
                "Invalid Routes",
                f"The following routes were skipped:\n" + "\n".join(invalid_routes)
            )

        # Populate the Treeview with the data
        for item in routes_data:
            treeview.insert("", "end", values=item)
        # messagebox.showinfo("Success", "Data loaded successfully from the XML file.")

    save_table_data_to_xml(treeview)

    # Enable menu for Read/Write if table is updated
    update_tabs()

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

    save_table_data_to_xml(treeview)

    # Enable menu for Read/Write if table is updated
    update_tabs()

def extract_numeric_part(name):
    match = re.search(r'\d+', name) #Extract numeric part
    return int(match.group()) if match else float('inf') # Convert to int for correct sorting


# Save data to XML
def save_table_data_to_xml(tree, filename=LGV_DATA):

    # Check if there is any data in the Treeview
    if not tree.get_children():
        print("Treeview is empty. No data to save.")
        return  # Exit the function if the Treeview is empty

    # Create the current data structure from the Treeview
    current_data = []
    for row in tree.get_children():
        lgv_data = tree.item(row)["values"]
        current_data.append({
            "Name": lgv_data[0],
            "AMSNetId": lgv_data[1],
            "Type": lgv_data[2]
        })

    # Sort the current data to ensure consistent ordering
    current_data.sort(key=lambda x: extract_numeric_part(x["Name"]))


    # If the file exists, compare it with the current data
    if os.path.exists(filename):
        tree_xml = ET.parse(filename)
        lgv_list = tree_xml.getroot()

        # Extract the existing data from the XML file
        existing_data = []
        for lgv in lgv_list.findall("LGV"):
            existing_data.append({
                "Name": lgv.find("Name").text,
                "AMSNetId": lgv.find("AMSNetId").text,
                "Type": lgv.find("Type").text
            })

        # Sort the existing data to ensure consistent ordering
        existing_data.sort(key=lambda x: extract_numeric_part(x["Name"]))

        # Compare existing data with current data
        if existing_data == current_data:
            print("No changes detected. Data not saved.")
            return  # Exit if there are no changes

    lgv_list = ET.Element("LGVData")
    for lgv in current_data:
        lgv_element = ET.SubElement(lgv_list, "LGV")
        ET.SubElement(lgv_element, "Name").text = lgv["Name"]
        ET.SubElement(lgv_element, "AMSNetId").text = lgv["AMSNetId"]
        ET.SubElement(lgv_element, "Type").text = lgv["Type"]

    # Convert to a pretty XML string
    xmlstr = minidom.parseString(ET.tostring(lgv_list, 'utf-8')).toprettyxml(indent="    ")

    # Write to a file
    with open(filename, "w", encoding='utf-8') as f:
        f.write(xmlstr)

    print(f"Data successfully saved to {filename}.")
    messagebox.showinfo("Attention", f"LGV data successfully saved to {filename}.")

# Load data from XML
def load_table_data_from_xml(tree, filename=LGV_DATA):
    if os.path.exists(filename):
        tree_xml = ET.parse(filename)
        lgv_list = tree_xml.getroot()

        # Check if there are any <LGV> elements
        if not lgv_list.findall("LGV"):
            print("The XML file has no LGV data, loading default table.")
            # messagebox.showwarning("Warning", "The XML file contains no LGV data. Loading default table.")
            messagebox.showinfo("Attention", "Default StaticRoutes.xml file loaded")
            populate_table_from_xml("C:\\TwinCAT\\3.1\\Target\\StaticRoutes.xml")
            return

        for lgv in lgv_list.findall("LGV"):
            lgv_name = lgv.find("Name").text
            ams_net_id = lgv.find("AMSNetId").text
            tc_type = lgv.find("Type").text
            tree.insert("", "end", values=(lgv_name, ams_net_id, tc_type))
    else:
        print("No saved XML data found, loading default table.")
        if os.path.exists("C:\\TwinCAT\\3.1\\Target\\StaticRoutes.xml"):
            # Populate table the first time with current StaticRoutes.xml file
            populate_table_from_xml("C:\\TwinCAT\\3.1\\Target\\StaticRoutes.xml")
            messagebox.showinfo("Attention", "Default StaticRoutes.xml file loaded")
        else:
            messagebox.showerror("Attention", "Default StaticRoutes.xml file not found")

# With DEL key
def delete_selected_record(event):
    selected_items = treeview.selection()
    for item in selected_items:
        if item:
            treeview.delete(item)


####################################################################################################################################################################
################################################################# ADS connection setup #############################################################################
####################################################################################################################################################################

monitor_timer = None

def monitor_connection_status():
    global current_ads_connection, monitor_timer

    if current_ads_connection is None:
        return

    try:
        if not check_plc_status(current_ads_connection):
            raise Exception("PLC not in valid state")

        update_status_in_queue("Connected", "green")

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

            # Stop the read thread
            stop_read_thread()  # Stop and join the thread

        if monitor_timer:
            monitor_timer.cancel()
            monitor_timer = None

        update_status_in_queue("Disconnected", "red")

# Background connection handler (runs in a separate thread)
def background_connect(plc_data):
    global current_ads_connection, connection_in_progress, connection_active

    try:
        # If already connected, don't try to reconnect
        if current_ads_connection is not None:
            return

        lgv_name, ams_net_id, tc_type = plc_data
        port = 851 if tc_type == 'TC3' else 801
        # ip_address = ".".join(str(ams_net_id).split(".")[:4])
        update_status_in_queue("Connecting...", "orange")

        # Attempt to open a new connection
        current_ads_connection = pyads.Connection(ams_net_id, port)
        current_ads_connection.open()

        connection_active = check_plc_status(current_ads_connection)

        # Check PLC status
        if connection_active:

            # Start monitoring the connection after connecting
            monitor_connection_status()

            connection_in_progress = False

            update_status_in_queue("Connected", "green")
            enable_control_buttons()

            # Automatically detect core variable
            check_for_core_variable("CoreGVL.ADS_Run")
            # Call update_buttons once to start the loop
            # update_buttons()
            update_buttons_from_plc_thread()



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
def connect_to_plc(event=None):
    """Connect to selected LGV"""
    global connection_in_progress

    with connection_lock:

        # If already connected, don't try to reconnect
        if current_ads_connection and not connection_in_progress:
            print("Target already connected")
            # messagebox.showinfo("Attention", "Target already connected")
            return

        if connection_in_progress:
            print("Connection in progress. Waiting for it to finish. Triggered on connect")
            # messagebox.showinfo("Attention", "Connection in progress. Waiting for it to finish. Triggered on connect")
            return


        # Get the selected PLC data
        selected_item = treeview.selection()
        if not selected_item:
            # messagebox.showinfo("Attention", "Select LGV")
            print("No LGV selected")
            return

        lgv_data = treeview.item(selected_item)["values"]

        connection_in_progress = True

    # Start the connection in a new thread
    connection_thread = threading.Thread(target=background_connect, args=(lgv_data,))
    connection_thread.daemon = True
    connection_thread.start()


previous_selection = None # track previous connection

connection_in_progress = False
# Close the current connection when selection changes
def on_treeview_select(event):
    global current_ads_connection, previous_selection, connection_in_progress, connection_active
    # Get the currently selected LGV

    selected_item = treeview.selection()
    if not selected_item:
        print("No item selected.")
        return

    # If the same item is selected, do nothing
    if ((previous_selection == selected_item)
            and current_ads_connection and connection_active
            and not connection_in_progress):
        print("Target already connected")
        # messagebox.showinfo("Attention", "Target already connected")
        return


    if connection_in_progress:
        print("Connection in progress. Waiting for it to finish. Triggered on select")
        # messagebox.showinfo("Attention", "Connection in progress. Waiting for it to finish. Triggered on select")
        treeview.selection_remove(treeview.selection())
        return

    old_selection = previous_selection
    previous_selection = selected_item  # Update the previously selected item

    # Close any existing connection when the selection changes
    if  current_ads_connection and connection_active:
        if read_variable('disable_horn'):
            old_lgv_name = treeview.item(old_selection)["values"][0]
            messagebox.showwarning("Attention", f"Horn in {old_lgv_name} is disabled!")

        print("Stopping read thread and closing current connection.")
        stop_read_thread()  # Ensure the read thread is stopped

        disable_control_buttons()
        close_current_connection()

    with connection_lock:
        connection_in_progress = False

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
    global variable_write, read_thread

    # Stop the read thread before resetting variables
    stop_read_thread()

    if os.path.exists("variables_config.json"):
        os.remove("variables_config.json")

    variable_write = copy.deepcopy(default_variable_write)
    print(F"Variable write after reset: {variable_write}")
    # print(f"Variables reset to defaults: {variable_write['disable_horn']['TC3']['core']}")

    update_menu()

    stop_thread_event.clear()
    start_read_thread()

    messagebox.showinfo("Reset", "Variables have been reset to defaults.")


    # else:
        # messagebox.showinfo("Reset", "No saved configuration found.")

# Function to update the menu item based on whether the JSON file exists
def update_menu():
    if os.path.exists("variables_config.json"):
        options_menu.entryconfig("Reset to Defaults ", state="normal")  # Enable if file exists
    else:
        options_menu.entryconfig("Reset to Defaults ", state="disabled")  # Disable if file doesn't exist

def update_tabs():
    if os.path.exists(LGV_DATA):
        notebook.tab(read_write_tab, state="normal")  # Enable if file exists
    else:
        notebook.tab(read_write_tab, state="disabled")  # Disable if file doesn't exist


# Load variables from JSON or fall back to defaults
def load_variables():
    """Load variables from JSON or return defaults if the file is missing."""
    if not os.path.exists("variables_config.json"):
        # If file doesn't exist, return the defaults
        vars = copy.deepcopy(default_variable_write)
        print(f"Default vars: {vars}")
        return vars

    # Load from JSON if the file exists
    with open("variables_config.json", "r") as json_file:
        user_variables = json.load(json_file)

    # Merge user-modified values into the defaults
    merge_vars = merge_dicts(copy.deepcopy(default_variable_write), user_variables)
    print(f"Merged vars: {merge_vars}")
    return merge_vars


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
    print(f"Merged vars input: {merged_vars}")

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
    print(f"Variable write: {variable_write}")
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

def on_test_button_click(button):
    """Function to simulate toggle behavior for testing the shortcut."""
    print(f"Test {button} shortcut triggered")

def on_dis_horn_button_click(button):
    """Enable/Disable horn"""
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
        print(f"Disable Horn pressed unsuccessful, value: {dis_horn_state}")

def trigger_dis_horn(event=None):
    """Enable/Disable horn"""
    on_dis_horn_button_click(dis_horn_button)


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


def bind_button_actions(button, action, shortcuts=None, press_value=True, release_value=False):
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


    # # Bind keyboard shortcuts (Control + Key press and release)
    # if shortcuts:
    #     for press_shortcut, release_shortcut in shortcuts:
    #         button.winfo_toplevel().bind(press_shortcut, on_button_press)
    #         button.winfo_toplevel().bind(release_shortcut, on_button_release)


def bind_connect_button_action(button, connect_function, shortcuts=None):
    """Bind connect behavior to both button click and keyboard shortcuts."""

    def on_connect(event=None):
        """Trigger the connect function."""
        connect_function()

    # Bind the button click directly to the connect function
    button.bind("<ButtonPress>", on_connect)

    # Bind keyboard shortcuts if provided
    if shortcuts:
        for shortcut in shortcuts:
            button.winfo_toplevel().bind(shortcut, lambda event: on_connect())


def bind_toggle_button_action(button, function=None, shortcuts=None):
    """Bind toggle behavior to both button click and keyboard shortcuts."""

    def on_toggle(event=None):
        print("Shortcut triggered in on_toggle")  # Debugging statement
        """Trigger the toggle function (mouse or shortcut)."""
        if function:
            print("Function is not None, calling function(button)")  # Debugging statement
            function(button)  # Call the function with the button reference
        else:
            print("Function is None")  # Debugging statement

    # Bind the button click to toggle
    button.bind("<ButtonPress>", on_toggle)

    # Bind keyboard shortcuts if provided
    if shortcuts:
        for shortcut in shortcuts:
            button.winfo_toplevel().bind_all(shortcut, lambda event: on_toggle())

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


def bind_treeview_focus_action(treeview, focus_shortcuts=None):
    """Bind focus behavior to Treeview for keyboard navigation."""

    # Bind keyboard shortcuts if provided
    if focus_shortcuts:
        for shortcut in focus_shortcuts:
            treeview.winfo_toplevel().bind(shortcut, focus_and_select_first)

def focus_and_select_first(event=None):
    """Select the first item from table"""
    treeview.focus_set()  # Set focus to the Treeview

    # Get the Treeview's scroll position
    yview = treeview.yview()
    if not yview:
        print("Treeview is empty or has no scroll position")
        return

    # Calculate the first visible item based on yview
    all_items = treeview.get_children()
    visible_item_index = int(yview[0] * len(all_items))  # Calculate the starting index

    if all_items:
        first_visible_item = all_items[visible_item_index]
        treeview.selection_set(first_visible_item)  # Select the first item
        treeview.focus(first_visible_item)  # Set the focus on the first item
        print("Treeview focused, first visible item selected")
    else:
        print("Treeview is empty, nothing to select")

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
        'TC2': [".OUT_Lamp_Top_Auto", ".OUT_Lamp_LgvRun"],
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

def check_for_core_variable(core_variable):
    global is_core
    try:
        # Attempt to read the core variable
        core_value = current_ads_connection.read_by_name(core_variable, pyads.PLCTYPE_BOOL)

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
    if not lgv_data:
        return

    if current_ads_connection is None:
        print("ADS connection is closed. Skipping variable read")
        return None

    tc_type = lgv_data[2]
    is_core_value = is_core

    # Get the variable(s) from the dictionary
    var_candidates = variable_read[action].get(tc_type) if tc_type == "TC2" else variable_read[action].get((tc_type, is_core_value))

    # Ensure var_candidates is always a list (if it's a string, wrap it in a list)
    if not isinstance(var_candidates, list):
        var_candidates = [var_candidates] if var_candidates else []

    last_error = None # Store the last error message

    for var_name in var_candidates:
        try:
            return current_ads_connection.read_by_name(var_name, pyads.PLCTYPE_BOOL)  # Stop if successful
        except Exception as e:
            last_error = f"Error reading variable {var_name}: {e}"  # Store but don't print yet

    # Only print the last error if all variables fail
    if last_error:
        print(last_error)

    return None


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

def update_button_color(action, button, read_value):
    if read_value is None:
        return
    # Change the button's foreground color based on the read_value
    if read_value:  # If the PLC variable is True
        button.configure(style='LGV.Connected.TButton')
    else:  # If the PLC variable is False
        button.configure(style='LGV.Disconnected.TButton')

read_lock = threading.Lock()
stop_thread_event = threading.Event()

def update_buttons_from_plc_thread():
    global current_ads_connection

    actions = ['run', 'disable_horn']

    # Mapping actions to buttons
    button_mapping = {
        'run': run_button,
        'disable_horn': dis_horn_button
    }

    # with read_lock:
    while not stop_thread_event.is_set():
        if current_ads_connection is None:
            return

        # print(f"Current state of variable write: {variable_write['disable_horn']['TC3']['core']}")
        for action in actions:
            read_value = read_variable(action)  # Read value from PLC
            button = button_mapping[action]
            root.after(0, update_button_color, action, button, read_value)

        stop_thread_event.wait(0.1)

    print("Read thread stopped...")

    # t = threading.Timer(0.1, update_buttons_from_plc_thread)
    # t.daemon = True
    # t.start()
read_thread = None

def start_read_thread():
    global read_thread
    stop_thread_event.clear()

    read_thread = threading.Thread(target=update_buttons_from_plc_thread)
    read_thread.daemon = True
    read_thread.start()


def stop_read_thread():
    global read_thread

    if read_thread is not None and read_thread.is_alive():
        print("Stopping read thread.")
        stop_thread_event.set()
        read_thread.join()  # Wait for the thread to finish
        read_thread = None  # Reset the thread reference
    else:
        print("No active read thread to stop.")

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
main_headings = {
    'Name': 'Name',
    'NetId': 'AMS Net Id',
    'Type': 'Type'
}

def setup_sortable_treeview(treeview, headings, anchor='w', on_sorted=None):
    def natural_keys(text):
        return [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', text)]

    def sort_column(col, reverse):
        # Retrieve all data from the treeview
        rows = [(treeview.set(k, col), k) for k in treeview.get_children('')]
        # Sort the data
        rows.sort(reverse=reverse, key=lambda t: natural_keys(t[0]))

        # Rearrange items in sorted positions
        for index, (_, k) in enumerate(rows):
            treeview.move(k, '', index)

        treeview.yview_moveto(0)

        if on_sorted:
            on_sorted(treeview)

        # Change the heading to show the sort direction
        for column in treeview['columns']:
            arrow = ' ↓' if reverse and column == col else ' ↑' if not reverse and column == col else ''
            treeview.heading(
                column,
                text=headings.get(column, column) + arrow,
                command=lambda _col=column: sort_column(_col, not reverse)
            )

    for col in treeview['columns']:
        treeview.heading(
            col,
            text=headings.get(col, col),
            command=lambda _col=col: sort_column(_col, False),
            anchor=anchor
        )


####################################################################################################################################################################
################################################################ Window To Set Variables ###########################################################################
####################################################################################################################################################################

variable_window = None

def open_variable_window_cond():
    global variable_window

    if variable_window is not None and variable_window.winfo_exists():
        variable_window.lift()
        variable_window.focus_force()
    else:
        open_variable_window()

def open_variable_window():
    global variable_window

    variable_window = tk.Toplevel(root)
    variable_window.title("Set Variables")

    window_width = 420
    window_lenght = 310
    variable_window.geometry(f"{window_width}x{window_lenght}")
    variable_window.minsize(window_width, window_lenght)

    # variable_window.resizable(False,False)

    def clear_entries():
        for entry in entries.values():
            entry.delete(0, tk.END)

    def radio_button_changed(*args):
        print(f"Radio button selected: {plc_type.get()}")
        clear_entries()

    def checkbox_changed(*args):
        print(f"Checkbox selected: {is_core.get()}")
        clear_entries()

    # Radio buttons for TC2 and TC3
    plc_type = tk.StringVar(value="TC2") # Default is TC2

    plc_type.trace_add("write", radio_button_changed)

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
    is_core = tk.BooleanVar(value=False)

    is_core.trace_add("write", checkbox_changed)
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
################################################################ Read/Write Management ###########################################################################
####################################################################################################################################################################
# read_write_window = None

# def open_read_write_window_cond():
#     global read_write_window

#     if read_write_window is not None and read_write_window.winfo_exists():
#         read_write_window.lift()
#         read_write_window.focus_force()
#     else:
#         open_read_write_window()


# def open_read_write_window():
#     global read_write_window

#     read_write_window = tk.Toplevel(root)
#     read_write_window.title("Read/Write ")

#     window_width = 475
#     window_lenght = 375
#     read_write_window.geometry(f"{window_width}x{window_lenght}")
#     read_write_window.minsize(window_width, window_lenght)

#     # Apply the icon after the window is initialized
#     read_write_window.after(100, set_icon, read_write_window)

RW_VARIABLES_FILE = "rw_variables.json"

# Predefined and custom variables
default_rw_variables = [
    'PressureGVLs.weightPar.touchingWeight',
    'CoreGVL.AutoReboot.startRequest',
    'CoreGVL.AutoReboot.autorebootDone',
    'Shutdown.DEBUG_forceShutdown',
    'LibraryInterfaces.FileManagement.loadRequest[3]']


def load_custom_variables():
    if os.path.exists(RW_VARIABLES_FILE):
        try:
            with open(RW_VARIABLES_FILE, "r") as file:
                data = json.load(file)
                if isinstance(data, list):  # Ensure the data is a list
                    return data
                else:
                    print("Invalid data format in JSON, resetting to empty list.")
                    return []
        except json.JSONDecodeError:
            print("JSON file is empty or invalid, resetting to empty list.")
            return []  # Return empty list if the file is invalid
    else:
        # Default variables if JSON does not exist
        return []

# Save variables to JSON
def save_variables(variables):
    with open(RW_VARIABLES_FILE, "w") as file:
        json.dump(variables, file, indent=4)
        file.write('\n')

def update_variable_menu(event=None):
    custom_rw_variables = load_custom_variables()

    combined_rw_variables = sorted (
        default_rw_variables + custom_rw_variables, key=str.lower
    )
    variable_menu["values"] = combined_rw_variables

def filter_combobox(event):
    if event.state & (0x0001 | 0x0004):  # Shift or Ctrl is pressed
        return  # Skip filtering
    
    typed_text = variable_menu.get()
    custom_rw_variables = load_custom_variables()
    combined_rw_variables = sorted (default_rw_variables + custom_rw_variables, key=str.lower)


    if typed_text == '':
        filtered_variables = combined_rw_variables
    else:
        filtered_variables = [var for var in combined_rw_variables if typed_text.lower() in var.lower()]

    variable_menu['values'] = filtered_variables

    if filtered_variables and not variable_menu['state'] == 'readonly':
        variable_menu.event_generate('<Down>')

# Functions
def add_variable():
    custom_rw_variables = load_custom_variables()
    new_variable = variable_menu.get().strip()

    if new_variable:
        # Normalize variable names to avoid issues with spaces around commas
        normalized_new_variable = ','.join(part.strip() for part in new_variable.split(','))

        # Normalize existing variables for comparison
        normalized_existing_variables = [
            ','.join(part.strip() for part in var.split(','))
            for var in default_rw_variables + custom_rw_variables
        ]

        if normalized_new_variable.lower() in (var.lower() for var in normalized_existing_variables):
            # messagebox.showwarning("Duplicate Entry", "This variable already exists.")
            print("Variable already exists")
            log_message("Variable already exists")
        else:
            custom_rw_variables.append(normalized_new_variable)
            save_variables(custom_rw_variables)
            update_variable_menu()
            print(f"Variable {new_variable} successfully added!")
            log_message(f"Variable {new_variable} successfully added!")
    else:
        print("Please enter a valid variable name.")
        log_message("Please enter a valid variable name.")


# result_var = tk.StringVar()


def parse_lgv_range(range_str):
    """Parse LGV range input into a list of LGV numbers."""
    lgv_numbers = set()
    parts = range_str.split(",")
    for part in parts:
        if "-" in part:
            start, end = map(int, part.split("-"))
            lgv_numbers.update(range(start, end + 1))
        else:
            lgv_numbers.add(int(part))
    return lgv_numbers

def validate_and_link_lgv():
    try:
        if lgv_range_entry.get().strip() == '':
            # messagebox.showerror("Error", "LGV range is empty!")
            print("LGV range is empty!")
            log_message("LGV range is empty!")
            return

        lgv_numbers = parse_lgv_range(lgv_range_entry.get())

        semaphore_size = min(10, max(3, len(lgv_numbers) // 10 or 1))  # Ensure at least 1
        global semaphore
        semaphore = threading.Semaphore(semaphore_size)
        print(f"Detected {len(lgv_numbers)} LGVs — using semaphore size: {semaphore_size}")

        found_entries = []

        remaining_children = list(treeview.get_children())

        # Iterate through Treeview to find matching LGVs
        for lgv in lgv_numbers:
            for child in remaining_children:
                name = treeview.item(child)["values"][0]  # e.g., "LGV01"
                match = re.search(r"\d+", name)

                if match and int(match.group()) == lgv:
                    amsnet_id = treeview.item(child)["values"][1]
                    tc_type = treeview.item(child)["values"][2]
                    found_entries.append((lgv, amsnet_id, tc_type))

                    # Remove matched child from remaining children list
                    remaining_children.remove(child)
                    break

        if len(found_entries) == len(lgv_numbers) and found_entries != []:
            # Display AMS Net IDs and types for the found LGVs
            print("LGV data found!")
            return found_entries
        else:
            overflow = len(lgv_numbers) - len(found_entries)
            if overflow > 0:
                raise ValueError(f"Range not matching LGV list. \nContains {overflow} extra elements than in list")
            else:
                raise ValueError(f"Some LGVs were not found, check range")
    except ValueError as e:
        # messagebox.showerror("Invalid Input", f"Error: {e}")
        print(f"Invalid input. Error: {e}")
        # messagebox.showerror("Error", f"Invalid input. Error: {e}")
        log_message(f"Invalid input. Error: {e}")
        # lgv_range_entry.delete(0, tk.END)
        return None


# Mapping of symbol type strings to pyads data types
if pyads_available:
    SYMBOL_TYPE_MAP = {
        'BOOL'      : pyads.PLCTYPE_BOOL,
        'INT'       : pyads.PLCTYPE_INT,
        'DINT'      : pyads.PLCTYPE_DINT,
        'REAL'      : pyads.PLCTYPE_REAL,
        'LREAL'     : pyads.PLCTYPE_LREAL,
        'STRING'    : pyads.PLCTYPE_STRING,
        'BYTE'      : pyads.PLCTYPE_BYTE,
        'WORD'      : pyads.PLCTYPE_WORD,
        'DWORD'     : pyads.PLCTYPE_DWORD,
        # 'LWORD'     : pyads.PLCTYPE_LWORD,
        'SINT'      : pyads.PLCTYPE_SINT,
        'USINT'     : pyads.PLCTYPE_USINT,
        'UINT'      : pyads.PLCTYPE_UINT,
        'UDINT'     : pyads.PLCTYPE_UDINT,
        'LINT'      : pyads.PLCTYPE_LINT,
        'ULINT'     : pyads.PLCTYPE_ULINT,
        'TIME'      : pyads.PLCTYPE_TIME,
        # 'LTIME'     : pyads.PLCTYPE_LTIME,
        'DATE'      : pyads.PLCTYPE_DATE,
        'TOD'       : pyads.PLCTYPE_TOD,  # Time of Day
        'DT'        : pyads.PLCTYPE_DT,    # Date and Time
        'WSTRING'   : pyads.PLCTYPE_WSTRING,
    }
else:
    # Use strings or None so the app loads without crashing
    SYMBOL_TYPE_MAP = {
        'BOOL'      : 'BOOL',
        'INT'       : 'INT',
        'DINT'      : 'DINT',
        'REAL'      : 'REAL',
        'LREAL'     : 'LREAL',
        'STRING'    : 'STRING',
        'BYTE'      : 'BYTE',
        'WORD'      : 'WORD',
        'DWORD'     : 'DWORD',
        'SINT'      : 'SINT',
        'USINT'     : 'USINT',
        'UINT'      : 'UINT',
        'UDINT'     : 'UDINT',
        'LINT'      : 'LINT',
        'ULINT'     : 'ULINT',
        'TIME'      : 'TIME',
        'DATE'      : 'DATE',
        'TOD'       : 'TOD',
        'DT'        : 'DT',
        'WSTRING'   : 'WSTRING',
    }

def get_pyads_type(symbol_type_str):
    """
    Map the symbol type string to a pyads type, handling arrays and other variations.
    """
    # Normalize the type string: Remove array and dimensions, strip whitespace
    array_match = re.search(r'ARRAY\s*\[.*?\]\s*OF\s*(\w+)', symbol_type_str.strip(), re.IGNORECASE)

    if array_match:
        # Extract the base type from the array declaration
        base_type = array_match.group(1).strip()
        if base_type in SYMBOL_TYPE_MAP:
            return SYMBOL_TYPE_MAP[base_type]
        else:
            print(f"Unknown array type detected: {symbol_type_str}. Defaulting to BYTE.")
            return pyads.PLCTYPE_BYTE  # Default for unknown array types

    # Remove any other dimensions or custom suffixes (e.g., STRING(80))
    normalized_type = re.sub(r'\(.*?\)', '', symbol_type_str.strip())

    # Map to a known type
    standard_type = SYMBOL_TYPE_MAP.get(normalized_type)
    if standard_type:
        return standard_type

    # Handle unknown or custom types
    print(f"Unknown type detected: {symbol_type_str}. Defaulting to BYTE.")
    return pyads.PLCTYPE_BYTE  # Default for unknown types


def check_type(value):
    """Determine the appropriate PLC data type based on the value."""
    if isinstance(value, bool):
        return pyads.PLCTYPE_BOOL
    elif isinstance(value, int):
        # Use INT or DINT depending on the size of the integer
        return pyads.PLCTYPE_INT if -32768 <= value <= 32767 else pyads.PLCTYPE_DINT
    elif isinstance(value, float):
        # Use REAL or LREAL based on precision
        return pyads.PLCTYPE_REAL if abs(value) < 3.4e38 else pyads.PLCTYPE_LREAL
    elif isinstance(value, str):
        # Use STRING type for string inputs
        return pyads.PLCTYPE_STRING
    else:
        raise ValueError(f"Unsupported type: {type(value)}")

# Global dictionary to store handles with context
handles = {}
next_handle_id = 0  # Unique integer handle ID generator

def get_new_handle_id():
    """Generate a new unique handle ID."""
    global next_handle_id
    handle_id = next_handle_id
    next_handle_id += 1
    return handle_id

def on_notification(adr, notification, user_handle):
    """Callback function to detect when the variable changes."""
    value = notification.contents.value
    print(f"Notification: Variable changed to {value}")

    # Access the stop event and expected value from the handles dictionary
    if handles[user_handle]["expected_value"] == value:
        handles[user_handle]["stop_event"].set()  # Signal to stop notification


semaphore = threading.Semaphore(MAX_WORKERS)


def safe_write_variable_for_lgv(*args):
    with semaphore:
        write_variable_for_lgv(*args)

def safe_read_variable_for_lgv(*args):
    with semaphore:
        read_variable_for_lgv(*args)

def safe_read_all_variables_for_lgv(*args):
    with semaphore:
        read_all_variables_for_lgv(*args)


read_write_in_progress = False



def write_variable_for_lgv(lgv, ams_net_id, tc_type, variable_name, display_name, value, result_queue):
    """Write a variable and confirm it via ADS notification."""

    ip = '.'.join(ams_net_id.split('.')[:4])
    if not is_host_reachable(ip):
        print(f"[WRITE] LGV {lgv} unreachable at {ip}, skipping write")
        result_queue.put((lgv, display_name, "Timeout"))  # or "Unreachable"
        return
    
    # stop_event = threading.Event()  # Event to track when the notification should stop
    handle_id = get_new_handle_id()
    print(f"Generated handle: {handle_id}, Type: {type(handle_id)}")

    # Store the context in the global handles dictionary
    # handles[handle_id] = {"expected_value": value, "stop_event": stop_event}

    port = 851 if tc_type == "TC3" else 801

    try:
        # Create a new connection for this LGV
        with pyads.Connection(ams_net_id, port) as ads_connection:
            print(f"Establishing connection for LGV {lgv} with AMS Net ID: {ams_net_id}")

            # type_var = check_type(value)

            # Get symbol info and determine the appropriate pyads type
            symbol_info = ads_connection.get_symbol(variable_name)
            symbol_type_str = symbol_info.symbol_type
            expected_type = get_pyads_type(symbol_type_str)

            print(f"Handle ID: {handle_id}, Type: {type(handle_id)}")  # Verify the type

            # Add a notification with a user handle containing the expected value and stop event

            # attr = pyads.NotificationAttrib(sizeof(expected_type))  # Adjust length as needed
            # notification_handle = ads_connection.add_device_notification(
            #     variable_name, attr, on_notification, handle_id
            # )

            # Write the value to the PLC using the provided variable name
            ads_connection.write_by_name(variable_name, value, expected_type)
            # print(f"Attempting to write {value} to {variable_name} for LGV {lgv}")

            # # Wait for the notification to confirm the change or timeout after 5 seconds
            # if not stop_event.wait(timeout=5):
            #     print(f"Write confirmation timed out for {variable_name} on LGV {lgv}")
            #     log_message(f"Error: {variable_name} not confirmed for LGV{lgv:02d}")
            # else:
            #     print(f"Successfully wrote {value} to {variable_name} for LGV {lgv}")
            print(f"Variable value in LGV{lgv:02d} is now {value}")
            # Add result to queue
            result_queue.put((lgv, display_name, value))

            # Remove the notification after use
            # ads_connection.del_device_notification(notification_handle, handle_id)
    except Exception as e:
        # Add error result to queue
        result_queue.put((lgv, display_name, e))
    # except pyads.ADSError as ads_err:
    #     # Handle ADS-specific errors with more detail
    #     error_message = f"Error writing to LGV{lgv:02d}: {ads_err}"
    #     print(error_message)
    #     log_message(error_message)

    # except ValueError as val_err:
    #     # Handle type-related errors
    #     error_message = f"Value Error for LGV{lgv:02d}: {val_err}"
    #     print(error_message)
    #     log_message(error_message)

    # except Exception as e:
    #     # Handle any other general exceptions
    #     error_message = f"Unexpected error for LGV{lgv:02d}: {str(e)}"
    #     print(error_message)
    #     log_message(error_message)


def convert_to_number(user_input):
    """Convert input to int or float; return None if conversion fails."""
    try:
        return int(user_input)
    except ValueError:
        try:
            return float(user_input)
        except ValueError:
            return None  # Not a number, possibly a string


def rw_write_variable(event=None):
    """Write variable"""
    global read_write_in_progress

    variable_names = variable_menu.get().strip()  # Directly get the variable name

    if variable_names == '':
        # messagebox.showerror("Error", "Variable name missing!")
        print("Variable name missing!")
        log_message("Variable name missing!")
        return

    # Split the input by commas and strip each variable name
    variables = [var.strip() for var in variable_names.split(';') if var.strip()]

    if not variables:
        print("No valid variable names found!")
        log_message("No valid variable names found!")
        return

    # Preprocess variable names for unique representation
    processed_variables = process_variable_names(variables)

    # Get the validated LGV data
    lgv_data = validate_and_link_lgv()
    if lgv_data is None:
        # messagebox.showerror("Error", "LGV range is empty")
        return  # Exit if validation failed
    
    if read_write_in_progress :
        print("Read/Write operation already in progress!")
        return

    # Prepare result table
    prepare_status_table(lgv_data, list(processed_variables.values()))

    # Result queue and thread tracking
    result_queue = Queue()
    threads = []

    radio_value = var_type.get()
    entry_value = value_entry.get().strip()

    # Validate the entry value: Ignore if it's "True" or "False"
    if entry_value.lower() in ["true", "false", ""]:
        value = radio_value  # Use the radio button value if the entry is empty or boolean-like
    else:
        # Try to convert to a number, otherwise keep it as a string
        converted_value = convert_to_number(entry_value)
        value = converted_value if converted_value is not None else entry_value

    # Delete entry_value after reading it to avoid using it the next time
    clear_entry_field()

    # Start a thread for each LGV to perform the write operation
    for lgv, ams_net_id, tc_type in lgv_data:
        for variable_name, display_name in processed_variables.items():
            thread = threading.Thread(
                target=safe_write_variable_for_lgv,
                args=(lgv, ams_net_id, tc_type, variable_name, display_name, value, result_queue)
            )
            thread.daemon = True
            thread.start()
            threads.append(thread)

    # Start a background thread to monitor results
    threading.Thread(
        target=process_results_in_background,
        args=(threads, result_queue, lgv_data),
        daemon=True
    ).start()

    read_write_in_progress = True


def process_variable_names(variables):
    """
    Process variable names to determine how many parts to include for uniqueness.
    If the last parts are unique, keep only the last part.
    If duplicates exist, include the second-to-last part for disambiguation.
    """
    last_parts = {}
    processed_variables = {}

    # Collect occurrences of last parts
    for variable in variables:
        parts = variable.split('.')
        last_part = parts[-1]
        last_parts.setdefault(last_part, []).append(variable)

    # Determine the display names for variables
    for last_part, full_vars in last_parts.items():
        if len(full_vars) > 1:  # Duplicate last parts found
            # Include the second-to-last part for these variables
            for var in full_vars:
                parts = var.split('.')
                processed_variables[var] = '.'.join(parts[-2:])  # Take last two parts
        else:  # No duplicate, keep only the last part
            var = full_vars[0]
            parts = var.split('.')
            processed_variables[var] = parts[-1]  # Keep only the last part

    return processed_variables


def read_variable_for_lgv(lgv, ams_net_id, tc_type, variable_name, display_name, result_queue):
    """Handle reading for each LGV in its own thread."""
    try:
        port = 851 if tc_type == "TC3" else 801
        # Create a new connection for this LGV
        with pyads.Connection(ams_net_id, port) as ads_connection:
            print(f"Establishing connection for LGV {lgv} with AMS Net ID: {ams_net_id}")

            # Get symbol info to validate type and existence
            symbol_info = ads_connection.get_symbol(variable_name)
            symbol_type_str = symbol_info.symbol_type
            expected_type = get_pyads_type(symbol_type_str)

            # Read the value from the PLC
            value = ads_connection.read_by_name(variable_name, expected_type)
            print(f"Successfully read {value} from {variable_name} for LGV {lgv}")

            # Add result to queue
            result_queue.put((lgv, display_name, value))

            # # Log the read value
            # log_message(f"{variable_last_part} value in LGV{lgv:02d} is {value}")

    except Exception as e:
        # Add error result to queue
        result_queue.put((lgv, display_name, e))

def read_all_variables_for_lgv(lgv, ams_net_id, tc_type, processed_variables, result_queue):
    # Extract IP from ams net id
    ip = '.'.join(ams_net_id.split('.')[:4])

    # Check if reachable before attempting connection
    if not is_host_reachable(ip):
        print(f"[READ] LGV {lgv} unreachable at {ip}, skipping")
        for display_name in processed_variables.values():
            result_queue.put((lgv, display_name, "Timeout"))
        return
    
    try:
        port = 851 if tc_type == "TC3" else 801
        with pyads.Connection(ams_net_id, port) as ads_connection:
            print(f"Connected to LGV {lgv} ({ams_net_id})")

            ads_connection.set_timeout(700)

            for variable_name, display_name in processed_variables.items():
                try:
                    symbol_info = ads_connection.get_symbol(variable_name)
                    expected_type = get_pyads_type(symbol_info.symbol_type)
                    value = ads_connection.read_by_name(variable_name, expected_type)
                    print(f"Read {value} from {variable_name} for LGV {lgv}")
                    result_queue.put((lgv, display_name, value))
                except Exception as e:
                    result_queue.put((lgv, display_name, e))
    except Exception as e:
        for display_name in processed_variables.values():
            result_queue.put((lgv, display_name, e))

def rw_read_variable(event=None):
    """Read variable(s)"""
    global read_write_in_progress

    variable_names = variable_menu.get().strip()  # Get the variable name directly

    if variable_names == '':
        # messagebox.showerror("Error", "Variable name missing!")
        print("Variable name missing!")
        log_message("Variable name missing!")
        return

    # Split the input by commas and strip each variable name
    variables = [var.strip() for var in variable_names.split(';') if var.strip()]

    if not variables:
        print("No valid variable names found!")
        log_message("No valid variable names found!")
        return

    # Preprocess variable names for unique representation
    processed_variables = process_variable_names(variables)

    # Get the validated LGV data
    lgv_data = validate_and_link_lgv()
    if lgv_data is None:
        return  # Exit if validation failed
    
    if read_write_in_progress :
        print("Read/Write operation already in progress!")
        return

    # Prepare result table
    prepare_status_table(lgv_data, list(processed_variables.values()))

    # Result queue and thread tracking
    result_queue = Queue()
    threads = []

    # Start a thread for each LGV to perform the read operation
    for lgv, ams_net_id, tc_type in lgv_data:
        thread = threading.Thread(
            target=safe_read_all_variables_for_lgv,
            args=(lgv, ams_net_id, tc_type, processed_variables, result_queue)
        )
        thread.daemon = True
        thread.start()
        threads.append(thread)

    # Start a background thread to monitor results
    threading.Thread(
        target=process_results_in_background,
        args=(threads, result_queue, lgv_data),
        daemon=True
    ).start()

    read_write_in_progress = True

def process_results_in_background(threads, result_queue, lgv_data):
    """Monitor threads and update UI as results arrive."""

    # Collect results
    results = {}
    responded_lgvs = set()  # Track which LGVs responded

    # Handle LGVs that didn't respond
    all_lgvs = {lgv for lgv, _, _ in lgv_data}
    variables = status_table["columns"][1:]

    def check_and_update():
        # Process new items in the result queue
        while not result_queue.empty():
            lgv, variable, value = result_queue.get()

            responded_lgvs.add(lgv)
            if lgv not in results:
                results[lgv] = {}

            # Record results or errors
            results[lgv][variable] = value

            # Update the table dynamically
            update_status_table(lgv, variable, value)
        
        # If all threads are done, handle timeouts and stop scheduling
        if all(not t.is_alive() for t in threads):
            missing_lgvs = all_lgvs - responded_lgvs

            for lgv in missing_lgvs:
                for variable in variables:
                    update_status_table(lgv, variable, "Timeout")

            # Handle variables that weren't updated for responding LGVs
            for lgv in responded_lgvs:
                for variable in variables:
                    if variable not in results[lgv]:
                        update_status_table(lgv, variable, "Timeout")
            
            # Reset the flag after all threads are done
            global read_write_in_progress
            read_write_in_progress = False

        else:
            # Schedule next check
            root.after(200, check_and_update)

    # Start checking 
    root.after(200, check_and_update)


def prepare_status_table(lgv_data, variables):
    """Pre-populate the table with LGVs and empty variable columns."""
    status_table.delete(*status_table.get_children())  # Clear the table

    lgv_overlay.delete(*lgv_overlay.get_children())

    print("Preparing table with variables:", variables)
    print("Current children:", status_table.get_children())
    print("Current columns:", status_table["columns"])

    # Set up dynamic columns: LGV + variable columns
    status_table["columns"] = ["LGV"] + variables
    status_table.heading("#0", text="", anchor="w")  # Hide default empty column
    status_table.column("#0", width=0, stretch=tk.NO)

    # Configure columns
    for col in status_table["columns"]:
        status_table.heading(col, text=col, anchor="center")
        header_lenght = len(str(col))
        col_width = max(header_lenght * 10, 50)
        status_table.column(col, anchor="center", width=col_width, stretch=False)  # Set default width

    # Pre-populate rows with LGVs
    for lgv, ams_net_id, _ in sorted(lgv_data, key=lambda x: x[0]):
        row_id = f"LGV{lgv:02d}"
        row_values = [row_id] + ["" for _ in variables]
        status_table.insert("", "end", iid=row_id, values=row_values)

        lgv_overlay.insert("", "end", iid=row_id, values=row_values) # Populate lgv_overlay as well

    status_headings = {col: col for col in status_table["columns"]}

    setup_sortable_treeview(status_table, status_headings, 'center', on_sorted=update_lgv_overlay)


def update_status_table(lgv, variable, value):
    """Update the table for a specific LGV and variable."""
    row_id = f"LGV{lgv:02d}"
    try:
        item = status_table.item(row_id)
        values = list(item["values"])

        if variable in status_table["columns"]:
            col_index = status_table["columns"].index(variable)
            values[col_index] = value

            tag = "" if value in ["Timeout", "Error"] else ""
            status_table.item(row_id, values=values, tags=(tag,))
    except Exception as e:
        print(f"Failed to update status for {row_id}, variable {variable}: {e}")

    # Adjust column widths
    adjust_column_width()


def adjust_column_width():
    """Dynamically adjust the width of each column based on content."""
    if not status_table.get_children():
        return

    if not status_table["columns"]:
        return
    
    # status_table["displaycolumns"] = status_table["columns"]

    for col in status_table["columns"]:
        max_length = max(
            len(str(status_table.set(child, col)))  # Get cell value
            for child in status_table.get_children()
        )
        max_length = max(max_length, len(col))      # Ensure header is included
        col_width = max(max_length*10, 20)          # Set a minimum width of 20 px in case of single char
        status_table.column(col, width=col_width, stretch=False)   # Adjust width (10px per char)


# # Dictionary to store original column headings for sorting indicators
# dynamic_headings = {}

# def setup_rw_data(treeview):
#     """
#     Setup sorting for dynamically generated columns.
#     """
#     for col in treeview['columns']:
#         dynamic_headings[col] = col  # Store original column heading
#         treeview.heading(
#             col,
#             text=col,
#             command=lambda _col=col: treeview_sort_column(treeview, _col, False),
#             anchor="center"
#         )


# def update_lgv_overlay_order(treeview):
#     """
#     Updates the LGV overlay to match the sorted order of the status_table.
#     """
#     lgv_overlay.delete(*lgv_overlay.get_children())  # Clear current overlay

#     # Insert LGV numbers in the sorted order
#     for item in treeview.get_children(''):
#         lgv_number = treeview.item(item, "values")[0]  # Extract LGV number from sorted table
#         lgv_overlay.insert("", "end", values=(lgv_number,))


def clear_entry_field():
    """Disable value entry if True/False radio is selected."""
    value_entry.delete(0, tk.END)  # Clear the entry field

def log_message(message):
    """Insert log messages into a messagebox."""
    # read_write_window.after(0, lambda: status_widget.insert(tk.END, message + "\n"))
    # read_write_window.after(0, status_widget.see, tk.END)  # Scroll to the bottom
    messagebox.showerror("Error", message)

def clear_status():
    """Clear the content of the status widget."""
    # status_widget.delete(1.0, tk.END)  # Clear all content


#     # Make the window layout expand properly
#     read_write_window.grid_rowconfigure(4, weight=1)
#     read_write_window.grid_columnconfigure(0, weight=1)
#     read_write_window.grid_columnconfigure(1, weight=1)

#     exceptions = [value_frame, read_button, write_button]

#     # Handle window close event to reset the reference
#     read_write_window.protocol("WM_DELETE_WINDOW", on_read_write_window_close)

# def on_read_write_window_close():
#     global read_write_window
#     read_write_window.destroy()
#     read_write_window = None


    # entry to input LGV range

    # drop down menu to add and save variables

    # frame to add radio buttons for TRUE FALSE or Value (in a entry) when writing

    # Frame with two buttons (read / write)

    # Widget to show results when reading (enable only with reading)

    # Read and write will be multi thread

###################################################################### Helper methods #########################################################################

def is_host_reachable(host, timeout=1):
    """Ping the host to check if it is reachable."""
    # Define the ping command based on the OS
    if platform.system().lower() == "windows":
        ping_cmd = ["ping", "-n", "1", "-w", str(timeout * 1000), host]
        creation_flags = subprocess.CREATE_NO_WINDOW
    else:
        ping_cmd = ["ping", "-c", "1", "-W", str(timeout), host]
        creation_flags = 0

    try:
        subprocess.run(
            ping_cmd, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL, 
            check=True, 
            timeout=timeout + 1,
            creationflags=creation_flags
        )
        return True
    except subprocess.TimeoutExpired:
        # print(f"Ping to {host} timed out.")
        return False
    except subprocess.CalledProcessError:
        # print(f"Ping to {host} failed.")
        return False
    

####################################################################################################################################################################
################################################################### Shortcuts Window ###############################################################################
####################################################################################################################################################################

global_shortcuts = [
    ("Ctrl+Shift+Tab", "Change between tabs"),
    ("F1", "Show shortcuts help")
]


def get_action_name(func):
    if hasattr(func, "__doc__") and func.__doc__:
        return func.__doc__.strip()
    elif hasattr(func, "__name__"):
        return func.__name__.replace('_', ' ').capitalize()
    return "Action"


shortcuts_window = None
shortcuts_frame = None
shortcuts_title_label = None

shortcuts_window_position = None

def toggle_shortcuts_window(event=None):
    global shortcuts_window, shortcuts_window_position

    if shortcuts_window is not None and shortcuts_window.winfo_exists():
        geometry = shortcuts_window.geometry()  # e.g. "420x400+123+456"
        # Extract just the +x+y part
        pos = geometry.split('+')
        if len(pos) >= 3:
            shortcuts_window_position = f"+{pos[1]}+{pos[2]}"

        shortcuts_window.destroy()
        shortcuts_window = None
    else:
        tab_text = notebook.tab(notebook.select(), "text")
        open_shortcuts_window(tab_text=tab_text)



def open_shortcuts_window(event=None, tab_text=None):
    global shortcuts_window, shortcuts_frame, shortcuts_title_label

    if tab_text is None:
        tab_text = notebook.tab(notebook.select(), "text")

    if shortcuts_window is not None and shortcuts_window.winfo_exists():
        refresh_shortcuts_window(tab_text)
        shortcuts_window.lift()
        shortcuts_window.focus_force()
        return

    shortcuts_window = tk.Toplevel(root)
    shortcuts_window.title(f"Shortcuts — {tab_text}")

    window_width = 420
    window_lenght = 400
    if shortcuts_window_position:
        shortcuts_window.geometry(f"{window_width}x{window_lenght}{shortcuts_window_position}")
    else:
        shortcuts_window.geometry(f"{window_width}x{window_lenght}")
    shortcuts_window.minsize(window_width, window_lenght)

    # Add a label for the title
    shortcuts_title_label = ttk.Label(shortcuts_window, text=f"Available Shortcuts — {tab_text}", font=("Segoe UI", 14))
    shortcuts_title_label.pack(pady=10)

    # Add a frame to contain the shortcuts in a neat layout
    shortcuts_frame = tk.Frame(shortcuts_window)
    shortcuts_frame.pack(fill="both", expand=True, padx=10, pady=5)

    refresh_shortcuts_window(tab_text)

    # Handle window close event to reset the reference
    shortcuts_window.protocol("WM_DELETE_WINDOW", on_shortcuts_window_close)


def refresh_shortcuts_window(tab_text):
    global shortcuts_frame, shortcuts_window, shortcuts_title_label

    shortcuts_window.title(f"Shortcuts — {tab_text}")
    shortcuts_title_label.config(text=f"Available Shortcuts — {tab_text}")

    actions = tab_shortcut_actions.get(tab_text, {})

    for widget in shortcuts_frame.winfo_children():
        widget.destroy()

    combined_shortcuts = []

    for key, config in actions.get("press_release", {}).items():
        combined_shortcuts.append((f"Ctrl+{key.upper()}", f"{config['action'].capitalize()} (hold)"))

    for key, func in actions.get("single_action", {}).items():
        combined_shortcuts.append((f"Ctrl+{key.upper()}", get_action_name(func)))

    if not combined_shortcuts:
        combined_shortcuts.append(("—", "No shortcuts available for this tab"))

    # Add global shortcuts
    if global_shortcuts:
        combined_shortcuts.append(("", ""))
        combined_shortcuts.append(("— Global Shortcuts —", ""))
        combined_shortcuts += global_shortcuts

    # Display in grid
    for i, (shortcut, description) in enumerate(combined_shortcuts):
        font_style = ("Segoe UI", 12, "bold") if shortcut.startswith("Ctrl") or shortcut.startswith("F") else ("Segoe UI", 11, "italic")
        tk.Label(shortcuts_frame, text=shortcut, font=font_style).grid(row=i, column=0, sticky="w", padx=10, pady=2)
        tk.Label(shortcuts_frame, text=description, font=("Segoe UI", 12)).grid(row=i, column=1, sticky="w", padx=10, pady=2)


def on_shortcuts_window_close():
    global shortcuts_window
    shortcuts_window.destroy()
    shortcuts_window = None

    
############################################################## Shortcut management #######################################################
current_tab_shortcuts = []

def create_tab_shortcut_actions():
    return {
        TAB_NAME[0]: {
            "press_release": {
                'r': {
                    'action': 'reset',
                    'button': reset_button,
                    'press_value': True,
                    'release_value': False
                },
                'g': {
                    'action': 'run',
                    'button': run_button,
                    'press_value': True,
                    'release_value': False
                },
                's': {
                    'action': 'stop',
                    'button': stop_button,
                    'press_value': False,
                    'release_value': True
                },
                'm': {
                    'action': 'man_auto',
                    'button': man_auto_button,
                    'press_value': True,
                    'release_value': False
                }
            },
            "single_action": {
                'h': trigger_dis_horn,
                'c': connect_to_plc,
                't': focus_and_select_first
            }
        },

        TAB_NAME[1]: {
            "press_release": {},
            "single_action": {
                't': select_true,
                'f': select_false,
                'x': focus_var_entry,
                'e': focus_other_entry,
                'l': focus_lgv_entry,
                'r': rw_read_variable,
                'w': rw_write_variable
            }
        }
    }


def bind_tab_shortcuts(tab_text):
    global current_tab_shortcuts
    for shortcut in current_tab_shortcuts:
        root.unbind(shortcut)
    current_tab_shortcuts.clear()

    if tab_text not in tab_shortcut_actions:
        return

    tab_actions = tab_shortcut_actions[tab_text]

    # --- Press + Release shortcuts ---
    for key, config in tab_actions.get("press_release", {}).items():
        for case in (key.lower(), key.upper()):
            press_shortcut = f"<Control-{case}>"
            release_shortcut = f"<KeyRelease-{case}>"

            def make_press_handler(c=config):
                return lambda e: on_button_action(c['action'], c['press_value'], c['button'])

            def make_release_handler(c=config):
                return lambda e: on_button_action(c['action'], c['release_value'], c['button'], is_release=True)

            root.bind(press_shortcut, make_press_handler())
            root.bind(release_shortcut, make_release_handler())

            current_tab_shortcuts.extend([press_shortcut, release_shortcut])

    # --- Single-action shortcuts (press only) ---
    for key, func in tab_actions.get("single_action", {}).items():
        for case in (key.lower(), key.upper()):
            shortcut = f"<Control-{case}>"
            root.bind(shortcut, func)
            current_tab_shortcuts.append(shortcut)


####################################################################  UI methods ###############################################################

# Keyboard shortcut functions
def select_true(event=None):
    var_type.set(True)
    clear_entry_field()

def select_false(event=None):
    var_type.set(False)
    clear_entry_field()

def focus_other_entry(event=None):
    value_entry.focus_set()

def focus_lgv_entry(event=None):
    lgv_range_entry.focus_set()

def focus_var_entry(event=None):
    variable_menu.focus_set()

# Function to check LGV column visibility
def toggle_lgv_overlay(*args):
    """Show or hide the LGV overlay depending on the visibility of the LGV column."""
    x = status_table.xview()[0]  # Get the normalized scroll position (0 to 1)
    if x > 0:  # If the scroll position is not at the beginning
        lgv_overlay.grid()  # Show overlay
        lgv_overlay.lift()
    else:
        lgv_overlay.grid_remove()  # Hide overlay

def update_lgv_overlay_deprecated(*args):
    # Handle vertical scrolling for visible rows (yscroll)
    lgv_overlay.delete(*lgv_overlay.get_children())  # Clear current rows in overlay

    # Get visible range
    visible_fraction = status_table.yview()  # Returns (start, end) as fractions
    total_rows = len(status_table.get_children())  # Total rows in the Treeview

    # Calculate visible row indices
    first_visible_row = int(visible_fraction[0] * total_rows)
    last_visible_row = min(int(visible_fraction[1] * total_rows)-1, total_rows-1)

    all_items = treeview.get_children()
    visible_items = all_items[first_visible_row:last_visible_row + 1]

    # Populate overlay with visible rows only
    for item in visible_items:
        lgv_name = treeview.item(item, "values")[0]
        lgv_overlay.insert("", "end", values=(lgv_name,))
        # print(f" First elem: {first_visible_row}, Last elem: {last_visible_row}, {len(status_table.get_children())}")


def update_lgv_overlay(*args):
    """
    Updates the LGV overlay to show only visible rows, in the current sorted order.
    """
    lgv_overlay.delete(*lgv_overlay.get_children())  # Clear overlay

    # Get current sorted and filtered items
    all_items = status_table.get_children()

    # Determine visible range
    visible_fraction = status_table.yview()
    total_items = len(all_items)
    first_visible_index = int(visible_fraction[0] * total_items)
    last_visible_index = min(int(visible_fraction[1] * total_items), total_items)  # no -1 here

    visible_items = all_items[first_visible_index:last_visible_index]

    # Add only visible sorted items
    for item_id in visible_items:
        lgv_name = status_table.item(item_id, "values")[0]
        lgv_overlay.insert("", "end", values=(lgv_name,))


def on_tab_changed(event):
    selected_tab = event.widget.select()
    tab_text = event.widget.tab(selected_tab, "text")

    bind_tab_shortcuts(tab_text)

    if shortcuts_window is not None and shortcuts_window.winfo_exists():
        refresh_shortcuts_window(tab_text)

    # if tab_text == TAB_NAME[1]:
    #     root.after(10, lambda: variable_menu.focus_set())
    #     print(f"Widget in {TAB_NAME[1]} is focused")
    # else:
    #     root.focus_set()


def select_next_tab(event=None):
    current = notebook.index(notebook.select())
    total = len(notebook.tabs())
    notebook.select((current + 1) % total)
    print("next tab")
    return "break"  # prevents default behavior

def select_previous_tab(event=None):
    current = notebook.index(notebook.select())
    total = len(notebook.tabs())
    prev_index = (current - 1) % total
    notebook.select(prev_index)
    print("previous tab")
    return "break"


############################# Set GUI icon ##########################
def set_icon(window):
    if os.path.exists(icon_path):
        window.iconbitmap(icon_path)
    else:
        print("Icon file not found.")

####################################################################################################################################################################
####################################################################### Create UI ##################################################################################
####################################################################################################################################################################


# Create the root window
root = tk.Tk()
root.title(f"Super ADS Client {__version__}")
# root.geometry("600x400")  # Adjust the window size

# Let the table_frame grow inside root
root.grid_rowconfigure(1, weight=1)
# root.grid_columnconfigure(1, weight=1)

# Check if running as a script or frozen executable
if getattr(sys, 'frozen', False):
    icon_path = os.path.join(sys._MEIPASS, __icon__)
else:
    icon_path = os.path.abspath(__icon__)
# root.iconbitmap(icon_path)

window_width = 480
window_lenght = 460
root.geometry(f"{window_width}x{window_lenght}")
root.minsize(window_width, window_lenght)

# Apply the icon after the window is initialized
root.after(100, set_icon, root)


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

style.configure("TNotebook.Tab",
                padding=[3, 5],
                font=("Segoe UI", 9))


notebook = ttk.Notebook(root)
notebook.grid(row=1, column=0, columnspan=2, sticky="nsew")

main_tab = ttk.Frame(notebook, style="TNotebook.Tab")
read_write_tab = ttk.Frame(notebook, style="TNotebook.Tab")

notebook.add(main_tab, text=TAB_NAME[0])
notebook.add(read_write_tab, text=TAB_NAME[1])


# Bind Ctrl+Tab and Ctrl+Shift+Tab
root.bind_all("<Control-Tab>", select_next_tab)
root.bind_all("<Control-Shift-Tab>", select_previous_tab)


# Create the menu bar
menu_bar = tk.Menu(root)

file_menu = tk.Menu(menu_bar, tearoff=0)
file_menu.add_command(label=" Load Config.db3 ", command=populate_table_from_db3)  # Add Load Config option
file_menu.add_command(label=" Load StaticRoutes.xml", command=populate_table_from_xml) # Add Load StaticRoutes option
file_menu.add_command(label=" Exit ", command=root.quit)  # Add Exit option
menu_bar.add_cascade(label="  File ", menu=file_menu)


options_menu = tk.Menu(menu_bar, tearoff=0)
options_menu.add_command(label="Set Variables    ", command=open_variable_window_cond)
options_menu.add_command(label="Reset to Defaults ", command=reset_to_defaults)
menu_bar.add_cascade(label=" Options ", menu=options_menu)

# more_menu = tk.Menu(menu_bar, tearoff=0)
# more_menu.add_command(label="Read/Write    ", command=open_read_write_window_cond)
# menu_bar.add_cascade(label=" More ", menu=more_menu)

about_menu = tk.Menu(menu_bar, tearoff=0)
about_menu.add_command(label="Shortcuts    ", command=open_shortcuts_window)
menu_bar.add_cascade(label=" About", menu=about_menu)

root.bind_all("<F1>", toggle_shortcuts_window)

root.config(menu=menu_bar)

# Update the menu based on whether the file exists
update_menu()

update_tabs()


frame_connect = ttk.Frame(main_tab, width=100)
# frame_connect.grid_propagate(False)
frame_connect.grid(row=0, column=0, padx=20, pady=5)

# Create a label as an indicator
core_status_label = ttk.Label(frame_connect, text="No Core Lib", foreground="#4682B4") # #3CB371, #6495ED, 4682B4
core_status_label.grid(row=0, column=0, padx=20, pady=0, sticky='e')


# Add a button to connect to the PLC
connect_button = ttk.Button(frame_connect, text="Connect", style='Connect.TButton')
connect_button.grid(row=0, column=1, padx=10, ipady=4, sticky='w')
connect_button.bind("<ButtonPress>", connect_to_plc)

# bind_connect_button_action(connect_button, connect_function=connect_to_plc,
#                             shortcuts=['<Control-c>', '<Control-C>'])



# Connection status label
status_label = ttk.Label(main_tab, text="Disconnected", foreground="red", font=("Segoe UI", 13))
status_label.grid(row=0, column=1, padx=5, pady=5)



# Create a frame for the table (Treeview)
table_frame = ttk.Frame(main_tab)
table_frame.grid(row=1, column=0, padx=10, pady=20, sticky='nsew')

# Let the table_frame expand its contents
table_frame.grid_rowconfigure(0, weight=1)
table_frame.grid_columnconfigure(0, weight=1)

treeview_style = ttk.Style()
treeview_style.configure("Treeview", rowheight=24)  # Increase row height for more space between items
treeview_style.configure("Treeview", font=("Segoe UI", 10))  # Adjust font size if necessary
treeview_style.configure("Treeview", padding=(5, 5))  # Add padding to rows (optional)

# Create the Treeview (table)
columns = ("Name", "NetId", "Type")
treeview = ttk.Treeview(table_frame, columns=columns, show="headings")

# Define the column widths
treeview.column("Name", width=70, anchor='w')
treeview.column("NetId", width=120, anchor='w')
treeview.column("Type", width=50, anchor='w')

setup_sortable_treeview(treeview, main_headings)

# Add the treeview to the table frame
treeview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

treeview.bind("<<TreeviewSelect>>", on_treeview_select)
treeview.bind('<Delete>', delete_selected_record)

# bind_treeview_focus_action(treeview, focus_shortcuts=['<Control-t>', '<Control-T>'])

# Create a vertical scrollbar for the table
scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=treeview.yview)
treeview.configure(yscroll=scrollbar.set)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)




# Create a frame for the buttons
button_frame = ttk.Frame(main_tab, width=170, height=350)
button_frame.pack_propagate(False)
button_frame.grid(row=1, column=1, padx=10, pady=10, sticky='new')


# Add some buttons to the right frame
reset_button = ttk.Button(button_frame,
                          text="Reset",
                          style='LGV.TButton')
                        #   command=lambda: bind_button_actions(reset_button, 'reset'))
                        #   command=lambda: on_button_action_wrapper('reset', True, False, reset_button))
reset_button.pack(pady=5, fill='x', expand=True, ipady=6)
bind_button_actions(reset_button, 'reset')

run_button = ttk.Button(button_frame,
                        text="Run",
                        style='LGV.TButton')
                        # command=lambda: on_button_action_wrapper('run', True, False, run_button))
run_button.pack(pady=5, fill='x', expand=True, ipady=6)
bind_button_actions(run_button, 'run')

stop_button = ttk.Button(button_frame,
                         text="Stop",
                         style='LGV.Pressed.TButton')
                        #  command=lambda: on_button_action_wrapper('stop', False, True, stop_button))
stop_button.pack(pady=5, fill='x', expand=True, ipady=6)
bind_button_actions(stop_button, 'stop', press_value=False, release_value=True)

man_auto_button = ttk.Button(button_frame,
                             text="Man/Auto",
                             style='LGV.TButton')
                            #  command=lambda: on_button_action_wrapper('man_auto', True, False, man_auto_button))
man_auto_button.pack(pady=5, fill='x', expand=True, ipady=6)
bind_button_actions(man_auto_button, 'man_auto')

dis_horn_button = ttk.Button(button_frame,
                             text="Disable Horn",
                             style='LGV.TButton',
                             command=trigger_dis_horn)
dis_horn_button.pack(pady=5, fill='x', expand=True, ipady=6)


disable_control_buttons()
# enable_control_buttons() #Uncomment for testing

load_table_data_from_xml(treeview)

variable_write = load_variables()

start_read_thread()

root.after(100, process_status_updates)

######################################################### RW Panel #################################################################

# Variables Frame
variable_frame = ttk.LabelFrame(read_write_tab, text="Variables")
variable_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")

# ttk.Label(variable_frame, text="Select or Add Variable:").grid(row=0, column=0, padx=5, pady=5)
variable_menu = ttk.Combobox(variable_frame)
variable_menu.grid(row=0, column=0, padx=5, pady=5, sticky='ew')
variable_menu.bind('<ButtonPress>', update_variable_menu)
# Bind the filter function to update on key release
variable_menu.bind('<Tab>', filter_combobox)

# variable_menu.configure(postcommand=lambda:filter_combobox(None))

add_var_btn = ttk.Button(variable_frame, text="Add Variable", command=add_variable)
add_var_btn.grid(row=0, column=1, padx=5, pady=5)

# Extend variable_frame sideways
variable_frame.grid_columnconfigure(0, weight=1)
# variable_frame.grid_rowconfigure(0, weight=1)

# Value Input Frame
value_frame = ttk.LabelFrame(read_write_tab, text="Set Value")
value_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")



bool_value_frame = ttk.Frame(value_frame)
bool_value_frame.grid(row=0, column=0, padx=5, pady=5)

var_type = tk.BooleanVar()
true_radio = ttk.Radiobutton(bool_value_frame, text="True", variable=var_type, value=True, command=clear_entry_field)
true_radio.grid(row=0, column=0, padx=5, pady=5)

false_radio = ttk.Radiobutton(bool_value_frame, text="False", variable=var_type, value=False, command=clear_entry_field)
false_radio.grid(row=0, column=1, padx=5, pady=5)

entry_value_frame = ttk.Frame(value_frame)
entry_value_frame.grid(row=0, column=1, padx=5, pady=5)
ttk.Label(entry_value_frame, text="Other:").grid(row=0, column=0, padx=5, pady=5)
value_entry = ttk.Entry(entry_value_frame)
value_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")


# LGV Range Frame
lgv_frame = ttk.Frame(read_write_tab)
lgv_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")

input_frame = ttk.Frame(lgv_frame)
input_frame.grid(row=0, column=0, padx=5, pady=5)
ttk.Label(input_frame, text="LGV:").grid(row=0, column=0, padx=5, pady=5)
lgv_range_entry = ttk.Entry(input_frame)
lgv_range_entry.grid(row=0, column=1, padx=5, pady=5)

# Buttons Frame
button_frame = ttk.Frame(lgv_frame)
button_frame.grid(row=0, column=2, columnspan=2, pady=10, padx=30, sticky='e')

read_button = ttk.Button(button_frame, text="Read", command=rw_read_variable)
read_button.grid(row=0, column=0, padx=10, ipadx=2, ipady=2)
write_button = ttk.Button(button_frame, text="Write", command=rw_write_variable)
write_button.grid(row=0, column=1, padx=10, ipadx=2, ipady=2)


# Status table frame
status_table_frame = ttk.Frame(read_write_tab)
status_table_frame.grid(row=4, column=0, columnspan=2, sticky="nsew")

status_table_frame.grid_columnconfigure(0, weight=1)
status_table_frame.grid_rowconfigure(0, weight=1)


# LGV overlay Treeview
lgv_overlay = ttk.Treeview(
    status_table_frame,
    show="headings",
    height=5
    # selectmode="none"  # Prevent selection
)
lgv_overlay.grid(row=0, column=0, padx=(15,0), pady=(5,0), sticky="nsw")  # Align to the left
lgv_overlay["columns"] = ["LGV"]
lgv_overlay.heading("LGV", text="LGV", anchor="center")
lgv_overlay.column("LGV", width=70, stretch=False, anchor="center")

lgv_overlay.grid_remove()  # Hide overlay initially

# Disable vertical scrolling on the LGV overlay
lgv_overlay.unbind("<MouseWheel>")  # Disable mouse scroll (Windows)
lgv_overlay.unbind("<Button-4>")    # Disable mouse scroll up (Linux)
lgv_overlay.unbind("<Button-5>")    # Disable mouse scroll down (Linux)

# Prevent programmatic vertical scrolling
lgv_overlay.yview = lambda *args: None


# Add the dynamic status table
status_table = ttk.Treeview(
    status_table_frame,
    show="headings",
    height=5
)

status_table.grid(row=0, column=0, padx=(15,0), pady=(5,0), sticky="nsew")

# Configure tags for the status table (e.g., red text for errors)
status_table.tag_configure("error", foreground="red")

# Extend status_table sideways
status_table.grid_columnconfigure(0, weight=1)
# status_table.grid_rowconfigure(0, weight=1)

# Configure scrollbars for the status table
scroll_y = ttk.Scrollbar(status_table_frame, orient="vertical", command=status_table.yview)
scroll_y.grid(row=0, column=1, sticky="ns")

scroll_x = ttk.Scrollbar(status_table_frame, orient="horizontal", command=status_table.xview)
scroll_x.grid(row=1, column=0, columnspan=2, sticky="ew")

# Attach the function to the horizontal scrollbar
status_table.configure(
    xscrollcommand=lambda *args: (scroll_x.set(*args), toggle_lgv_overlay(*args)),
    yscrollcommand=lambda *args: (scroll_y.set(*args), update_lgv_overlay(*args))
)


root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(1, weight=1)

# Make the table in the main tab expandable downwards
main_tab.grid_columnconfigure(0, weight=0)
main_tab.grid_rowconfigure(1, weight=1)

# Make the window layout expand properly
read_write_tab.grid_rowconfigure(4, weight=1)
read_write_tab.grid_columnconfigure(0, weight=1)


update_lgv_overlay()

notebook.bind("<<NotebookTabChanged>>", on_tab_changed)


tab_shortcut_actions = create_tab_shortcut_actions()

def on_closing():
    close_current_connection()  # Close connection before exiting

    # Save data to custom xml to avoid reloading .db3 or .xml everytime app is open
    save_table_data_to_xml(treeview)

    root.destroy()  # Close the application

# Bind the window close event to custom close function
root.protocol("WM_DELETE_WINDOW", on_closing)


root.mainloop()

# root.focus_set()


# 1. select LGV,
# changing lgv drops previous connection


# two inputs, table or manual entry. In manual add just ip, maybe not needed now that table is updated since the beginning

# reset, run, stop, manual/auto and disable horn only needed

# Avoid to enable connection when the user click connect more than once

# Add colors to the buttons, at least for the horn, and reset that variable whenever there's a new connection

# Connected/Disconnedted label doesn't change from conencted to disconnected when another selection is made, maybe set this to default when connection is closed

# Ponerle keyboard shortcut a los botones
# Ctrl + R, G, S, M, D



# Usar coma para separar varias variables y leerlas al mismo tiempo, para escribir solo una

# TO DO