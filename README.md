

# APT Proxy Configuration Editor
aka
# apt-proxy-edit

Edit apt.conf to include proxies with ease.

**Version:** 0.7.10 (as per the referenced Python script)

## Program Description and Purpose

The APT Proxy Configuration Editor is a graphical Python application designed for Linux systems that use the Advanced Package Tool (APT). Its primary purpose is to simplify the management of APT proxy server settings. 

Users can:
* View currently configured proxy servers (both enabled and disabled).
* Add new proxy server entries for HTTP, HTTPS, FTP, and SOCKS.
* Edit existing proxy configurations, including their name, type, URL, and enabled status.
* Enable or disable specific proxy entries.
* Remove proxy configurations.

The application provides a user-friendly interface to modify the `/etc/apt/apt.conf` file, which can otherwise be daunting for users unfamiliar with its syntax. It also includes features like:
* Automatic backup of the `apt.conf` file before making changes.
* Auto-correction of minor whitespace issues in existing proxy lines.
* A helper to set up a Polkit policy for smoother privilege escalation with `pkexec`.
* Support for custom names for proxy entries, stored as comments in the `apt.conf` file for better organization.

This tool aims to make APT proxy management more accessible and less error-prone.

## System Requirements and Dependencies

* **Operating System:** An APT-based Linux distribution (e.g., Debian, Ubuntu, Linux Mint, and their derivatives).
* **Python:** Python 3.x.
* **Tkinter:** The Tkinter library for Python, which is usually included with standard Python installations. If not, it can typically be installed via your distribution's package manager (e.g., `sudo apt install python3-tk`).
* **Optional (for enhanced privilege escalation):**
    * `pkexec` (part of Polkit) for the "Elevate Privileges" feature.
    * `zenity` for a graphical password prompt if `pkexec` is not fully configured or preferred for `sudo -E` fallback. (e.g., `sudo apt install zenity`).
* **Permissions:**
    * Read access to `/etc/apt/apt.conf` is needed to view settings.
    * Write access (root privileges) to `/etc/apt/apt.conf` is required to save changes, auto-correct the file, or set up the Polkit policy.

## Setup and Installation

There are two primary ways to use this application:

### Option 1: Direct Execution (Recommended for quick use or development)

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/mrsurge/apt-proxy-edit/
    cd apt-proxy-edit
    ```

2.  **Ensure Files are Present:**
    Make sure the following files from the repository are in the same directory:
    * `aptproxies.py` (the main Python script)
    * `icon.png` (the application icon)
    * `install.sh` (the installation script, if you choose to use Option 2 later)

3.  **Make the Python Script Executable:**
    ```bash
    chmod +x aptproxies.py
    ```

4.  **Run the Application:**
    * **Without root privileges (read-only mode):**
        ```bash
        ./aptproxies.py
        ```
        In this mode, you can view settings but cannot save changes or use features requiring root.
    * **With root privileges (full functionality):**
        The recommended way for GUI applications is to preserve your user's display environment:
        ```bash
        sudo -E ./aptproxies.py
        ```
        Alternatively, if you have set up the Polkit policy (see "Using the Interface" below), the "Elevate Privileges" menu option within the application should work.

### Option 2: Using the Installation Script (for system-wide installation)

The `install.sh` script automates copying the application files to system directories and creates a desktop menu entry.

1.  **Clone the Repository (if not already done):**
    ```bash
    git clone https://github.com/mrsurge/apt-proxy-edit/
    cd apt-proxy-edit
    ```

2.  **Ensure Files are Present:**
    As above, ensure `aptproxies.py`, `icon.png`, and `install.sh` are in the current directory.

3.  **Make the Installation Script Executable:**
    ```bash
    chmod +x install.sh
    ```

4.  **Run the Installation Script with Sudo:**
    ```bash
    sudo ./install.sh
    ```
    The script will:
    * Prompt you if an existing installation is found and ask if you want to overwrite it.
    * Copy `aptproxies.py` and `icon.png` to `/opt/APTProxyEditor/`.
    * Create a symbolic link `apt-proxy-editor` in `/usr/local/bin/` so you can run the application by typing `apt-proxy-editor` in the terminal.
    * Copy `icon.png` to `/usr/share/pixmaps/`.
    * Create a `.desktop` file in `/usr/share/applications/` to make the application appear in your system's application menu.
    * Attempt to update the desktop database.

    After installation, you should be able to launch "APT Proxy Editor" from your application menu or by typing `apt-proxy-editor` in a terminal.

## Using the Interface

1.  **Launching:**
    * If installed: Find "APT Proxy Editor" in your application menu or type `apt-proxy-editor` in a terminal.
    * If running directly: Use `./aptproxies.py` (read-only) or `sudo -E ./aptproxies.py` (writable).

2.  **Main Window:**
    * The application displays two tables:
        * **Enabled Proxies:** Shows proxy configurations that are currently active in `/etc/apt/apt.conf`.
        * **Disabled / Placeholder Proxies:** Shows proxy configurations that are commented out in `/etc/apt/apt.conf` or are placeholders for standard types (HTTP, HTTPS, FTP, SOCKS) if no configuration exists for them.
    * Each entry displays its **Name** (if defined), **Type**, and **URL**.

3.  **Actions (Buttons and Menu):**
    * **Add Proxy...:** Opens a dialog to define a new proxy. You can specify:
        * **Name (Optional):** A friendly name for the proxy (e.g., "Work Proxy," "Home SOCKS"). This name is stored as a special comment in `apt.conf`.
        * **Proxy Type:** HTTP, HTTPS, FTP, or SOCKS (select from dropdown).
        * **URL:** The full proxy URL (e.g., `http://user:pass@proxy.example.com:8080`, `socks5h://localhost:9050`).
        * **Enabled (Checkbox):** Check to make this proxy active. If checked, it will be added to the "Enabled Proxies" table (subject to uniqueness rules: only one enabled proxy per type is allowed). If unchecked, it goes to the "Disabled Proxies" table.
    * **Edit Selected...:** (Also accessible by double-clicking an entry) Opens the same dialog as "Add Proxy," pre-filled with the selected proxy's details, allowing you to modify them.
    * **Remove Selected:** (Also accessible by pressing the Delete key on a selected entry) Deletes the selected proxy configuration entirely from the list (and from `apt.conf` upon saving). Prompts for confirmation.
    * **File > Save (Ctrl+S):** Saves all current changes (additions, edits, removals, enabled/disabled status) to the `/etc/apt/apt.conf` file. Requires root privileges. A backup is created before saving.
    * **File > Reload (Ctrl+R):** Discards any unsaved changes and reloads the configuration from `/etc/apt/apt.conf`. Prompts for confirmation if there are unsaved changes.
    * **File > Elevate Privileges...:** Attempts to relaunch the application with root privileges.
        * It will first try using `zenity` for a graphical password prompt to run with `sudo -E` (which preserves your display environment).
        * If `zenity` or `sudo` are unavailable, it falls back to `pkexec`. For `pkexec` to work reliably with GUI applications, a Polkit policy might be needed.
    * **File > Setup Polkit for Elevation...:** (Linux only) This helper attempts to create the necessary Polkit policy file for `pkexec`. It will ask for your `sudo` password to write the policy to `/usr/share/polkit-1/actions/`. This can make the "Elevate Privileges..." option work more smoothly via `pkexec`.
    * **File > Exit (Ctrl+Q):** Closes the application. Prompts to save if there are unsaved changes.
    * **Help > About:** Displays information about the application.

