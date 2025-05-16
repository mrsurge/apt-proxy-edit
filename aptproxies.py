#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import os
import re
import shutil
import datetime
import subprocess
import sys

# --- Global Configuration ---
APT_CONF_PATH = "/etc/apt/apt.conf"
# APT_CONF_PATH = "dummy_apt.conf" # For testing

APP_VERSION = "0.7.10 - Dual Icon Path (Installed & Local)" # Version from previous correct state
APP_NAME = "APT Proxy Configuration Editor"
NAME_COMMENT_PREFIX = "## APT Proxy Editor Name: "

# --- Icon Configuration ---
# Primary path for the icon when the application is "installed" by install.sh
INSTALLED_APP_DIR = "/opt/APTProxyEditor" 
INSTALLED_ICON_FILENAME = "icon.png" 
# This line defines the variable that was reported as missing.
# It constructs the full path to where the icon is expected after installation.
INSTALLED_ICON_PATH = os.path.join(INSTALLED_APP_DIR, INSTALLED_ICON_FILENAME)

# Fallback icon name if running locally (not installed) or if INSTALLED_ICON_PATH not found
LOCAL_ICON_FILENAME = "icon.png" 


# --- Polkit Configuration (IMPORTANT for pkexec) ---
POLKIT_ACTION_ID = "com.yourorg.aptproxyeditor.pkexec" 
POLKIT_POLICY_FILENAME = f"{POLKIT_ACTION_ID}.policy"
POLKIT_POLICY_PATH = f"/usr/share/polkit-1/actions/{POLKIT_POLICY_FILENAME}"


# --- Data Structures ---
class ProxyEntry:
    """Represents a single proxy entry from the apt.conf file."""
    def __init__(self, line_id, proxy_type, url, enabled, name="", original_lines=None):
        self.id = line_id
        self.proxy_type = proxy_type.upper()
        self.url = url
        self.enabled = enabled
        self.name = name 
        self.original_lines = original_lines if original_lines is not None else []

    def to_conf_strings(self):
        """Generates the list of strings for this proxy for apt.conf (name comment + proxy line)."""
        strings = []
        if self.name:
            strings.append(f"{NAME_COMMENT_PREFIX}{self.name}")
        
        proxy_line_content = f'Acquire::{self.proxy_type}::Proxy "{self.url}";'
        if self.enabled:
            strings.append(proxy_line_content)
        else:
            strings.append(f"# {proxy_line_content}")
        return strings

    def __repr__(self):
        return f"ProxyEntry(id={self.id}, name='{self.name}', type='{self.proxy_type}', url='{self.url}', enabled={self.enabled})"

