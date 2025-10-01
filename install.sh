#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}
╔══════════════════════════════════════╗
║      Marzban Monitor Installer       ║
║           Automated Setup            ║
╚══════════════════════════════════════╝
${NC}"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[i]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    print_error "Please run as root: sudo bash install.sh"
    exit 1
fi

# Check system compatibility
print_info "Checking system compatibility..."

# Check OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
else
    print_error "Cannot determine OS"
    exit 1
fi

print_status "Detected OS: $OS"

# Update system and install dependencies
print_info "Updating system packages..."
apt update -y

# Check and install Python3
if ! command -v python3 &> /dev/null; then
    print_info "Installing Python3..."
    apt install -y python3
fi
print_status "Python3 is installed"

# Check and install pip3
if ! command -v pip3 &> /dev/null; then
    print_info "Installing pip3..."
    apt install -y python3-pip
fi
print_status "pip3 is installed"

# Check and install curl
if ! command -v curl &> /dev/null; then
    print_info "Installing curl..."
    apt install -y curl
fi
print_status "Curl is installed"

# Create application directory
APP_DIR="/opt/monitorMoon"
print_info "Creating application directory: $APP_DIR"
mkdir -p $APP_DIR

# Download scripts
print_info "Downloading monitor script..."
curl -sL https://raw.githubusercontent.com/SevinEW/monitorMoon/main/monitor.py -o $APP_DIR/monitor.py

print_info "Downloading requirements..."
curl -sL https://raw.githubusercontent.com/SevinEW/monitorMoon/main/requirements.txt -o $APP_DIR/requirements.txt

print_info "Downloading setup script..."
curl -sL https://raw.githubusercontent.com/SevinEW/monitorMoon/main/setup.py -o $APP_DIR/setup.py

# Make scripts executable
chmod +x $APP_DIR/monitor.py
chmod +x $APP_DIR/setup.py

# Install Python requirements
print_info "Installing Python dependencies..."
pip3 install -q python-telegram-bot paramiko psutil schedule pytz
print_status "Python dependencies installed"

# Run setup
print_info "Starting interactive setup..."
cd $APP_DIR
python3 setup.py

if [ $? -eq 0 ]; then
    print_status "Setup completed successfully"
else
    print_error "Setup failed. Please check the errors above."
    exit 1
fi

# Create systemd service
print_info "Creating system service..."
cat > /etc/systemd/system/monitorMoon.service << EOF
[Unit]
Description=Monitor Moon Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/python3 $APP_DIR/monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable monitorMoon
systemctl start monitorMoon

print_status "Service installed and started"

# Create uninstall script
cat > $APP_DIR/uninstall.sh << 'EOF'
#!/bin/bash
systemctl stop monitorMoon
systemctl disable monitorMoon
rm -f /etc/systemd/system/monitorMoon.service
systemctl daemon-reload
rm -rf /opt/monitorMoon
echo "Monitor Moon completely uninstalled"
EOF

chmod +x $APP_DIR/uninstall.sh

print_status ""
print_status "🎉 Installation completed successfully!"
print_status "📁 Application directory: $APP_DIR"
print_status "🔧 Service name: monitorMoon"
print_status "📋 Check status: systemctl status monitorMoon"
print_status "📝 View logs: journalctl -u monitorMoon -f"
print_status "🗑️ Uninstall: $APP_DIR/uninstall.sh"

echo -e "${GREEN}
╔══════════════════════════════════════╗
║        Installation Complete!        ║
║     Monitor is now running...        ║
╚══════════════════════════════════════╝
${NC}"
