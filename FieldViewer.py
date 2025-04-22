import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import pyads
import xml.etree.ElementTree as ET
import os
import threading
import queue
import time

# ----------------------------------------------------------------
# Field Viewer 1.9.1
# ----------------------------------------------------------------

plc = None  # Single ADS connection

device_mappings = {}
ads_vars = {}
ui_elements = {}
routes_dict = {}

poll_thread = None
stop_event = threading.Event()
data_queue = queue.Queue()

# The user-adjustable timer (in seconds) for unforcing
global_timer_seconds = 0

# ----------------------------------------------------------------
# 1) Default ADS variable names for known devices
# ----------------------------------------------------------------
default_ads_vars = {
    "front": {
        "write": "SafetyGlobals.plsFrontHandler.testCaseNumber",
        "read":  "SafetyGlobals.plsFrontHandler.active"
    },
    "rear": {
        "write": "SafetyGlobals.plsRearHandler.testCaseNumber",
        "read":  "SafetyGlobals.plsRearHandler.active"
    },
    "lat_left": {
        "write": "SafetyGlobals.plsLateralHandler.testCaseNumberLeft",
        "read":  "SafetyGlobals.plsLateralHandler.activeLeft"
    },
    "lat_right": {
        "write": "SafetyGlobals.plsLateralHandler.testCaseNumberRight",
        "read":  "SafetyGlobals.plsLateralHandler.activeRight"
    },
    "vertical_left": {
        "write": "SafetyGlobals.plsVerticalFrontHandler.testCaseLeftNumber",
        "read":  "SafetyGlobals.plsVerticalFrontHandler.activeLeft"
    },
    "vertical_right": {
        "write": "SafetyGlobals.plsVerticalFrontHandler.testCaseRightNumber",
        "read":  "SafetyGlobals.plsVerticalFrontHandler.activeRight"
    },
}