4.  **Status Bar:**
    * Shows the current mode (Read-only or Ready), the path to the configuration file being managed, and status messages for operations.

5.  **Important Notes on Usage:**
    * **Root Privileges:** To save any changes, add, edit, or remove proxies that modify `/etc/apt/apt.conf`, or to use the "Setup Polkit" feature, the application needs root privileges. Use "Elevate Privileges..." or run the script with `sudo -E`.
    * **Uniqueness:** Only one proxy of each type (HTTP, HTTPS, FTP, SOCKS) can be *enabled* at a time. The application will prevent you from enabling a second proxy of the same type if one is already active.
    * **Placeholders:** If no configuration (enabled or disabled) exists for HTTP, HTTPS, FTP, or SOCKS, a blank, disabled placeholder entry will appear in the "Disabled / Placeholder Proxies" table, allowing you to easily add a configuration for that type.
    * **Backups:** The application automatically creates a timestamped backup of `/etc/apt/apt.conf` before any auto-correction or manual save operation that modifies the file.

This will be the first of a number of gui scripts that im working on to graphically manipulate key system configuration files present in many common linux systems (ex. fstabs, .bashrc, system init files, etc) that I am planning on releasing. Many of which the big distros left out any graphical interface in which to make simple changes.  Admittedly, much of this code is generated and trouble shot with the help of AI, but I comb through the code personally and test all my work on my personal machine... which brings me to eplainnig the true purpose why no one really works on stuff like this and why im doing it in the manner I am... the ammount of work it takes to create something that changes a few strings on a document in an x11 or wayland or whatever window takes a mountain of coding and TONS of debugging for multiple case senarios, distros,  etc et... all that have to be considered lest the system not start because of some hakky s#!+,  when the entire time one could just "echo 'somestring' >> 'some config file' and be done with it. But the process of doing that over and over again, especialy on fresh installs, gets mindnumbingly tedious. 

Sooo Heerya go.. this script helps me loads when switching back and forth to my phones hackkey hotspot that requires me to bypass my carriers restrictions to use with an on device proxy server.  And when I need to use apt again on a normal connection this thing makes it extremely easy to turn it back off. Feel free to make/suggest any changes
