import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import re
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
import pyads
import sys

__version__ = '1.1.2'
__icon__ = 'ads.ico'

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
        root = tree_xml.getroot()
        for plc in root.findall("LGV"):
            plc_name = plc.find("Name").text
            ams_net_id = plc.find("AMSNetId").text
            plc_type = plc.find("Type").text
            tree.insert("", "end", values=(plc_name, ams_net_id, plc_type))
    else:
        print("No saved XML data found, loading default table.")


####################################################################################################################################################################
############################################################## Treeview setup and sorting ##########################################################################
####################################################################################################################################################################

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

def set_icon():
    if os.path.exists(icon_path):
        root.iconbitmap(icon_path)
    else:
        print("Icon file not found.")

# Apply the icon after the window is initialized
root.after(100, set_icon)

style = ttk.Style()
style.configure("LGV.TButton", 
                focuscolor="white", 
                padding=4, 
                focusthickness=1, 
                font=("Segoe UI", 13))
                # font = ("Tahoma", 12))

# Create a frame for the table (Treeview)
table_frame = ttk.Frame(root)
table_frame.grid(row=1, rowspan=4, column=0, padx=15, pady=10)

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

# Create a vertical scrollbar for the table
scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=treeview.yview)
treeview.configure(yscroll=scrollbar.set)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

load_config_button = ttk.Button(root, text="Load Config.db3", command=populate_table_from_db3)
load_config_button.grid(row=0, column=0, padx=5, pady=5)

# Create a frame for the buttons
button_frame = ttk.Frame(root)
button_frame.grid(row=0, column=1, padx=10, pady=10)

# Add some buttons to the right frame
reset_button = ttk.Button(button_frame, 
                          text="Reset", 
                          style='LGV.TButton',
                          command=lambda: print("Reset clicked"))
reset_button.pack(pady=5)

run_button = ttk.Button(button_frame, 
                        text="Run",
                        style='LGV.TButton', 
                        command=lambda: print("Run clicked"))
run_button.pack(pady=5)

stop_button = ttk.Button(button_frame, 
                         text="Stop", 
                         style='LGV.TButton',
                         command=lambda: print("Stop clicked"))
stop_button.pack(pady=5)

man_auto_button = ttk.Button(button_frame, 
                             text="Man/Auto",
                             style='LGV.TButton',
                             command=lambda: print("Man/Auto clicked"))
man_auto_button.pack(pady=5)

dis_horn_button = ttk.Button(button_frame, 
                             text="Disable Horn", 
                             style='LGV.TButton',
                             command=lambda: print("Disable Horn clicked"))
dis_horn_button.pack(pady=5)

load_table_data_from_xml(treeview)

root.mainloop()


# 1. select LGV, 
# changing lgv drops previous connection


# two inputs, table or manual entry. In manual add just ip

# reset, run, stop, manual/auto and disable horn only needed