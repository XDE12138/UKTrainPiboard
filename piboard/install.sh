#!/bin/bash
# PiBoard 安装脚本（在树莓派 Zero 2W 上运行）
set -e

echo "=== PiBoard Install ==="

# 系统依赖
sudo apt update
sudo apt install -y python3-pygame python3-pip libsdl2-dev

# Python 依赖（--break-system-packages 适用于 Bookworm）
pip3 install flask flask-sock requests icalendar --break-system-packages

# GPU 内存配置（写入 /boot/firmware/config.txt，若不存在则用旧路径）
CONFIG_FILE="/boot/firmware/config.txt"
[ -f "$CONFIG_FILE" ] || CONFIG_FILE="/boot/config.txt"

if ! grep -q "vc4-kms-v3d" "$CONFIG_FILE"; then
    echo "" | sudo tee -a "$CONFIG_FILE"
    echo "# PiBoard" | sudo tee -a "$CONFIG_FILE"
    echo "dtoverlay=vc4-kms-v3d" | sudo tee -a "$CONFIG_FILE"
    echo "gpu_mem=64" | sudo tee -a "$CONFIG_FILE"
    echo "Added vc4-kms-v3d overlay to $CONFIG_FILE"
fi

# 确定安装目录
INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_FILE="/etc/systemd/system/piboard.service"

# 创建 systemd 服务
sudo bash -c "cat > $SERVICE_FILE" << EOF
[Unit]
Description=PiBoard Display System
After=network.target

[Service]
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/main.py
WorkingDirectory=${INSTALL_DIR}
Restart=always
RestartSec=5
User=pi
Environment=SDL_VIDEODRIVER=kmsdrm
Environment=SDL_AUDIODRIVER=dummy

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable piboard
echo ""
echo "=== Installation complete ==="
echo "Run: sudo systemctl start piboard"
echo "Logs: sudo journalctl -u piboard -f"
echo "Web:  http://$(hostname -I | awk '{print $1}'):5000"
