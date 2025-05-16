#!/bin/bash

# Installation script for APT Proxy Editor
# Version: 1.2 - Refined interactive overwrite prompt.

# --- Configuration ---
APP_NAME="APT Proxy Editor"
SCRIPT_NAME="aptproxies.py" # The name of your main Python script
ICON_NAME="icon.png"        # The name of your source icon file
INSTALL_DIR="/opt/APTProxyEditor"
EXECUTABLE_LINK_DIR="/usr/local/bin"
EXECUTABLE_NAME="apt-proxy-editor" # Command to run the app
ICON_INSTALL_DIR="/usr/share/pixmaps"
INSTALLED_ICON_NAME="$ICON_NAME" 
DESKTOP_FILE_DIR="/usr/share/applications"
DESKTOP_FILE_NAME="apt-proxy-editor.desktop"

# --- Helper Functions ---
echo_info() {
    echo "[INFO] $1"
}

echo_error() {
    echo "[ERROR] $1" >&2
}

# --- Pre-flight Checks ---
# 1. Check if running as root
if [ "$(id -u)" -ne 0 ]; then
    echo_error "This script must be run as root. Please use sudo."
    exit 1
fi

# 2. Check if script and icon files exist in the current directory
if [ ! -f "$SCRIPT_NAME" ]; then
    echo_error "Main application script '$SCRIPT_NAME' not found in the current directory."
    exit 1
fi

icon_found_in_source=true
if [ ! -f "$ICON_NAME" ]; then
    echo_error "Icon file '$ICON_NAME' not found in the current directory."
    echo_info "Proceeding with installation, but the application and menu entry might not have an icon."
    icon_found_in_source=false
fi

# --- Overwrite Logic (Interactive Option) ---
if [ -d "$INSTALL_DIR" ]; then
    echo_info "Existing installation found at $INSTALL_DIR."
    # Prompt the user for confirmation. Default is 'N' (No) if Enter is pressed.
    read -p "Remove existing installation and proceed? (y/N) [N]: " confirm_overwrite
    if [[ "$confirm_overwrite" =~ ^[Yy]$ ]]; then
        echo_info "Removing existing installation directory: $INSTALL_DIR"
        rm -rf "$INSTALL_DIR"
        if [ $? -ne 0 ]; then
            echo_error "Failed to remove existing installation directory $INSTALL_DIR."
            echo_error "Please check permissions or remove it manually and try again."
            exit 1
        fi
    else
        echo_info "Overwrite cancelled by user. Exiting installation."
        exit 0
    fi
fi


# --- Installation Steps ---
echo_info "Starting installation of $APP_NAME..."

# 1. Create installation directory (should be clean or non-existent now)
echo_info "Creating installation directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
if [ $? -ne 0 ]; then
    echo_error "Failed to create installation directory $INSTALL_DIR."
    exit 1
fi

# 2. Copy application script
echo_info "Copying application script '$SCRIPT_NAME' to $INSTALL_DIR/$SCRIPT_NAME"
cp "$SCRIPT_NAME" "$INSTALL_DIR/$SCRIPT_NAME"
if [ $? -ne 0 ]; then
    echo_error "Failed to copy $SCRIPT_NAME."
    exit 1
fi

# 3. Make the script executable
echo_info "Making $INSTALL_DIR/$SCRIPT_NAME executable..."
chmod +x "$INSTALL_DIR/$SCRIPT_NAME"
if [ $? -ne 0 ]; then
    echo_error "Failed to make $SCRIPT_NAME executable."
fi

# 4. Copy icon to application directory (for the Python script to use at runtime)
if [ "$icon_found_in_source" = true ]; then
    echo_info "Copying icon '$ICON_NAME' to $INSTALL_DIR/$ICON_NAME for runtime use..."
    cp "$ICON_NAME" "$INSTALL_DIR/$ICON_NAME"
    if [ $? -ne 0 ]; then
        echo_error "Failed to copy $ICON_NAME to $INSTALL_DIR. Window icon might be missing."
    else
        chmod 644 "$INSTALL_DIR/$ICON_NAME"
    fi
else
    echo_info "Skipping copying icon to $INSTALL_DIR as source icon was not found."
fi


# 5. Create symbolic link for the executable
echo_info "Creating symbolic link $EXECUTABLE_LINK_DIR/$EXECUTABLE_NAME"
# Remove existing link if it exists, to avoid 'ln: failed to create symbolic link: File exists'
# This handles overwriting the symlink cleanly.
if [ -L "$EXECUTABLE_LINK_DIR/$EXECUTABLE_NAME" ] || [ -f "$EXECUTABLE_LINK_DIR/$EXECUTABLE_NAME" ]; then
    echo_info "Removing existing link/file at $EXECUTABLE_LINK_DIR/$EXECUTABLE_NAME"
    rm -f "$EXECUTABLE_LINK_DIR/$EXECUTABLE_NAME"
fi
ln -s "$INSTALL_DIR/$SCRIPT_NAME" "$EXECUTABLE_LINK_DIR/$EXECUTABLE_NAME"
if [ $? -ne 0 ]; then
    echo_error "Failed to create symbolic link."
    echo_info "You might need to run the application directly from $INSTALL_DIR/$SCRIPT_NAME"
fi

# 6. Copy icon to system pixmaps directory (for .desktop file / menu icon)
# cp will overwrite if the file exists.
if [ "$icon_found_in_source" = true ]; then
    echo_info "Copying icon '$ICON_NAME' to $ICON_INSTALL_DIR/$INSTALLED_ICON_NAME for menu icon..."
    mkdir -p "$ICON_INSTALL_DIR" 
    cp "$ICON_NAME" "$ICON_INSTALL_DIR/$INSTALLED_ICON_NAME"
    if [ $? -ne 0 ]; then
        echo_error "Failed to copy icon to $ICON_INSTALL_DIR. The application might not have an icon in the menu."
    else
        chmod 644 "$ICON_INSTALL_DIR/$INSTALLED_ICON_NAME"
    fi
else
    echo_info "Skipping copying icon to $ICON_INSTALL_DIR as source icon was not found."
fi

# 7. Create .desktop file
# Using 'cat >' will overwrite the .desktop file if it already exists.
echo_info "Creating .desktop file: $DESKTOP_FILE_DIR/$DESKTOP_FILE_NAME"
mkdir -p "$DESKTOP_FILE_DIR" 

cat > "$DESKTOP_FILE_DIR/$DESKTOP_FILE_NAME" << EOF
[Desktop Entry]
Version=1.0
Name=$APP_NAME
GenericName=Proxy Configuration
Comment=Manage APT proxy configurations
Exec=$EXECUTABLE_NAME
Icon=$INSTALLED_ICON_NAME
Terminal=false
Type=Application
Categories=System;Settings;Network;
Keywords=proxy;apt;network;
EOF

if [ $? -ne 0 ]; then
    echo_error "Failed to create .desktop file."
else
    chmod 644 "$DESKTOP_FILE_DIR/$DESKTOP_FILE_NAME"
    echo_info "Updating desktop database (this might take a moment)..."
    if command -v update-desktop-database &> /dev/null; then
        update-desktop-database "$DESKTOP_FILE_DIR"
    else
        echo_info "Command 'update-desktop-database' not found. You might need to log out and back in for the application to appear in your menu."
    fi
fi

echo_info ""
echo_info "$APP_NAME installation complete!"
echo_info "You should now be able to find '$APP_NAME' in your application menu, or run it from the terminal using '$EXECUTABLE_NAME'."
echo_info "If the menu entry doesn't appear immediately, try logging out and back in, or restarting your desktop environment."

exit 0

