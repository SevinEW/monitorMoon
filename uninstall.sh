#!/bin/bash

echo "🔄 Uninstalling Monitor Moon..."

# Stop and disable service
systemctl stop monitorMoon
systemctl disable monitorMoon

# Remove service file
rm -f /etc/systemd/system/monitorMoon.service
systemctl daemon-reload

# Remove application directory
rm -rf /opt/monitorMoon

echo "✅ Monitor Moon completely uninstalled!"
echo "📝 Note: Configuration and log files were removed"