# --- Proxy Management Logic ---
class ProxyManager:
    """Handles loading, parsing, modifying, and saving proxy configurations."""
    def __init__(self, conf_path_setting):
        self.conf_path_setting = conf_path_setting
        self.proxies = []
        self.next_id = 0
        self.initial_syntax_error = None
        self.apt_conf_exists = False
        self.last_used_effective_path = ""

    def _generate_id(self):
        self.next_id += 1
        return str(self.next_id)

    def _get_effective_conf_path(self):
        path = self.conf_path_setting
        if path == "dummy_apt.conf" and not os.path.isabs(path):
            script_dir = os.path.dirname(os.path.abspath(__file__)) if not getattr(sys, 'frozen', False) else os.path.dirname(sys.executable)
            path = os.path.join(script_dir, path)
        self.last_used_effective_path = os.path.abspath(path)
        self.apt_conf_exists = os.path.exists(self.last_used_effective_path)
        return self.last_used_effective_path

    def can_write_to_conf(self):
        path_to_check = self._get_effective_conf_path()
        if self.apt_conf_exists:
            return os.access(path_to_check, os.W_OK)
        parent_dir = os.path.dirname(path_to_check)
        return os.access(parent_dir if parent_dir else ".", os.W_OK)

    def load_proxies_from_conf(self):
        self.proxies = []
        self.next_id = 0
        self.initial_syntax_error = None
        corrections_made_and_saved = False 
        effective_conf_path = self._get_effective_conf_path()

        print(f"DEBUG: Attempting to load from: {effective_conf_path}")
        print(f"DEBUG: File exists check: {self.apt_conf_exists}")

        if not self.apt_conf_exists:
            print(f"DEBUG: Config file '{effective_conf_path}' not found. Adding placeholders.")
            self._add_placeholder_proxies_if_needed()
            return corrections_made_and_saved

        original_lines_from_file = []
        try:
            with open(effective_conf_path, 'r') as f:
                original_lines_from_file = f.readlines()
            print(f"DEBUG: Read {len(original_lines_from_file)} lines from {effective_conf_path}")
        except IOError as e:
            self.initial_syntax_error = f"IOError reading '{effective_conf_path}': {e}"
            print(f"DEBUG: {self.initial_syntax_error}")
            return corrections_made_and_saved

        lines_to_process = list(original_lines_from_file) 
        can_write = self.can_write_to_conf()
        print(f"DEBUG: Can write to config file '{effective_conf_path}': {can_write}")

        if can_write and self.apt_conf_exists:
            print(f"DEBUG: Write privileges detected. Checking for correctable whitespace issues.")
            correction_pattern = re.compile(
                r"^(?P<core_proxy_line>(?:#\s*)?Acquire::(?:HTTP|HTTPS|FTP|SOCKS)::Proxy\s+\"[^\"]+\")"
                r"(?P<problematic_spacing>\s+)"
                r"(?P<semicolon_part>;\s*)$",
                re.IGNORECASE
            )
            temp_corrected_lines = []
            any_line_changed_in_memory = False
            for line_content in lines_to_process: 
                stripped_for_match = line_content.rstrip('\r\n')
                match = correction_pattern.match(stripped_for_match)
                if match and match.group('problematic_spacing'):
                    corrected_line_segment = match.group('core_proxy_line') + ";"
                    if stripped_for_match != corrected_line_segment:
                        print(f"DEBUG: Whitespace issue: '{stripped_for_match}' -> Corrected: '{corrected_line_segment}'")
                        temp_corrected_lines.append(corrected_line_segment + "\n")
                        any_line_changed_in_memory = True
                    else:
                        temp_corrected_lines.append(line_content)
                else:
                    temp_corrected_lines.append(line_content)

            if any_line_changed_in_memory:
                print(f"DEBUG: Whitespace issues identified. Attempting to save corrections.")
                if self.create_backup(effective_conf_path, "pre_whitespace_correction"):
                    try:
                        with open(effective_conf_path, 'w') as f_write:
                            f_write.writelines(temp_corrected_lines)
                        print(f"DEBUG: Successfully saved corrected file: {effective_conf_path}")
                        lines_to_process = temp_corrected_lines 
                        corrections_made_and_saved = True
                    except IOError as e: 
                        error_msg = f"IOError writing corrected file '{effective_conf_path}': {e}"
                        self.initial_syntax_error = (self.initial_syntax_error + "\n" if self.initial_syntax_error else "") + error_msg
                        print(f"DEBUG: {error_msg}. Parsing original content with lenient regex.")
                        lines_to_process = original_lines_from_file 
                        corrections_made_and_saved = False
                else: 
                    warn_msg = f"Backup failed for '{effective_conf_path}'. Auto-correction aborted."
                    self.initial_syntax_error = (self.initial_syntax_error + "\n" if self.initial_syntax_error else "") + warn_msg
                    print(f"DEBUG: {warn_msg}")
                    lines_to_process = original_lines_from_file 
                    corrections_made_and_saved = False
        
        parsing_regex_str = r"^(#\s*)?Acquire::(HTTP|HTTPS|FTP|SOCKS)::Proxy\s+\"([^\"]+)\""
        parsing_regex_str += r";$" if corrections_made_and_saved else r"\s*;"
        print(f"DEBUG: Using {'STRICT' if corrections_made_and_saved else 'LENIENT'} regex for proxy lines.")
        
        proxy_parser = re.compile(parsing_regex_str, re.IGNORECASE)
        name_comment_parser = re.compile(r"^" + re.escape(NAME_COMMENT_PREFIX.strip()) + r"\s*(.*)", re.IGNORECASE)
        
        parsed_proxies_count = 0
        last_seen_name = None
        collected_original_lines_for_entry = []

        for line_num, current_line_content in enumerate(lines_to_process):
            stripped_line = current_line_content.strip()
            collected_original_lines_for_entry.append(current_line_content) 

            name_match = name_comment_parser.match(stripped_line)
            if name_match:
                last_seen_name = name_match.group(1).strip()
                print(f"DEBUG: Found name comment: '{last_seen_name}'")
                continue 
            
            proxy_match = proxy_parser.match(stripped_line)
            if proxy_match:
                parsed_proxies_count += 1
                is_commented_proxy_line = bool(proxy_match.group(1)) 
                proxy_type = proxy_match.group(2).upper()
                url = proxy_match.group(3)
                entry_id = self._generate_id()
                actual_enabled_status = not is_commented_proxy_line
                current_name = last_seen_name if last_seen_name else ""
                
                self.proxies.append(ProxyEntry(entry_id, proxy_type, url, actual_enabled_status, 
                                               name=current_name, 
                                               original_lines=list(collected_original_lines_for_entry)))
                print(f"DEBUG: Matched proxy: Name='{current_name}', Type={proxy_type}, URL='{url}', Enabled={actual_enabled_status}")
                
                last_seen_name = None 
                collected_original_lines_for_entry = [] 
            
            elif stripped_line and not stripped_line.startswith("#"): 
                if "::Proxy" in stripped_line: 
                    warning_msg = f"Warning: Possible malformed proxy line {line_num+1}: '{stripped_line[:70]}...'"
                    self.initial_syntax_error = (self.initial_syntax_error + "\n" if self.initial_syntax_error else "") + warning_msg
                    print(f"DEBUG: {warning_msg}")
                last_seen_name = None 
                collected_original_lines_for_entry = [] 
            elif not stripped_line: 
                last_seen_name = None 
                collected_original_lines_for_entry = []

        print(f"DEBUG: Parsed {parsed_proxies_count} proxy entries from content.")
        self._add_placeholder_proxies_if_needed()
        print(f"DEBUG: Final self.proxies list size: {len(self.proxies)}")
        return corrections_made_and_saved

    def _add_placeholder_proxies_if_needed(self):
        standard_types = ["HTTP", "HTTPS", "FTP", "SOCKS"]
        existing_types_with_entries = {p.proxy_type.upper() for p in self.proxies if p.url or p.name} 
        
        for std_type in standard_types:
            if std_type not in existing_types_with_entries:
                if not any(p.proxy_type.upper() == std_type and not p.url and not p.name for p in self.proxies):
                    entry_id = self._generate_id()
                    self.proxies.append(ProxyEntry(entry_id, std_type, "", False, name=""))
                    print(f"DEBUG: Added placeholder for {std_type}")

    def get_proxy_by_id(self, entry_id):
        for proxy in self.proxies:
            if proxy.id == entry_id: return proxy
        return None

    def add_proxy(self, name, proxy_type, url, enabled):
        new_id = self._generate_id()
        new_proxy = ProxyEntry(new_id, proxy_type, url, enabled, name=name)
        self.proxies.append(new_proxy)
        return new_id

    def update_proxy(self, entry_id, name, new_type, new_url, new_enabled):
        proxy = self.get_proxy_by_id(entry_id)
        if proxy:
            proxy.name = name
            proxy.proxy_type = new_type.upper()
            proxy.url = new_url
            proxy.enabled = new_enabled
            return True
        return False

    def remove_proxy(self, entry_id):
        proxy = self.get_proxy_by_id(entry_id)
        if proxy:
            self.proxies.remove(proxy)
            return True
        return False

    def is_proxy_type_unique(self, proxy_type_to_check, current_proxy_id=None):
        return sum(1 for p in self.proxies if p.proxy_type.upper() == proxy_type_to_check.upper() and \
                   p.enabled and (not current_proxy_id or p.id != current_proxy_id)) == 0

    def save_proxies_to_conf(self):
        effective_conf_path = self._get_effective_conf_path()
        if not self.can_write_to_conf():
            messagebox.showerror("Permission Denied", f"Cannot write to {effective_conf_path}.")
            return False
        if not self.create_backup(effective_conf_path, "pre_manual_save"):
            if not messagebox.askyesno("Backup Failed", f"Backup failed for {effective_conf_path}. Save anyway?"):
                return False
        
        other_lines_to_preserve = []
        if self.apt_conf_exists:
            try:
                with open(effective_conf_path, 'r') as f_orig:
                    proxy_line_parser = re.compile(r"^(#\s*)?Acquire::(?:HTTP|HTTPS|FTP|SOCKS)::Proxy\s+\"[^\"]+\"\s*;", re.IGNORECASE)
                    name_comment_parser = re.compile(r"^" + re.escape(NAME_COMMENT_PREFIX.strip()), re.IGNORECASE)
                    
                    for line in f_orig:
                        stripped = line.strip()
                        if not proxy_line_parser.match(stripped) and not name_comment_parser.match(stripped):
                            other_lines_to_preserve.append(line)
            except IOError as e: print(f"DEBUG: Error reading original file during save: {e}")

        try:
            with open(effective_conf_path, 'w') as f:
                f.writelines(other_lines_to_preserve)
                if other_lines_to_preserve and self.proxies:
                    if other_lines_to_preserve[-1].strip() != "":
                        f.write("\n")
                elif not other_lines_to_preserve and self.proxies: 
                    pass 
                
                for proxy_idx, proxy in enumerate(self.proxies):
                    if proxy.url or proxy.name or (proxy.enabled and proxy.proxy_type):
                        conf_strings = proxy.to_conf_strings()
                        for line_to_write in conf_strings:
                            f.write(line_to_write + "\n")
                        if proxy.name and (proxy_idx < len(self.proxies) -1):
                            next_proxy = self.proxies[proxy_idx+1]
                            if next_proxy.url or next_proxy.name or (next_proxy.enabled and next_proxy.proxy_type):
                                f.write("\n")
            print(f"DEBUG: Successfully saved proxies to {effective_conf_path}")
            return True
        except IOError as e:
            messagebox.showerror("Save Error", f"Failed to save to {effective_conf_path}: {e}")
            print(f"ERROR saving proxies: {e}")
            return False

    def create_backup(self, file_path_to_backup, suffix="backup"):
        if not os.path.exists(file_path_to_backup):
            print(f"DEBUG: No file at {file_path_to_backup} to backup. Skipping.")
            return True
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_dir = os.path.dirname(file_path_to_backup)
            base_filename = os.path.basename(file_path_to_backup) or "apt.conf.rootdir"
            backup_path = os.path.join(backup_dir, f"{base_filename}.{suffix}.{timestamp}")
            shutil.copy2(file_path_to_backup, backup_path)
            print(f"Backup created: {backup_path}")
            return True
        except Exception as e:
            print(f"Backup failed for {file_path_to_backup}: {e}")
            return False