# ----------------------------------------------------------------
# 2) Built-in default enumerations for each device
# ----------------------------------------------------------------
built_in_mappings = {
    "front": {
        1: "Micro", 2: "MiniPhysical", 3: "MiniStraight", 4: "MiniLeft", 5: "MiniRight",
        6: "MiniWarehouse", 7: "MiniWideStraight", 8: "MiniWideLeft", 9: "MiniWideRight",
        10: "ShortPhysical", 11: "ShortStraight", 12: "ShortLeft", 13: "ShortRight",
        14: "ShortWarehouse", 15: "ShortWideStraight", 16: "ShortWideLeft", 17: "ShortWideRight",
        18: "MediumPhysical", 19: "MediumStraight", 20: "MediumLeft", 21: "MediumRight",
        22: "MediumWarehouse", 23: "MediumWideStraight", 24: "MediumWideLeft", 25: "MediumWideRight",
        26: "LongPhysical", 27: "LongStraight", 28: "LongLeft", 29: "LongRight",
        30: "LongWarehouse", 31: "LongWideStraight", 32: "LongWideLeft", 33: "LongWideRight",
        34: "ExtraLongPhysical", 35: "ExtraLongStraight", 36: "ExtraLongLeft", 37: "ExtraLongRight",
        38: "ExtraLongWarehouse", 39: "ExtraLongWideStraight", 40: "ExtraLongWideLeft",
        41: "ExtraLongWideRight", 42: "MiniNoWarning"
    },
    "rear": {
        1: "Minimal", 2: "ForkEdgePhysical", 3: "ForkEdgeStraight", 4: "ForkEdgeLeft",
        5: "ForkEdgeRight", 6: "ForkEdgeWarehouse", 7: "ForkEdgeRotation",
        8: "ForkEdgeSinglePallet", 9: "ForkEdgeNoWarning", 10: "ForkEdgeLeftNoWarning",
        11: "ForkEdgeRightNoWarning", 12: "ForkEdgeWideStraight", 13: "ForkEdgeWideLeft",
        14: "ForkEdgeWideRight", 15: "ForkEdgeOutPhysical", 16: "ForkEdgeOut",
        17: "ForkEdgeOutWarehouse", 18: "ForkEdgeOutWide", 19: "ForkEdgeOutDouble",
        20: "Conveyor", 21: "ShortPhysical", 22: "ShortStraight", 23: "ShortLeft", 24: "ShortRight",
        25: "ShortWarehouse", 26: "ShortWideStraight", 27: "ShortWideLeft", 28: "ShortWideRight",
        29: "ShortOutPhysical", 30: "ShortOut", 31: "ShortOutWarehouse", 32: "ShortOutWide",
        33: "MediumPhysical", 34: "MediumStraight", 35: "MediumLeft", 36: "MediumRight",
        37: "MediumWarehouse", 38: "MediumWideStraight", 39: "MediumWideLeft", 40: "MediumWideRight",
        41: "MediumOutPhysical", 42: "MediumOut", 43: "MediumOutWarehouse", 44: "MediumOutWide",
        45: "LongPhysical", 46: "LongStraight", 47: "LongLeft", 48: "LongRight",
        49: "LongWideStraight", 50: "LongWideLeft", 51: "LongWideRight", 52: "LongWarehouse",
        53: "UnknownCheck", 54: "UnknownLoad", 55: "UnknownUnload", 56: "UnknownUnloadWide",
        57: "HalfFork", 58: "ForkEdgeRackLv0"
    },
    "vertical_left": {
        1: "Micro", 2: "Mini", 3: "Short", 4: "ShortLeft", 5: "ShortRight",
        6: "Medium", 7: "MediumLeft", 8: "MediumRight", 9: "Long", 10: "LongLeft",
        11: "LongRight", 12: "Mini_RearForkEdge", 13: "Mini_RearShort",
        14: "Mini_Charger", 15: "Null"
    },
    "vertical_right": {
        1: "Micro", 2: "Mini", 3: "Short", 4: "ShortLeft", 5: "ShortRight",
        6: "Medium", 7: "MediumLeft", 8: "MediumRight", 9: "Long", 10: "LongLeft",
        11: "LongRight", 12: "Mini_RearForkEdge", 13: "Mini_RearShort",
        14: "Mini_Charger", 15: "Null"
    },
    "lat_left": {
        1: "Micro", 2: "Mini", 3: "Mini2", 4: "Mini3", 5: "Short", 6: "Medium", 7: "Long",
        8: "ShortFwMiniBw", 9: "MediumFwMiniBw", 10: "LongFwMiniBw",
        11: "ShortBwMiniFw", 12: "MediumBwMiniFw", 13: "LongBwMiniFw",
        14: "odMiniPhysical", 15: "odMini", 16: "odMiniFwShort", 17: "odMiniFwMedium", 18: "odMiniFwLong",
        19: "odMiniBwShort", 20: "odMiniBwMedium", 21: "odMiniBwLong",
        22: "odShortPhysical", 23: "odShort", 24: "odShortFwShort", 25: "odShortFwMedium",
        26: "odShortFwLong", 27: "odShortBwShort", 28: "odShortBwMedium", 29: "odShortBwLong",
        30: "odMediumPhysical", 31: "odMedium", 32: "odMediumFwShort", 33: "odMediumFwMedium",
        34: "odMediumFwLong", 35: "odMediumBwShort", 36: "odMediumBwMedium", 37: "odMediumBwLong",
        38: "odLongPhysical", 39: "odLong", 40: "odLongFwShort", 41: "odLongFwMedium", 42: "odLongFwLong",
        43: "odLongBwShort", 44: "odLongBwMedium", 45: "odLongBwLong"
    },
    "lat_right": {
        1: "Micro", 2: "Mini", 3: "Mini2", 4: "Mini3", 5: "Short", 6: "Medium", 7: "Long",
        8: "ShortFwMiniBw", 9: "MediumFwMiniBw", 10: "LongFwMiniBw",
        11: "ShortBwMiniFw", 12: "MediumBwMiniFw", 13: "LongBwMiniFw",
        14: "odMiniPhysical", 15: "odMini", 16: "odMiniFwShort", 17: "odMiniFwMedium", 18: "odMiniFwLong",
        19: "odMiniBwShort", 20: "odMiniBwMedium", 21: "odMiniBwLong",
        22: "odShortPhysical", 23: "odShort", 24: "odShortFwShort", 25: "odShortFwMedium",
        26: "odShortFwLong", 27: "odShortBwShort", 28: "odShortBwMedium", 29: "odShortBwLong",
        30: "odMediumPhysical", 31: "odMedium", 32: "odMediumFwShort", 33: "odMediumFwMedium",
        34: "odMediumFwLong", 35: "odMediumBwShort", 36: "odMediumBwMedium", 37: "odMediumBwLong",
        38: "odLongPhysical", 39: "odLong", 40: "odLongFwShort", 41: "odLongFwMedium", 42: "odLongFwLong",
        43: "odLongBwShort", 44: "odLongBwMedium", 45: "odLongBwLong"
    }
}

