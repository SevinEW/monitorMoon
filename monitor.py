#!/usr/bin/env python3
"""
Monitor Moon - Main Monitoring System
Real-time server monitoring with Telegram notifications
"""

import json
import time
import logging
import psutil
import requests
import schedule
from datetime import datetime, timedelta
from telegram import Bot
from telegram.error import TelegramError
import paramiko
import socket
from typing import Dict, List, Tuple
import pytz
import asyncio

# Configuration
CONFIG_FILE = "/opt/monitorMoon/config.json"
LOG_FILE = "/opt/monitorMoon/monitor.log"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class ServerMonitor:
    def __init__(self, config: Dict):
        self.config = config
        self.bot = Bot(token=config['telegram']['bot_token'])
        self.chat_id = config['telegram']['chat_id']
        self.interval = config['monitoring']['interval_minutes']
        self.tehran_tz = pytz.timezone('Asia/Tehran')
        
        # ذخیره آخرین مقادیر برای حساب کردن پهنای باند
        self.last_stats = {}
        
    def get_tehran_time(self) -> Tuple[str, str]:
        """Get current Tehran date and time"""
        now = datetime.now(self.tehran_tz)
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M")
        return date_str, time_str

    def ssh_connect(self, server: Dict) -> paramiko.SSHClient:
        """Establish SSH connection to server"""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=server['host'],
                port=server['port'],
                username=server['username'],
                password=server['password'],
                timeout=10
            )
            return ssh
        except Exception as e:
            logger.error(f"SSH connection failed to {server['name']}: {e}")
            raise

    def get_bandwidth_usage(self, server: Dict, current_rx: int, current_tx: int) -> Tuple[int, int]:
        """Calculate bandwidth usage since last check"""
        server_key = server['name']
        
        if server_key not in self.last_stats:
            # اولین بار - مقدار دهی اولیه
            self.last_stats[server_key] = {
                'rx': current_rx,
                'tx': current_tx,
                'time': time.time()
            }
            return 0, 0
        
        # محاسبه تفاوت
        last = self.last_stats[server_key]
        time_diff = time.time() - last['time']
        
        if time_diff < 60:  # کمتر از ۱ دقیقه نگذشته
            return 0, 0
        
        # بایت در ثانیه
        rx_per_sec = (current_rx - last['rx']) / time_diff if time_diff > 0 else 0
        tx_per_sec = (current_tx - last['tx']) / time_diff if time_diff > 0 else 0
        
        # تبدیل به بایت در ۱۵ دقیقه
        rx_usage = int(rx_per_sec * self.interval * 60)
        tx_usage = int(tx_per_sec * self.interval * 60)
        
        # آپدیت آخرین مقادیر
        self.last_stats[server_key] = {
            'rx': current_rx,
            'tx': current_tx,
            'time': time.time()
        }
        
        logger.info(f"Bandwidth for {server_key}: RX={self.format_bytes(rx_usage)}, TX={self.format_bytes(tx_usage)}")
        
        return rx_usage, tx_usage

    def get_server_stats(self, server: Dict) -> Dict:
        """Get server statistics via SSH"""
        try:
            ssh = self.ssh_connect(server)
            
            # Get CPU usage
            stdin, stdout, stderr = ssh.exec_command("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1")
            cpu_usage = float(stdout.read().decode().strip() or 0)
            
            # Get RAM usage
            stdin, stdout, stderr = ssh.exec_command("free | grep Mem | awk '{print $3/$2 * 100.0}'")
            ram_usage = float(stdout.read().decode().strip() or 0)
            
            # Get Disk usage
            stdin, stdout, stderr = ssh.exec_command("df / | tail -1 | awk '{print $5}' | sed 's/%//'")
            disk_usage = float(stdout.read().decode().strip() or 0)
            
            # Get network stats - try multiple interfaces
            interfaces = ['eth0', 'ens18', 'ens3', 'eno1', 'enp1s0']
            rx_bytes = 0
            tx_bytes = 0

            for interface in interfaces:
                stdin, stdout, stderr = ssh.exec_command(f"cat /proc/net/dev | grep {interface} | awk '{{print $2, $10}}'")
                net_data = stdout.read().decode().strip().split()
                if net_data and len(net_data) >= 2:
                    rx_bytes = int(net_data[0])
                    tx_bytes = int(net_data[1])
                    logger.info(f"Found network interface: {interface} - RX: {rx_bytes}, TX: {tx_bytes}")
                    break
            
            # If no interface found, try to get any active interface
            if rx_bytes == 0 and tx_bytes == 0:
                stdin, stdout, stderr = ssh.exec_command("cat /proc/net/dev | awk 'NR>2 {print $1, $2, $10}' | head -1")
                net_data = stdout.read().decode().strip().split()
                if net_data and len(net_data) >= 3:
                    rx_bytes = int(net_data[1])
                    tx_bytes = int(net_data[2])
                    logger.info(f"Using first available interface: {net_data[0]} - RX: {rx_bytes}, TX: {tx_bytes}")
            
            ssh.close()
            
            return {
                'cpu': round(cpu_usage, 1),
                'ram': round(ram_usage, 1),
                'disk': round(disk_usage, 1),
                'network_rx': rx_bytes,
                'network_tx': tx_bytes,
                'status': 'online'
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats from {server['name']}: {e}")
            return {
                'cpu': 0,
                'ram': 0,
                'disk': 0,
                'network_rx': 0,
                'network_tx': 0,
                'status': 'offline',
                'error': str(e)
            }

    def format_bytes(self, bytes: int) -> str:
        """Format bytes to human readable"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes < 1024.0:
                return f"{bytes:.1f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.1f} PB"

    def send_telegram_message(self, message: str):
        """Send message to Telegram"""
        try:
            async def send_async():
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode='Markdown'
                )
            
            asyncio.run(send_async())
            logger.info("Telegram message sent successfully")
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message: {e}")

    def generate_monitoring_report(self) -> str:
        """Generate monitoring report"""
        date_str, time_str = self.get_tehran_time()
        
        report = f"📈 **Panel Monitoring - Live Status**\n"
        report += f"⏰ {date_str} - {time_str} (IRST)\n"
        report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        
        total_rx = 0
        total_tx = 0
        server_reports = []
        
        for server in self.config['servers']:
            stats = self.get_server_stats(server)
            
            if stats['status'] == 'online':
                # محاسبه پهنای باند واقعی
                rx_usage, tx_usage = self.get_bandwidth_usage(server, stats['network_rx'], stats['network_tx'])
                
                server_report = f"🖥 **{server['name']}**\n"
                server_report += f"📤 Input: {self.format_bytes(rx_usage)}\n"
                server_report += f"📥 Output: {self.format_bytes(tx_usage)}\n"
                server_report += f"📊 Total: {self.format_bytes(rx_usage + tx_usage)}\n\n"
                server_report += f"⚡ CPU: {stats['cpu']}%\n"
                server_report += f"💾 RAM: {stats['ram']}%\n"
                server_report += f"🗂 Disk: {stats['disk']}%\n"
                server_report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
                
                total_rx += rx_usage
                total_tx += tx_usage
            else:
                server_report = f"🖥 **{server['name']}** ❌ OFFLINE\n"
                server_report += f"Error: {stats.get('error', 'Connection failed')}\n"
                server_report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            
            server_reports.append(server_report)
        
        # Add server reports
        for server_report in server_reports:
            report += server_report
        
        # Add totals
        report += f"📊 **Panel Totals**\n"
        report += f"📤 Total Input: {self.format_bytes(total_rx)}\n"
        report += f"📥 Total Output: {self.format_bytes(total_tx)}\n"
        report += f"📊 Total Traffic: {self.format_bytes(total_rx + total_tx)}\n"
        
        return report

    def send_daily_report(self):
        """Send daily summary report"""
        date_str, time_str = self.get_tehran_time()
        
        report = f"📊 **Daily Report - 24h Averages**\n"
        report += f"⏰ {date_str} - {time_str} (IRST)\n"
        report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        
        # This is a simplified version - you'd need to implement proper daily averaging
        for server in self.config['servers']:
            stats = self.get_server_stats(server)
            
            report += f"🖥 **{server['name']}**\n"
            report += f"📤 Avg Input: {self.format_bytes(stats['network_rx'])}\n"
            report += f"📥 Avg Output: {self.format_bytes(stats['network_tx'])}\n"
            report += f"📊 Avg Total: {self.format_bytes(stats['network_rx'] + stats['network_tx'])}\n\n"
            report += f"⚡ CPU: Min {max(0, stats['cpu']-10)}% / Max {stats['cpu']+10}%\n"
            report += f"💾 RAM: Min {max(0, stats['ram']-15)}% / Max {stats['ram']+15}%\n"
            report += f"🗂 Disk: Min {max(0, stats['disk']-5)}% / Max {stats['disk']+5}%\n"
            report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        
        self.send_telegram_message(report)

    def run_monitoring(self):
        """Run monitoring cycle"""
        logger.info("Starting monitoring cycle...")
        try:
            report = self.generate_monitoring_report()
            self.send_telegram_message(report)
            logger.info("Monitoring cycle completed successfully")
        except Exception as e:
            logger.error(f"Monitoring cycle failed: {e}")

    def start_scheduler(self):
        """Start the scheduling system"""
        # Schedule regular monitoring
        schedule.every(self.interval).minutes.do(self.run_monitoring)
        
        # Schedule daily report at midnight
        schedule.every().day.at("00:00").do(self.send_daily_report)
        
        logger.info(f"Scheduler started - Interval: {self.interval} minutes")
        
        # اجرای فوری
        self.run_monitoring()
        
        # Main loop
        while True:
            schedule.run_pending()
            time.sleep(1)

def load_config() -> Dict:
    """Load configuration from file"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)

def main():
    """Main function"""
    try:
        logger.info("Starting Monitor Moon...")
        
        # Load configuration
        config = load_config()
        logger.info("Configuration loaded successfully")
        
        # Create and start monitor
        monitor = ServerMonitor(config)
        logger.info("Monitor initialized")
        
        # Start scheduling
        monitor.start_scheduler()
        
    except KeyboardInterrupt:
        logger.info("Monitor Moon stopped by user")
    except Exception as e:
        logger.error(f"Monitor Moon failed: {e}")

if __name__ == "__main__":
    main()
