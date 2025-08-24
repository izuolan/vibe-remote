#!/usr/bin/env python3
"""
Telegram Webhook 管理工具

用于管理 Telegram bot 的 webhook 配置的命令行工具。
"""

import argparse
import asyncio
import os
import sys
from typing import Optional

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import TelegramConfig
from telegram import Bot
from telegram.error import TelegramError


class WebhookManager:
    """Webhook 管理器"""

    def __init__(self, bot_token: str):
        self.bot = Bot(token=bot_token)

    async def get_webhook_info(self) -> dict:
        """获取当前 webhook 信息"""
        try:
            webhook_info = await self.bot.get_webhook_info()
            return {
                "url": webhook_info.url,
                "has_custom_certificate": webhook_info.has_custom_certificate,
                "pending_update_count": webhook_info.pending_update_count,
                "last_error_date": webhook_info.last_error_date,
                "last_error_message": webhook_info.last_error_message,
                "max_connections": webhook_info.max_connections,
                "allowed_updates": webhook_info.allowed_updates,
            }
        except TelegramError as e:
            print(f"❌ 获取 webhook 信息失败: {e}")
            return {}

    async def set_webhook(
        self,
        url: str,
        secret_token: Optional[str] = None,
        cert_path: Optional[str] = None,
        max_connections: int = 40,
    ) -> bool:
        """设置 webhook"""
        try:
            kwargs = {
                "url": url,
                "max_connections": max_connections,
            }

            if secret_token:
                kwargs["secret_token"] = secret_token

            if cert_path and os.path.exists(cert_path):
                with open(cert_path, "rb") as cert_file:
                    kwargs["certificate"] = cert_file.read()
                print(f"📄 使用证书文件: {cert_path}")

            result = await self.bot.set_webhook(**kwargs)

            if result:
                print(f"✅ Webhook 设置成功: {url}")
                return True
            else:
                print("❌ Webhook 设置失败")
                return False

        except TelegramError as e:
            print(f"❌ 设置 webhook 失败: {e}")
            return False
        except FileNotFoundError:
            print(f"❌ 证书文件不存在: {cert_path}")
            return False

    async def delete_webhook(self) -> bool:
        """删除 webhook"""
        try:
            result = await self.bot.delete_webhook()
            if result:
                print("✅ Webhook 删除成功")
                return True
            else:
                print("❌ Webhook 删除失败")
                return False
        except TelegramError as e:
            print(f"❌ 删除 webhook 失败: {e}")
            return False

    async def test_webhook(self, url: str) -> bool:
        """测试 webhook 连接"""
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                test_data = {"test": "webhook_connection"}
                async with session.post(
                    url, json=test_data, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status in [200, 404]:  # 404 也是正常的，说明端点可达
                        print(f"✅ Webhook URL 可访问: {url} (状态码: {response.status})")
                        return True
                    else:
                        print(f"⚠️  Webhook URL 响应异常: {url} (状态码: {response.status})")
                        return False
        except Exception as e:
            print(f"❌ 无法连接到 webhook URL: {url} - {e}")
            return False


def print_webhook_info(webhook_info: dict):
    """打印 webhook 信息"""
    if not webhook_info:
        print("❌ 无法获取 webhook 信息")
        return

    print("\n📋 当前 Webhook 信息:")
    print(f"  URL: {webhook_info.get('url', '未设置')}")
    print(f"  自定义证书: {'是' if webhook_info.get('has_custom_certificate') else '否'}")
    print(f"  待处理更新数: {webhook_info.get('pending_update_count', 0)}")
    print(f"  最大连接数: {webhook_info.get('max_connections', 'N/A')}")

    if webhook_info.get("last_error_date"):
        print(f"  最后错误时间: {webhook_info.get('last_error_date')}")
        print(f"  最后错误信息: {webhook_info.get('last_error_message')}")
    else:
        print("  ✅ 无错误记录")

    allowed_updates = webhook_info.get("allowed_updates")
    if allowed_updates:
        print(f"  允许的更新类型: {', '.join(allowed_updates)}")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Telegram Webhook 管理工具")
    parser.add_argument("--token", help="Bot Token (可从环境变量 TELEGRAM_BOT_TOKEN 获取)")

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 信息命令
    subparsers.add_parser("info", help="显示当前 webhook 信息")

    # 设置命令
    set_parser = subparsers.add_parser("set", help="设置 webhook")
    set_parser.add_argument("url", help="Webhook URL")
    set_parser.add_argument("--secret", help="安全令牌")
    set_parser.add_argument("--cert", help="SSL 证书文件路径")
    set_parser.add_argument("--max-connections", type=int, default=40, help="最大连接数 (默认: 40)")

    # 删除命令
    subparsers.add_parser("delete", help="删除 webhook")

    # 测试命令
    test_parser = subparsers.add_parser("test", help="测试 webhook 连接")
    test_parser.add_argument("url", help="要测试的 Webhook URL")

    # 从配置设置
    subparsers.add_parser("set-from-env", help="从环境变量设置 webhook")

    args = parser.parse_args()

    # 获取 bot token
    bot_token = args.token or os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("❌ 请提供 Bot Token (--token 参数或 TELEGRAM_BOT_TOKEN 环境变量)")
        sys.exit(1)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    manager = WebhookManager(bot_token)

    try:
        if args.command == "info":
            webhook_info = await manager.get_webhook_info()
            print_webhook_info(webhook_info)

        elif args.command == "set":
            success = await manager.set_webhook(
                url=args.url,
                secret_token=args.secret,
                cert_path=args.cert,
                max_connections=args.max_connections,
            )
            if success:
                webhook_info = await manager.get_webhook_info()
                print_webhook_info(webhook_info)

        elif args.command == "delete":
            await manager.delete_webhook()

        elif args.command == "test":
            await manager.test_webhook(args.url)

        elif args.command == "set-from-env":
            try:
                config = TelegramConfig.from_env()
                if not config.webhook_url:
                    print("❌ 环境变量中未设置 TELEGRAM_WEBHOOK_URL")
                    sys.exit(1)

                success = await manager.set_webhook(
                    url=config.webhook_url,
                    secret_token=config.webhook_secret_token,
                    cert_path=config.webhook_cert_path,
                )

                if success:
                    print("\n🔧 从环境变量设置的配置:")
                    print(f"  URL: {config.webhook_url}")
                    print(f"  端口: {config.webhook_port}")
                    print(f"  监听地址: {config.webhook_listen}")
                    if config.webhook_secret_token:
                        print(f"  安全令牌: {'*' * len(config.webhook_secret_token)}")
                    if config.webhook_cert_path:
                        print(f"  证书路径: {config.webhook_cert_path}")

                    webhook_info = await manager.get_webhook_info()
                    print_webhook_info(webhook_info)

            except ValueError as e:
                print(f"❌ 配置错误: {e}")
                sys.exit(1)

    except KeyboardInterrupt:
        print("\n⏹️  操作已取消")
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