# ----------------------------------------------------------------
# 3) device_warning_map for reading "PLS.<deviceName>.warningViolated"
#    This is needed for the code that sets the warn_color to red, green, or (new) yellow.
# ----------------------------------------------------------------
device_warning_map = {
    "front":         "PLS.front.warningViolated",
    "rear":          "PLS.rear.warningViolated",
    "lat_left":      "PLS.lateralLeft.warningViolated",
    "lat_right":     "PLS.lateralRight.warningViolated",
    "vertical_left": "PLS.verticalFrontLeft.warningViolated",
    "vertical_right":"PLS.verticalFrontRight.warningViolated",
}

device_protective_map = {
    "front":         "PLS.front.protectiveViolated",
    "rear":          "PLS.rear.protectiveViolated",
    "lat_left":      "PLS.lateralLeft.protectiveViolated",
    "lat_right":     "PLS.lateralRight.protectiveViolated",
    "vertical_left": "PLS.verticalFrontLeft.protectiveViolated",
    "vertical_right":"PLS.verticalFrontRight.protectiveViolated",
}


# ----------------------------------------------------------------
# 4) Merging built-in mappings on startup
# ----------------------------------------------------------------
def load_built_in_mappings():
    """
    Merges built_in_mappings into device_mappings for known devices
    that are not already in device_mappings.
    """
    for dev, mapping in built_in_mappings.items():
        if dev not in device_mappings:
            device_mappings[dev] = mapping

# ----------------------------------------------------------------
# 5) read_static_routes (for AMS NetIDs) and reset_indicators_and_reads
# ----------------------------------------------------------------
def read_static_routes():
    static_routes_path = r"C:\TwinCAT\3.1\Target\StaticRoutes.xml"
    routes = {}
    if not os.path.exists(static_routes_path):
        print(f"Static routes file not found at {static_routes_path}")
        return routes
    try:
        tree = ET.parse(static_routes_path)
        root = tree.getroot()
        for route in root.findall(".//Route"):
            name_elem = route.find("Name")
            address_elem = route.find("Address")
            if name_elem is not None and address_elem is not None:
                route_name = name_elem.text.strip()
                if "lgv" in route_name.lower():
                    ip_address = address_elem.text.strip()
                    if not ip_address.endswith(".1.1"):
                        ip_address += ".1.1"
                    routes[route_name] = ip_address
        return routes
    except Exception as e:
        print(f"Error reading static routes: {e}")
        return {}

def reset_indicators_and_reads():
    """
    Resets all device indicators: active label, warning color, forcing label, write button text.
    Called on disconnect.
    """
    for device, ui in ui_elements.items():
        ui["label"].config(text="Active: Not read")
        warn_label = ui.get("warning_label")
        if warn_label:
            warn_label.config(bg="gray")
        forcing_lbl = ui.get("forcing_label")
        if forcing_lbl:
            forcing_lbl.config(text="")
        write_btn = ui.get("button")
        if write_btn:
            write_btn.config(text="Write", fg="black")

# ----------------------------------------------------------------
# 6) Import XML from menu, rebuild device panels
# ----------------------------------------------------------------
def import_xml():
    filepath = filedialog.askopenfilename(
        title="Select XML File",
        filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
    )
    if not filepath:
        return
    mapping, type_name = load_mapping_xml(filepath)
    if mapping:
        device_keys = []
        if type_name:
            tn = type_name.lower()
            if "vertical" in tn:
                device_keys = ["vertical_left", "vertical_right"]
            elif tn == "frontcase":
                device_keys = ["front"]
            elif tn == "rearcase":
                device_keys = ["rear"]
            elif tn == "lateralcase":
                device_keys = ["lat_left", "lat_right"]
            else:
                key = tn.replace("case", "").strip()
                device_keys = [key]
        else:
            device_keys = ["imported_device"]
        
        for key in device_keys:
            device_mappings[key] = mapping
            print(f"Imported mapping for device '{key}' from '{filepath}'")
        setup_ads_vars()
        rebuild_device_panels()

