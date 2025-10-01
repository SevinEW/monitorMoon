#!/usr/bin/env python3
"""
Monitor Moon - Setup Script
Interactive configuration setup
"""

import json
import os
import sys
from typing import Dict, List
import asyncio

CONFIG_FILE = "/opt/monitorMoon/config.json"

def clear_screen():
    """Clear terminal screen"""
    os.system('clear' if os.name == 'posix' else 'cls')

def print_banner():
    """Print setup banner"""
    banner = """
╔══════════════════════════════════════╗
║           Monitor Moon               ║
║         Configuration Setup          ║
╚══════════════════════════════════════╝
"""
    print(banner)

def get_telegram_config() -> Dict:
    """Get Telegram bot configuration"""
    print("\n🔶 **Telegram Bot Configuration**")
    print("⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯")
    
    bot_token = input("1. Enter your Telegram Bot Token: ").strip()
    if not bot_token:
        print("❌ Bot token is required!")
        sys.exit(1)
    
    chat_id = input("2. Enter your Chat ID: ").strip()
    if not chat_id:
        print("❌ Chat ID is required!")
        sys.exit(1)
    
    return {
        "bot_token": bot_token,
        "chat_id": chat_id
    }

def get_server_config() -> List[Dict]:
    """Get servers configuration"""
    print("\n🔶 **Server Configuration**")
    print("⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯")
    
    servers = []
    server_count = 1
    
    while True:
        print(f"\n🖥️  **Server {server_count}**")
        name = input("   Server Name (e.g., Main Server): ").strip()
        host = input("   IP/Hostname: ").strip()
        port = input("   SSH Port (default 22): ").strip() or "22"
        username = input("   SSH Username: ").strip()
        password = input("   SSH Password: ").strip()
        
        if not all([name, host, username, password]):
            print("❌ All fields are required!")
            continue
        
        servers.append({
            "name": name,
            "host": host,
            "port": int(port),
            "username": username,
            "password": password
        })
        
        add_more = input("\nAdd another server? (y/n): ").strip().lower()
        if add_more != 'y':
            break
            
        server_count += 1
    
    return servers

def get_monitoring_config() -> Dict:
    """Get monitoring configuration"""
    print("\n🔶 **Monitoring Configuration**")
    print("⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯")
    
    interval = input("Monitoring interval in minutes (default 15): ").strip()
    interval = int(interval) if interval.isdigit() else 15
    
    return {
        "interval_minutes": interval,
        "timezone": "Asia/Tehran"
    }

def test_telegram_connection(config: Dict) -> bool:
    """Test Telegram bot connection"""
    print("\n🔷 Testing Telegram connection...")
    try:
        from telegram import Bot
        import asyncio
        
        async def send_test_message():
            bot = Bot(token=config['telegram']['bot_token'])
            await bot.send_message(
                chat_id=config['telegram']['chat_id'],
                text="✅ **Monitor Moon Test**\n\nTest message from Monitor Moon setup!\n\nConfiguration completed successfully! 🚀"
            )
        
        asyncio.run(send_test_message())
        print("✅ Telegram connection successful!")
        return True
    except Exception as e:
        print(f"❌ Telegram connection failed: {e}")
        return False

def save_config(config: Dict):
    """Save configuration to file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        print(f"\n✅ Configuration saved to: {CONFIG_FILE}")
    except Exception as e:
        print(f"❌ Failed to save configuration: {e}")
        sys.exit(1)

def main():
    """Main setup function"""
    clear_screen()
    print_banner()
    
    print("Welcome to Monitor Moon setup! Please provide the following information:\n")
    
    # Get all configurations
    telegram_config = get_telegram_config()
    servers_config = get_server_config()
    monitoring_config = get_monitoring_config()
    
    # Build complete config
    config = {
        "telegram": telegram_config,
        "servers": servers_config,
        "monitoring": monitoring_config
    }
    
    # Display summary
    print("\n📋 **Configuration Summary**")
    print("⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯")
    print(f"🤖 Bot Token: {telegram_config['bot_token'][:10]}...")
    print(f"💬 Chat ID: {telegram_config['chat_id']}")
    print(f"🖥️  Servers: {len(servers_config)} server(s)")
    print(f"⏰ Interval: {monitoring_config['interval_minutes']} minutes")
    
    # Confirm
    confirm = input("\nProceed with this configuration? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Setup cancelled!")
        sys.exit(0)
    
    # Save config
    save_config(config)
    
    # Test Telegram
    if test_telegram_connection(config):
        print("\n🎉 **Setup completed successfully!**")
        print("🚀 Monitor Moon is now ready to run!")
        print("\n📋 Next steps:")
        print("   • Service will start automatically")
        print("   • Check status: systemctl status monitorMoon")
        print("   • View logs: journalctl -u monitorMoon -f")
    else:
        print("\n⚠️  Setup completed with Telegram connection issues!")
        print("Please check your bot token and chat ID.")

if __name__ == "__main__":
    main()