# --- GUI Dialogs ---
class PasswordDialog(simpledialog.Dialog):
    """A simple dialog to ask for a password, masking the input."""
    def __init__(self, parent, title, prompt):
        self.prompt = prompt
        self.password_var = tk.StringVar()
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text=self.prompt).pack(pady=5, padx=5, anchor="w")
        self.entry = ttk.Entry(master, textvariable=self.password_var, show="*", width=30)
        self.entry.pack(pady=5, padx=5, fill=tk.X, expand=True)
        return self.entry # initial focus

    def apply(self):
        self.result = self.password_var.get() # Return the entered password

class ProxyDialog(simpledialog.Dialog):
    def __init__(self, parent, title, proxy_entry=None, manager=None):
        self.proxy, self.manager = proxy_entry, manager
        self.name_var, self.proxy_type_var, self.url_var, self.enabled_var = tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.BooleanVar()
        self.id_to_edit = proxy_entry.id if proxy_entry else None
        
        if self.proxy:
            self.name_var.set(self.proxy.name)
            self.proxy_type_var.set(self.proxy.proxy_type)
            self.url_var.set(self.proxy.url)
            self.enabled_var.set(self.proxy.enabled)
        else: 
            self.proxy_type_var.set("HTTP")
            self.enabled_var.set(True) 
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text="Name (Optional):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.name_entry = ttk.Entry(master, textvariable=self.name_var, width=40)
        self.name_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")

        ttk.Label(master, text="Proxy Type:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.type_combo = ttk.Combobox(master, textvariable=self.proxy_type_var,
                                       values=["HTTP", "HTTPS", "FTP", "SOCKS"], width=38, state="readonly")
        self.type_combo.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        
        ttk.Label(master, text="URL:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.url_entry = ttk.Entry(master, textvariable=self.url_var, width=40)
        self.url_entry.grid(row=2, column=1, padx=5, pady=2, sticky="ew")
        
        self.enabled_check = ttk.Checkbutton(master, text="Enabled", variable=self.enabled_var)
        self.enabled_check.grid(row=3, column=0, columnspan=2, sticky="w", padx=5, pady=5)
        
        master.grid_columnconfigure(1, weight=1)
        return self.name_entry 

    def validate(self):
        name = self.name_var.get().strip()
        ptype, url, enabled = self.proxy_type_var.get().strip().upper(), self.url_var.get().strip(), self.enabled_var.get()
        
        if NAME_COMMENT_PREFIX in name: 
            messagebox.showwarning("Validation Error", f"Name cannot contain '{NAME_COMMENT_PREFIX}'.", parent=self)
            return False
        if not ptype: messagebox.showwarning("Validation Error", "Proxy type empty.", parent=self); return False
        if not url and enabled: messagebox.showwarning("Validation Error", "URL empty for enabled proxy.", parent=self); return False
        if " " in url: messagebox.showwarning("Validation Error", "URL should not contain spaces.", parent=self); return False
        if self.manager and enabled and not self.manager.is_proxy_type_unique(ptype, self.id_to_edit):
             messagebox.showwarning("Validation Error", f"Enabled proxy for '{ptype}' already exists.", parent=self); return False
        return True

    def apply(self):
        self.result = {"name": self.name_var.get().strip(),
                       "proxy_type": self.proxy_type_var.get().strip().upper(),
                       "url": self.url_var.get().strip(), 
                       "enabled": self.enabled_var.get()}

class AboutDialog(simpledialog.Dialog): 
    def __init__(self, parent, title=f"About {APP_NAME}"): super().__init__(parent, title)
    def body(self, master):
        ttk.Label(master, text=APP_NAME, font=("TkDefaultFont", 16, "bold")).pack(pady=10)
        ttk.Label(master, text=f"Version: {APP_VERSION}").pack(pady=2)
        ttk.Label(master, text="Manage APT proxy configurations.").pack(pady=5)
        ttk.Label(master, text=f"Config: {APT_CONF_PATH}").pack(pady=2)
        ttk.Label(master, text="\nGenerated Script").pack(pady=10)
        return None
    def buttonbox(self):
        box = ttk.Frame(self); ttk.Button(box, text="OK", width=10, command=self.ok, default=tk.ACTIVE).pack(pady=5)
        self.bind("<Return>", self.ok); self.bind("<Escape>", self.cancel); box.pack()

# --- Main Application ---
class AptProxyEditorApp:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title(APP_NAME)
        self.root.geometry("750x650") 
        
        # --- Icon loading ---
        icon_path_to_try = None
        # 1. Try the absolute installed path first
        if os.path.exists(INSTALLED_ICON_PATH):
            icon_path_to_try = INSTALLED_ICON_PATH
            print(f"DEBUG: Attempting to load icon from installed path: {INSTALLED_ICON_PATH}")
        else:
            # 2. Fallback to local directory (if not found at installed path or if running locally)
            print(f"DEBUG: Icon not found at installed path '{INSTALLED_ICON_PATH}'.")
            try:
                if getattr(sys, 'frozen', False): 
                    base_path = sys._MEIPASS # For PyInstaller
                else: 
                    base_path = os.path.dirname(os.path.abspath(__file__)) # For .py script
                
                local_icon_full_path = os.path.join(base_path, LOCAL_ICON_FILENAME)
                if os.path.exists(local_icon_full_path):
                    icon_path_to_try = local_icon_full_path
                    print(f"DEBUG: Attempting to load icon from local path: {local_icon_full_path}")
                else:
                    print(f"DEBUG: Icon file '{LOCAL_ICON_FILENAME}' also not found at local path: {local_icon_full_path}.")
            except Exception as e_path:
                 print(f"DEBUG: Error determining local icon path: {e_path}")
        
        if icon_path_to_try:
            try:
                photo = tk.PhotoImage(file=icon_path_to_try)
                self.root.iconphoto(True, photo) 
                print(f"DEBUG: Icon successfully loaded from {icon_path_to_try}")
            except tk.TclError as e:
                print(f"DEBUG: Could not load icon from '{icon_path_to_try}' (TclError: {e}). Ensure it's a valid PNG/GIF.")
            except Exception as e:
                print(f"DEBUG: An unexpected error occurred while loading icon from '{icon_path_to_try}': {e}")
        else:
            print(f"DEBUG: No icon file found. Using default system icon.")
        # --- End Icon loading ---

        self.proxy_manager = ProxyManager(APT_CONF_PATH)
        self.unsaved_changes = False
        self.is_read_only = True
        self._setup_style()
        self._create_widgets()
        self._check_privileges_and_update_gui_status()
        self.load_proxies()
        self.root.protocol("WM_DELETE_WINDOW", self.quit_application)
        if "--elevated-from-gui" in sys.argv and os.name == 'posix' and os.geteuid() == 0:
            messagebox.showinfo("Elevated Privileges", 
                                "Relaunched with root privileges.\n"
                                "Auto-correction of file format (if needed) will be attempted.", 
                                parent=self.root)


    def _setup_style(self): 
        self.style = ttk.Style()
        themes = self.style.theme_names()
        for t in ["clam", "alt", "default"]:
            if t in themes: self.style.theme_use(t); break

    def _create_widgets(self):
        self.menubar = tk.Menu(self.root); self.root.config(menu=self.menubar)
        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="Save", command=self.save_proxies, accelerator="Ctrl+S")
        self.file_menu.add_command(label="Reload", command=self.reload_proxies, accelerator="Ctrl+R")
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Elevate Privileges...", command=self.elevate_privileges)
        self.file_menu.add_command(label="Setup Polkit for Elevation...", command=self.setup_polkit_policy_interactive) 
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.quit_application, accelerator="Ctrl+Q")
        
        self.help_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Help", menu=self.help_menu)
        self.help_menu.add_command(label="About", command=self.show_about_dialog)
        
        for key, cmd in [("<Control-s>", self.save_proxies), ("<Control-r>", self.reload_proxies), ("<Control-q>", self.quit_application)]:
            self.root.bind_all(key, lambda e, c=cmd: c())

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("id", "name", "type", "url") 

        enabled_table_frame = ttk.LabelFrame(main_frame, text="Enabled Proxies", padding="5")
        enabled_table_frame.pack(fill=tk.BOTH, expand=True, pady=(0,5))
        self.enabled_proxy_table = self._create_proxy_table(enabled_table_frame, columns)

        disabled_table_frame = ttk.LabelFrame(main_frame, text="Disabled / Placeholder Proxies", padding="5")
        disabled_table_frame.pack(fill=tk.BOTH, expand=True, pady=(5,5))
        self.disabled_proxy_table = self._create_proxy_table(disabled_table_frame, columns)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(5,0))
        self.add_button = ttk.Button(button_frame, text="Add Proxy...", command=self.add_new_proxy_dialog)
        self.add_button.pack(side=tk.LEFT, padx=(0,5))
        self.edit_button = ttk.Button(button_frame, text="Edit Selected...", command=self.edit_selected_proxy_dialog)
        self.edit_button.pack(side=tk.LEFT, padx=5)
        self.remove_button = ttk.Button(button_frame, text="Remove Selected", command=self.remove_selected_proxy)
        self.remove_button.pack(side=tk.LEFT, padx=5)
        
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w", padding="2 5")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_var.set("Initializing...")

    def _create_proxy_table(self, parent_frame, column_defs):
        table = ttk.Treeview(parent_frame, columns=column_defs, show="headings", selectmode="browse")
        table.heading("id", text="InternalID")
        table.heading("name", text="Name") 
        table.heading("type", text="Type")
        table.heading("url", text="Proxy URL")
        
        table.column("id", width=0, stretch=tk.NO) 
        table.column("name", width=150, minwidth=100, anchor="w") 
        table.column("type", width=80, minwidth=60, anchor="w")
        table.column("url", width=300, minwidth=150, anchor="w") 
        
        scrollbar = ttk.Scrollbar(parent_frame, orient=tk.VERTICAL, command=table.yview)
        table.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        table.pack(fill=tk.BOTH, expand=True)
        
        table.bind("<Double-1>", self.edit_selected_proxy_event)
        table.bind("<Delete>", self.remove_selected_proxy_event)
        return table

    def _check_privileges_and_update_gui_status(self): 
        was_read_only = self.is_read_only
        effective_path = self.proxy_manager._get_effective_conf_path()
        self.is_read_only = not (os.name == 'posix' and os.geteuid() == 0) and not self.proxy_manager.can_write_to_conf()
        
        title_suffix = f" ({os.path.basename(effective_path)})"
        self.root.title(f"{APP_NAME}{' [READ-ONLY]' if self.is_read_only else ''}{title_suffix}")
        self.status_var.set(f"{'Read-only mode. ' if self.is_read_only else 'Ready. '}File: {effective_path}")

        new_state = tk.DISABLED if self.is_read_only else tk.NORMAL
        for widget in [self.add_button, self.edit_button, self.remove_button]: widget.config(state=new_state)
        self.file_menu.entryconfig("Save", state=new_state)
        self.file_menu.entryconfig("Setup Polkit for Elevation...", state=tk.NORMAL if os.name == 'posix' else tk.DISABLED) 

        if was_read_only and not self.is_read_only: print("DEBUG: Privileges changed to writable.")
        elif not was_read_only and self.is_read_only: print("DEBUG: Privileges changed to read-only.")

    def populate_tables(self):
        for table in [self.enabled_proxy_table, self.disabled_proxy_table]:
            for item in table.get_children(): table.delete(item)
        
        def sort_key(p):
            type_order = {"HTTP":0, "HTTPS":1, "FTP":2, "SOCKS":3}
            return (p.name.lower() if p.name else "~", 
                    type_order.get(p.proxy_type, 4), 
                    p.proxy_type)

        for proxy in sorted(self.proxy_manager.proxies, key=sort_key):
            target_table = self.enabled_proxy_table if proxy.enabled else self.disabled_proxy_table
            table_values = (proxy.id, proxy.name, proxy.proxy_type, proxy.url) 
            target_table.insert("", tk.END, iid=proxy.id, values=table_values)
        
        if self.proxy_manager.initial_syntax_error:
            messagebox.showwarning("Config Warning", f"Issues reading config:\n\n{self.proxy_manager.initial_syntax_error}\n\nPlaceholders may have been added.", parent=self.root)
            self.proxy_manager.initial_syntax_error = None

    def load_proxies(self): 
        self.status_var.set(f"Loading from {self.proxy_manager.last_used_effective_path}...")
        self.root.update_idletasks()
        corrections_applied = self.proxy_manager.load_proxies_from_conf()
        if corrections_applied:
            messagebox.showinfo("File Auto-Corrected", f"Whitespace in '{self.proxy_manager.last_used_effective_path}' auto-corrected.", parent=self.root)
        self.populate_tables()
        self.unsaved_changes = False
        self._check_privileges_and_update_gui_status()
        status_msg = f"Loaded {os.path.basename(self.proxy_manager.last_used_effective_path)}. {'Read-only.' if self.is_read_only else 'Ready.'}"
        self.status_var.set(status_msg)

    def reload_proxies(self): 
        if self.unsaved_changes and not messagebox.askyesno("Confirm Reload", "Discard unsaved changes?", parent=self.root): return
        self.load_proxies()

    def save_proxies(self): 
        if self.is_read_only: messagebox.showerror("Read-Only", "Cannot save. Try elevating privileges.", parent=self.root); return
        self.status_var.set(f"Saving to {self.proxy_manager.last_used_effective_path}...")
        if self.proxy_manager.save_proxies_to_conf():
            self.unsaved_changes = False
            self.status_var.set(f"Saved to {os.path.basename(self.proxy_manager.last_used_effective_path)}.")
            messagebox.showinfo("Saved", "Configuration saved.", parent=self.root)
        else: self.status_var.set(f"Save failed for {os.path.basename(self.proxy_manager.last_used_effective_path)}.")

    def add_new_proxy_dialog(self):
        if self.is_read_only: return
        dialog = ProxyDialog(self.root, "Add New Proxy", manager=self.proxy_manager)
        if dialog.result:
            self.proxy_manager.add_proxy(dialog.result["name"],
                                         dialog.result["proxy_type"], 
                                         dialog.result["url"], 
                                         dialog.result["enabled"])
            self.populate_tables(); self.unsaved_changes = True; self.status_var.set("Proxy added. Unsaved.")

    def edit_selected_proxy_dialog(self):
        if self.is_read_only: return
        selected_id, _ = self.get_selected_proxy_id_and_table()
        if not selected_id: messagebox.showinfo("No Selection", "Select proxy to edit.", parent=self.root); return
        proxy_to_edit = self.proxy_manager.get_proxy_by_id(selected_id)
        if not proxy_to_edit: return

        dialog = ProxyDialog(self.root, f"Edit Proxy ({proxy_to_edit.proxy_type})", 
                             proxy_entry=proxy_to_edit, manager=self.proxy_manager)
        if dialog.result:
            self.proxy_manager.update_proxy(selected_id, 
                                            dialog.result["name"],
                                            dialog.result["proxy_type"], 
                                            dialog.result["url"], 
                                            dialog.result["enabled"])
            self.populate_tables(); self.unsaved_changes = True; self.status_var.set("Proxy edited. Unsaved.")

    def edit_selected_proxy_event(self, event): 
        widget = event.widget
        if widget == self.enabled_proxy_table or widget == self.disabled_proxy_table:
             self.edit_selected_proxy_dialog()

    def remove_selected_proxy(self): 
        if self.is_read_only: return
        selected_id, table_origin = self.get_selected_proxy_id_and_table()
        if not selected_id: messagebox.showinfo("No Selection", "Select proxy to remove.", parent=self.root); return
        proxy = self.proxy_manager.get_proxy_by_id(selected_id)
        if proxy and messagebox.askyesno("Confirm Remove", f"Remove '{proxy.name if proxy.name else proxy.proxy_type}' proxy ({proxy.url})?", parent=self.root):
            self.proxy_manager.remove_proxy(selected_id)
            self.populate_tables(); self.unsaved_changes = True; self.status_var.set("Proxy removed. Unsaved.")

    def remove_selected_proxy_event(self, event): 
        self.remove_selected_proxy()

    def get_selected_proxy_id_and_table(self): 
        focused_widget = None
        try: 
            focused_widget = self.root.focus_get()
        except Exception:
            pass

        if focused_widget == self.enabled_proxy_table:
            selection = self.enabled_proxy_table.selection()
            if selection: return selection[0], "enabled"
        elif focused_widget == self.disabled_proxy_table:
            selection = self.disabled_proxy_table.selection()
            if selection: return selection[0], "disabled"
        
        selection_enabled = self.enabled_proxy_table.selection()
        if selection_enabled: return selection_enabled[0], "enabled"
        
        selection_disabled = self.disabled_proxy_table.selection()
        if selection_disabled: return selection_disabled[0], "disabled"
            
        return None, None

    def elevate_privileges(self):
        if os.name == 'posix':
            if os.geteuid() == 0:
                messagebox.showinfo("Privileges", "Already running with root privileges.", parent=self.root)
                if self.is_read_only:
                    self._check_privileges_and_update_gui_status()
                    self.load_proxies() 
                return

            # Attempt 1: Try zenity + sudo -S -E (often more reliable for GUI environment)
            if shutil.which("zenity") and shutil.which("sudo"):
                try:
                    print("DEBUG: Attempting elevation with zenity and sudo -S -E...")
                    password_dialog_tk = PasswordDialog(self.root, "Sudo Password Required",
                                                        "Enter your sudo password to relaunch with root privileges:")
                    sudo_password = password_dialog_tk.result

                    if not sudo_password: 
                        messagebox.showwarning("Elevation Cancelled", "Password entry cancelled or no password provided.", parent=self.root)
                        return
                    
                    script_path = os.path.abspath(sys.argv[0])
                    args_sudo_e = ['sudo', '-S', '-E', sys.executable, script_path, '--elevated-from-gui']
                    
                    messagebox.showinfo("Elevate Privileges (via sudo -E)",
                                        "Attempting to relaunch with administrator privileges using 'sudo -E'.\n"
                                        "The current window may close. The password you entered will be used.",
                                        parent=self.root)

                    process_sudo_e = subprocess.Popen(args_sudo_e, stdin=subprocess.PIPE,
                                                      stdout=subprocess.DEVNULL, 
                                                      stderr=subprocess.PIPE) 
                    try:
                        process_sudo_e.stdin.write((sudo_password + '\n').encode())
                        process_sudo_e.stdin.close()
                        self.root.after(1000, lambda p=process_sudo_e: self._check_sudo_e_stderr(p))
                        return 
                    except Exception as popen_err:
                         print(f"DEBUG: Error during Popen for sudo -S -E: {popen_err}")
                         messagebox.showerror("Elevation Error", f"Error launching sudo: {popen_err}", parent=self.root)
                         return 
                except FileNotFoundError: 
                     print("DEBUG: sudo command not found (unexpected after shutil.which). Will try pkexec.")
                except Exception as e_sudo:
                    messagebox.showerror("Error", f"Failed to elevate privileges with sudo -E: {e_sudo}", parent=self.root)
            else:
                print("DEBUG: zenity or sudo not found. Proceeding to pkexec attempt.")


            # Attempt 2: Fallback to pkexec (if zenity/sudo failed or not available)
            try:
                print("DEBUG: Attempting elevation with pkexec...")
                script_path = os.path.abspath(sys.argv[0])
                script_args_for_pkexec = [script_path, '--elevated-from-gui']
                args_pkexec = ['pkexec', sys.executable] + script_args_for_pkexec # Removed --disable-internal-agent
                
                messagebox.showinfo("Elevate Privileges (via pkexec)",
                                    "Attempting to relaunch with administrator privileges using pkexec. "
                                    "The current window may close. Please grant permissions when prompted.\n\n"
                                    "IMPORTANT:\nIf the new window doesn't appear or shows a display error, "
                                    "it's likely due to pkexec not passing the necessary display environment "
                                    "variables. This often requires a Polkit policy file for this script "
                                    "(see File > Setup Polkit for Elevation).\n"
                                    "If this fails, try running the script directly with:\n"
                                    "sudo -E python3 your_script_name.py",
                                    parent=self.root)
                
                subprocess.Popen(args_pkexec)
                self.quit_application(force_quit=True)
                return

            except FileNotFoundError:
                messagebox.showerror("Error", 
                                     "pkexec, and sudo/zenity approach failed or not available. Cannot elevate privileges automatically. "
                                     "Please run the script with 'sudo -E python3 your_script_name.py'.", 
                                     parent=self.root)
            except Exception as e_pkexec:
                messagebox.showerror("Error", f"Failed to elevate privileges with pkexec: {e_pkexec}", parent=self.root)
        
        else: 
            messagebox.showinfo("Privilege Escalation",
                                "Automatic privilege escalation is primarily for Linux. "
                                "For other operating systems, please run the script as an administrator/root manually if needed.",
                                parent=self.root)

    def _check_sudo_e_stderr(self, process):
        """Helper to check stderr from the sudo -E process after a short delay."""
        try:
            if process.poll() is not None and process.returncode != 0:
                stderr_output = process.stderr.read().decode().strip() if process.stderr else "Unknown sudo error."
                messagebox.showerror("Sudo Elevation Failed", 
                                     f"Failed to elevate with sudo -E.\n"
                                     f"Sudo reported: {stderr_output}\n\n"
                                     "Please ensure you entered the correct password.",
                                     parent=self.root)
                print(f"DEBUG: sudo -E process exited with code {process.returncode}. Stderr: {stderr_output}")
                return 
            else:
                 print("DEBUG: Assuming sudo -E process launched successfully or is handling auth. Quitting current instance.")
                 self.quit_application(force_quit=True)
        except Exception as e:
            print(f"DEBUG: Error in _check_sudo_e_stderr: {e}")
            self.quit_application(force_quit=True)


    def setup_polkit_policy_interactive(self):
        if os.name != 'posix':
            messagebox.showinfo("Polkit Setup", "Polkit policy setup is specific to Linux systems.", parent=self.root)
            return

        if os.path.exists(POLKIT_POLICY_PATH):
            if not messagebox.askyesno("Polkit Policy Exists",
                                       f"A Polkit policy file already exists at:\n{POLKIT_POLICY_PATH}\n\n"
                                       "Do you want to overwrite it? (This requires sudo password)",
                                       parent=self.root):
                return
        else:
            if not messagebox.askyesno("Setup Polkit Policy",
                                       "This will attempt to create a Polkit policy file to allow "
                                       f"'{APP_NAME}' to be launched with root privileges via pkexec "
                                       "more smoothly (e.g., for the 'Elevate Privileges' menu option).\n\n"
                                       f"The policy file will be created at:\n{POLKIT_POLICY_PATH}\n\n"
                                       "This operation requires your sudo password.\nProceed?",
                                       parent=self.root):
                return

        password_dialog = PasswordDialog(self.root, "Sudo Password Required", 
                                         "Enter your sudo password to create/update the Polkit policy file:")
        sudo_password = password_dialog.result

        if not sudo_password:
            messagebox.showwarning("Polkit Setup Aborted", "No password provided. Polkit policy setup cancelled.", parent=self.root)
            return

        python_executable_path = sys.executable
        script_full_path = os.path.abspath(sys.argv[0])

        policy_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/software/polkit/policyconfig-1.0.dtd">
