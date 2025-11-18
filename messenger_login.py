"""
Messenger登录工具 - 保存Facebook cookies
"""

import json
import time
from playwright.sync_api import sync_playwright


def save_facebook_cookies():
    """手动登录Facebook并保存cookies"""

    print("🌐 Opening Facebook login page...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # 访问Messenger
        page.goto("https://www.messenger.com/")

        print("\n" + "="*60)
        print("📝 请在浏览器中手动登录Facebook/Messenger")
        print("登录完成后，回到终端按 Enter 键继续...")
        print("="*60 + "\n")

        input("按 Enter 键继续...")

        # 等待页面加载完成
        time.sleep(2)

        # 获取所有cookies
        all_cookies = context.cookies()

        print(f"\n📊 Found {len(all_cookies)} total cookies")

        # 转换为字典格式 - 包括所有Facebook相关域名
        cookies_dict = {}
        for cookie in all_cookies:
            domain = cookie.get('domain', '')
            # 包括 facebook.com, messenger.com 及其子域名
            if 'facebook' in domain or 'messenger' in domain or 'fb' in domain:
                cookies_dict[cookie['name']] = cookie['value']
                print(f"  - {cookie['name']}: {cookie['value'][:20]}...")

        print(f"\n✅ Extracted {len(cookies_dict)} Facebook/Messenger cookies")

        # 保存到文件
        auth_data = {
            "facebook": {
                "cookies": cookies_dict
            }
        }

        with open("messenger_auth.json", 'w') as f:
            json.dump(auth_data, f, indent=2)

        print("\n✅ Cookies saved to messenger_auth.json")
        print(f"📊 Saved {len(cookies_dict)} cookies")

        # 验证登录状态
        print("\n🔍 Verifying login status...")
        page.goto("https://www.messenger.com/")
        time.sleep(3)

        if "login" not in page.url:
            print("✅ Login verified successfully!")
        else:
            print("❌ Login verification failed. Please try again.")

        browser.close()


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════╗
    ║        Messenger Cookie Saver                        ║
    ║                                                      ║
    ║  此脚本会打开浏览器，请手动登录Facebook/Messenger    ║
    ║  登录后，cookies会自动保存到 messenger_auth.json    ║
    ╚══════════════════════════════════════════════════════╝
    """)

    save_facebook_cookies()

    print("\n✅ Done! Now you can run: python messenger_scraper.py")