def load_mapping_xml(filepath):
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        ns = {'tc': 'http://www.plcopen.org/xml/tc6_0200'}
        dataTypeElem = root.find(".//tc:dataType", ns)
        if dataTypeElem is None:
            print(f"No 'dataType' element found in {filepath}")
            return None, None
        type_name = dataTypeElem.get("name")
        valuesElem = dataTypeElem.find(".//tc:baseType/tc:enum/tc:values", ns)
        if valuesElem is None:
            print(f"No enum values found in {filepath}")
            return None, None
        mapping = {}
        for valueElem in valuesElem.findall("tc:value", ns):
            key = int(valueElem.get("value"))
            enum_name = valueElem.get("name")
            mapping[key] = enum_name
        return mapping, type_name
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load XML: {e}")
        return None, None

def rebuild_device_panels():
    for dev, ui in ui_elements.items():
        ui["frame"].destroy()
    ui_elements.clear()
    create_device_panels()

# ----------------------------------------------------------------
# 7) Setup ADS vars
# ----------------------------------------------------------------
def setup_ads_vars():
    ads_vars.clear()
    for device in device_mappings:
        if device in default_ads_vars:
            ads_vars[device] = default_ads_vars[device]
        else:
            device_cap = "".join(word.capitalize() for word in device.split("_"))
            ads_vars[device] = {
                "write": f"SafetyGlobals.pls{device_cap}Handler.testCaseNumber",
                "read":  f"SafetyGlobals.pls{device_cap}Handler.active"
            }

# ----------------------------------------------------------------
# 8) Polling thread
#    New logic: If warningViolated==TRUE but "active" (val) == 0 => YELLOW
#    else if warningViolated==TRUE => RED, else => GREEN
# ----------------------------------------------------------------

def get_running_var_name(device):
    custom_run_map = {
        "front":         "PLS.front.running",
        "rear":          "PLS.rear.running",
        "lat_left":      "PLS.lateralLeft.running",
        "lat_right":     "PLS.lateralRight.running",
        "vertical_left": "PLS.verticalFrontLeft.running",
        "vertical_right":"PLS.verticalFrontRight.running",
    }
    # Fallback if device not in map:
    return custom_run_map.get(device, f"PLS.{device}.running")
def poll_ads_values():
    while not stop_event.is_set():
        if plc is None:
            time.sleep(1)
            continue

        # Check read_state as a ping
        try:
            ads_state, device_state = plc.read_state()
        except Exception:
            data_queue.put({"comm_lost": True})
            return

        device_results = {}
        for device in sorted(device_mappings.keys()):
            # read "running"
            run_var = get_running_var_name(device)
            is_running = True
            try:
                r_val = plc.read_by_name(run_var, pyads.PLCTYPE_BOOL)
                if r_val is False:
                    is_running = False
            except:
                is_running = False

            if not is_running:
                device_results[device] = {"running": False}
                continue

            active_text = "Comm Error"
            warn_color = "gray"
            btn_text = "Write"
            btn_fg = "black"
            forcing_label = ""

            # read the enumerated "active"
            val = None
            if device in ads_vars:
                read_name = ads_vars[device]["read"]
                try:
                    val = plc.read_by_name(read_name, pyads.PLCTYPE_BYTE)
                    if isinstance(val, bytes):
                        val = int.from_bytes(val, byteorder="little")
                    mapping = device_mappings.get(device, {})
                    active_text = mapping.get(val, f"({val})")
                except:
                    active_text = "Comm Error"

            # read warningViolated
            wvar = device_warning_map.get(device, None)
            wval = False
            if wvar:
                try:
                    wval = plc.read_by_name(wvar, pyads.PLCTYPE_BOOL)
                except:
                    pass

            # read warningViolated
            pvar = device_protective_map.get(device, None)
            pval = False
            if pvar:
                try:
                    pval = plc.read_by_name(pvar, pyads.PLCTYPE_BOOL)
                except:
                    pass

            # if wval is True => check if pval is FALSE => YELLOW else RED
            # if wval is False => GREEN
            if wval:
                if pval:
                
                    warn_color = "red"
                else:
                    warn_color = "yellow"
            else:
                warn_color = "green"

            # testCase bool => forcing?
            bool_var = get_testcase_bool_var(device)
            if bool_var:
                try:
                    tc_val = plc.read_by_name(bool_var, pyads.PLCTYPE_BOOL)
                    if tc_val is True:
                        btn_text = "Unforce"
                        forcing_label = "Forcing"
                    else:
                        btn_text = "Write"
                        forcing_label = ""
                except:
                    btn_text = "CommErr"
                    forcing_label = ""

            device_results[device] = {
                "running": True,
                "active_text": active_text,
                "warn_color": warn_color,
                "btn_text": btn_text,
                "btn_fg": btn_fg,
                "forcing_label": forcing_label
            }

        data_queue.put({"devices": device_results})
        time.sleep(1)