<policyconfig>
  <action id="{POLKIT_ACTION_ID}">
    <description>Run {APP_NAME} with root privileges</description>
    <message>Authentication is required to run {APP_NAME} as root to manage APT proxy settings.</message>
    <icon_name>dialog-password</icon_name>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">{python_executable_path}</annotate>
    <annotate key="org.freedesktop.policykit.exec.argv1">{script_full_path}</annotate>
    <annotate key="org.freedesktop.policykit.exec.argv2">--elevated-from-gui</annotate>
  </action>
</policyconfig>
"""
        try:
            proc_sudo = subprocess.Popen(['sudo', '-S', 'tee', POLKIT_POLICY_PATH], 
                                         stdin=subprocess.PIPE, 
                                         stdout=subprocess.PIPE, 
                                         stderr=subprocess.PIPE)
            stdout_bytes, stderr_bytes = proc_sudo.communicate(input=(sudo_password + '\n' + policy_content).encode())
            returncode = proc_sudo.returncode

            if returncode == 0:
                messagebox.showinfo("Polkit Setup Successful",
                                    f"Polkit policy file created/updated successfully at:\n{POLKIT_POLICY_PATH}\n\n"
                                    "The 'Elevate Privileges' option should now work more reliably.",
                                    parent=self.root)
                print(f"DEBUG: Polkit policy written. stdout: {stdout_bytes.decode()}, stderr: {stderr_bytes.decode()}")
            else:
                error_details = stderr_bytes.decode().strip() if stderr_bytes else "Unknown error."
                if "incorrect password attempt" in error_details.lower() or "try again" in error_details.lower():
                     messagebox.showerror("Polkit Setup Failed",
                                     f"Failed to create/update Polkit policy file.\n\n"
                                     "Reason: Incorrect sudo password or sudo failure.\n\n"
                                     f"Details from sudo: {error_details}", parent=self.root)
                else:
                    messagebox.showerror("Polkit Setup Failed",
                                     f"Failed to create/update Polkit policy file.\n\n"
                                     f"Sudo command return code: {returncode}\n"
                                     f"Error: {error_details}\n\n"
                                     "Ensure you have sudo privileges and entered the correct password. "
                                     "You might need to create this file manually.", parent=self.root)
                print(f"ERROR: Polkit policy write failed. Return code: {returncode}, stderr: {error_details}")

        except FileNotFoundError:
             messagebox.showerror("Polkit Setup Error", "sudo command not found. Cannot set up Polkit policy.", parent=self.root)
        except Exception as e:
            messagebox.showerror("Polkit Setup Error", f"An unexpected error occurred: {e}", parent=self.root)
            print(f"ERROR: Unexpected error during Polkit setup: {e}")


    def show_about_dialog(self): AboutDialog(self.root) 
    def quit_application(self, force_quit=False): 
        if not force_quit and self.unsaved_changes and \
           not messagebox.askyesno("Confirm Exit", "Discard unsaved changes?", parent=self.root): return
        self.root.quit(); self.root.destroy()

if __name__ == "__main__":
    is_root_at_start = (os.name == 'posix' and os.geteuid() == 0)
    is_pkexec_relaunch = "--elevated-from-gui" in sys.argv

    if is_pkexec_relaunch:
        sys.argv.remove("--elevated-from-gui") 
        print("INFO: Script (re)launched with --elevated-from-gui flag.")
        
        if not is_root_at_start: 
             print("WARNING: --elevated-from-gui flag present, but not running as root. Elevation might have failed silently before script execution.")
        
        if not os.environ.get('DISPLAY'):
            error_title = "Display Error (Post-Elevation)"
            error_message_content = (
                "$DISPLAY environment variable is not set for the (presumably) root user.\n\n"
                "This is a common issue when launching GUI applications with pkexec or sometimes sudo "
                "if the environment is not correctly preserved.\n\n"
                "The application cannot start its graphical interface.\n\n"
                "Possible solutions:\n"
                "1. If using 'Elevate Privileges' via pkexec: Ensure a Polkit policy is correctly set up "
                "(use 'File > Setup Polkit for Elevation...' in the non-elevated app first).\n"
                "2. If running manually: Use 'sudo -E python3 your_script_name.py' "
                "(the -E flag preserves your environment).\n\n"
                "See console output for more details."
            )
            cleaned_error_message = error_message_content.replace(chr(92) + 'n' + chr(92) + 'n', chr(92) + 'n')
            print(f"ERROR: {cleaned_error_message}") 
            try:
                temp_root = tk.Tk()
                temp_root.withdraw() 
                messagebox.showerror(error_title, error_message_content)
                temp_root.destroy()
            except tk.TclError as e_tk: 
                print(f"CRITICAL ERROR: Could not initialize Tkinter to show error dialog (TclError: {e_tk}). "
                      "This confirms $DISPLAY is missing or inaccessible for root.")
            except Exception as e_other: 
                print(f"CRITICAL ERROR: An unexpected error occurred trying to show Tkinter error (Exception: {e_other}).")
            sys.exit(1) 

    root = tk.Tk()
    if is_root_at_start and not is_pkexec_relaunch: 
        print("INFO: Script started with root privileges (e.g., via sudo).")
        
    app = AptProxyEditorApp(root)
    root.mainloop()