# ----------------------------------------------------------------
# 9) check_queue => update UI
# ----------------------------------------------------------------
def check_queue():
    try:
        while True:
            item = data_queue.get_nowait()
            if "comm_lost" in item:
                messagebox.showerror("Lost Communication", "Connection to the device was lost.")
                disconnect_ads()
                # Instead of 'return', do:
                continue
            if "devices" in item:
                device_results = item["devices"]
                for device, info in device_results.items():
                    if not info.get("running", False):
                        hide_device_panel(device)
                        continue
                    else:
                        show_device_panel(device)

                    ui = ui_elements.get(device)
                    if not ui:
                        continue
                    active_text = info.get("active_text", "Comm Error")
                    warn_color = info.get("warn_color", "gray")
                    btn_text = info.get("btn_text", "Write")
                    btn_fg = info.get("btn_fg", "black")
                    forcing_label = info.get("forcing_label", "")

                    ui["label"].config(text=f"Active: {active_text}")
                    warn_label = ui.get("warning_label")
                    if warn_label:
                        warn_label.config(bg=warn_color)

                    write_btn = ui.get("button")
                    if write_btn:
                        write_btn.config(
                            text=btn_text,
                            fg=btn_fg,
                            command=lambda d=device, b=btn_text: on_write_button_clicked(d, b)
                        )

                    forcing_lbl = ui.get("forcing_label")
                    if forcing_lbl:
                        forcing_lbl.config(text=forcing_label, fg="blue" if forcing_label else "black")

    except queue.Empty:
        pass
    root.after(100, check_queue)

def on_write_button_clicked(device, btn_text):
    if btn_text == "Unforce":
        bool_var = get_testcase_bool_var(device)
        if plc and bool_var:
            try:
                plc.write_by_name(bool_var, False, pyads.PLCTYPE_BOOL)
            except Exception as e:
                messagebox.showerror("Error", f"Failed unforcing for {device}: {e}")
        else:
            messagebox.showerror("Error", "No PLC or bool var not found.")
    else:
        write_test_case(device)

def hide_device_panel(device):
    ui = ui_elements.get(device)
    if not ui:
        return
    frame = ui["frame"]
    frame.pack_forget()

def show_device_panel(device):
    ui = ui_elements.get(device)
    if not ui:
        return
    frame = ui["frame"]
    if not frame.winfo_ismapped():
        frame.pack(fill="x", padx=5, pady=3)

# ----------------------------------------------------------------
# 10) Helpers: get_testcase_bool_var, get_timer_seconds
# ----------------------------------------------------------------
def get_testcase_bool_var(device):
    if device not in ads_vars:
        return None
    write_name = ads_vars[device]["write"]
    bool_var = write_name.replace("NumberLeft", "Left")
    bool_var = bool_var.replace("NumberRight", "Right")
    bool_var = bool_var.replace("Number", "")
    return bool_var

def get_timer_seconds():
    return global_timer_seconds

# ----------------------------------------------------------------
# 11) write_test_case => sets the testCaseNumber and testCase=TRUE
# ----------------------------------------------------------------
def write_test_case(device):
    global plc
    if plc is None:
        messagebox.showerror("Error", "No connection to ADS")
        return

    ui = ui_elements[device]
    selected_value = ui["combobox"].get()
    if not selected_value:
        messagebox.showerror("Error", "No test case selected")
        return

    mapping = device_mappings.get(device)
    if not mapping:
        messagebox.showerror("Error", f"No mapping for device '{device}'")
        return
    reverse_mapping = {v: k for k, v in mapping.items()}
    if selected_value not in reverse_mapping:
        messagebox.showerror("Error", f"Test case '{selected_value}' not found in mapping")
        return
    int_value = reverse_mapping[selected_value]

    if device not in ads_vars:
        messagebox.showerror("Error", f"No ADS vars defined for device '{device}'")
        return

    write_name = ads_vars[device]["write"]
    try:
        plc.write_by_name(write_name, int_value, pyads.PLCTYPE_BYTE)
    except Exception as e:
        messagebox.showerror("Error", f"Failed writing testCaseNumber for '{device}': {e}")
        return

    bool_var = get_testcase_bool_var(device)
    if not bool_var:
        messagebox.showerror("Error", f"Could not derive boolean var for device '{device}'")
        return

    try:
        plc.write_by_name(bool_var, True, pyads.PLCTYPE_BOOL)
    except Exception as e:
        messagebox.showerror("Error", f"Failed writing bool testCase for '{device}': {e}")
        return



    timer_s = get_timer_seconds()

    if timer_s > 0:
        def set_testcase_false():
            if plc is not None:
                try:
                    plc.write_by_name(bool_var, False, pyads.PLCTYPE_BOOL)
                except Exception as e:
                    messagebox.showerror(
                        "Error",
                        f"Failed writing {bool_var} = FALSE for '{device}' after {timer_s}s: {e}"
                    )
        root.after(timer_s * 1000, set_testcase_false)


# ----------------------------------------------------------------
# 12) Polling thread control
# ----------------------------------------------------------------
def stop_polling_thread():
    global poll_thread, stop_event
    if poll_thread is not None:
        stop_event.set()
        poll_thread.join(timeout=2)
        poll_thread = None

# ----------------------------------------------------------------
# 13) Disconnect / Connect
# ----------------------------------------------------------------
def disconnect_ads():
    global plc
    if plc is not None:
        for device in device_mappings:
            bool_var = get_testcase_bool_var(device)
            if bool_var and plc is not None:
                try:
                    plc.write_by_name(bool_var, False, pyads.PLCTYPE_BOOL)
                except Exception as e:
                    print(f"Failed to write {bool_var} = False: {e}")

        reset_indicators_and_reads()

        try:
            plc.close()
        except Exception as e:
            print(f"Error closing connection: {e}")

        plc = None
        btn_connect.config(text="Connect", fg="black", state="normal")
        # No pop-up on manual disconnect
    stop_polling_thread()

def start_polling_thread():
    global poll_thread, stop_event
    stop_event.clear()
    poll_thread = threading.Thread(target=poll_ads_values, daemon=True)
    poll_thread.start()

def connect_ads_worker(ams_netid, result_q):
    try:
        plc_local = pyads.Connection(ams_netid, 851)
        plc_local.open()
        ads_state, device_state = plc_local.read_state()
        if ads_state != 5:
            raise Exception(f"ADS state is not RUN (state: {ads_state})")
        result_q.put(("success", plc_local))
    except Exception as e:
        result_q.put(("error", str(e)))

def on_route_selected(event):
    global plc
    if plc is not None:
        disconnect_ads()

def check_connect_result(thread, result_q, selected_route):
    if not thread.is_alive():
        if not result_q.empty():
            result_type, result_value = result_q.get()
            if result_type == "success":
                global plc
                plc = result_value
                btn_connect.config(text="Connected", fg="gray", state="disabled")
                messagebox.showinfo("Connected", f"Successfully connected to {selected_route}")
                start_polling_thread()
            else:
                messagebox.showerror("Error", f"Failed to connect: {result_value}")
        else:
            messagebox.showerror("Error", "Connection timeout")
    else:
        root.after(100, lambda: check_connect_result(thread, result_q, selected_route))

def start_connection():
    global plc
    selected_route = route_combobox.get()
    if not selected_route:
        messagebox.showerror("Error", "No route selected")
        return
    ams_netid = routes_dict.get(selected_route)
    if not ams_netid:
        messagebox.showerror("Error", "Selected route has no valid AMS NetID")
        return

    if plc is not None:
        disconnect_ads()

    result_q = queue.Queue()
    thread = threading.Thread(target=connect_ads_worker, args=(ams_netid, result_q))
    thread.daemon = True
    thread.start()

    root.after(100, lambda: check_connect_result(thread, result_q, selected_route))

# ----------------------------------------------------------------
# 14) Menubar and Timer dialog
# ----------------------------------------------------------------
def create_menubar():
    menubar = tk.Menu(root)
    file_menu = tk.Menu(menubar, tearoff=False)
    file_menu.add_command(label="Import ENUM", command=import_xml)
    menubar.add_cascade(label="File", menu=file_menu)

    options_menu = tk.Menu(menubar, tearoff=False)
    options_menu.add_command(label="Set Timer", command=show_timer_dialog)
    menubar.add_cascade(label="Options", menu=options_menu)

    root.config(menu=menubar)

def show_timer_dialog():
    def on_ok():
        nonlocal entry
        global global_timer_seconds
        try:
            val = int(entry.get())
            if val < 0:
                val = 0
            elif val > 600:
                val = 600
            global_timer_seconds = val
        except:
            pass
        dialog.destroy()

    dialog = tk.Toplevel(root)
    dialog.title("Timer Options")
    tk.Label(dialog, text="Timer(s):(0 for disabled)").pack(padx=10, pady=10)
    entry = tk.Entry(dialog, width=6)
    entry.pack(pady=5)
    entry.insert(0, str(global_timer_seconds))
    tk.Button(dialog, text="OK", command=on_ok).pack(pady=5)

# ----------------------------------------------------------------
# 15) Main UI
# ----------------------------------------------------------------
def create_main_ui():
    global frame_conn, btn_connect, btn_disconnect, route_combobox
    frame_conn = tk.Frame(root, pady=5)
    frame_conn.pack()

    tk.Label(frame_conn, text="Select Route:").grid(row=0, column=0, sticky="w", padx=2, pady=2)
    route_combobox = ttk.Combobox(frame_conn, state="readonly", width=30)
    route_combobox.grid(row=0, column=1, padx=2, pady=2, sticky="w")

    if routes_dict:
        route_names = sorted(routes_dict.keys())
        route_combobox["values"] = route_names
        route_combobox.set(route_names[0])
    else:
        route_combobox["values"] = ["No routes found"]

    route_combobox.bind("<<ComboboxSelected>>", on_route_selected)

    global btn_connect
    btn_connect = tk.Button(frame_conn, text="Connect", command=start_connection, width=10)
    btn_connect.grid(row=0, column=2, padx=5, pady=2)

    global btn_disconnect
    btn_disconnect = tk.Button(frame_conn, text="Disconnect", command=disconnect_ads, width=10)
    btn_disconnect.grid(row=1, column=2, padx=5, pady=2, sticky="n")

def create_device_panels():
    for device in sorted(device_mappings.keys()):
        frame_device = tk.LabelFrame(root, text=device.capitalize(), padx=5, pady=5)
        frame_device.pack(fill="x", padx=5, pady=3)

        lbl_active = tk.Label(frame_device, text="Active: Not read", width=22, anchor="w")
        lbl_active.grid(row=0, column=0, padx=2, pady=2, sticky="w")

        lbl_warning = tk.Label(frame_device, text="", bg="gray", width=20, height=1)
        lbl_warning.grid(row=0, column=1, padx=2, pady=2, sticky="w")

        lbl_forcing = tk.Label(frame_device, text="", fg="blue", width=7, anchor="w")
        lbl_forcing.grid(row=0, column=2, padx=2, pady=2, sticky="w")

        lbl_testcase = tk.Label(frame_device, text="Test Case:", anchor="w")
        lbl_testcase.grid(row=1, column=0, padx=2, pady=2, sticky="w")

        cmb_test_case = ttk.Combobox(frame_device, state="readonly", width=20)
        cmb_test_case.grid(row=1, column=1, padx=2, pady=2, sticky="w")

        mapping = device_mappings[device]
        values = [mapping[k] for k in sorted(mapping.keys())]
        cmb_test_case["values"] = values
        if values:
            cmb_test_case.set(values[0])

        btn_write = tk.Button(frame_device, text="Write", width=10)
        btn_write.grid(row=1, column=2, padx=5, pady=2, sticky="w")

        ui_elements[device] = {
            "frame": frame_device,
            "label": lbl_active,
            "warning_label": lbl_warning,
            "forcing_label": lbl_forcing,
            "button": btn_write,
            "combobox": cmb_test_case
        }

def main():
    # Merge built-in enumerations for known devices
    load_built_in_mappings()
    # Setup ADS variable names
    setup_ads_vars()
    # Read static routes for AMS NetIDs
    global routes_dict
    routes_dict = read_static_routes()

    root.title("Field Viewer 1.9.1")

    create_menubar()
    create_main_ui()
    create_device_panels()

    root.after(100, check_queue)
    root.mainloop()

    stop_polling_thread()
    if plc is not None:
        plc.close()

# -------------------------------------------------------------
# Start the entire app
# -------------------------------------------------------------
root = tk.Tk()
icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
if os.path.exists(icon_path):
    root.iconbitmap(icon_path)

main()
