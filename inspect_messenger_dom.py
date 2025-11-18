"""
Messenger DOM Inspector
Analyzes the structure of Messenger messages to find reliable sender detection methods
"""

import json
import time
from playwright.sync_api import sync_playwright

# Load cookies
try:
    with open("messenger_auth.json", 'r') as f:
        config = json.load(f)
    cookies_data = config.get('facebook', {}).get('cookies', {})
    print(f"✅ Loaded {len(cookies_data)} cookies")
except:
    cookies_data = {}
    print("⚠️  No cookies found")

with sync_playwright() as p:
    print("🚀 Launching browser...")
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    )

    # Load cookies
    if cookies_data:
        cookies_list = []
        for name, value in cookies_data.items():
            cookies_list.append({'name': name, 'value': value, 'domain': '.facebook.com', 'path': '/'})
            cookies_list.append({'name': name, 'value': value, 'domain': '.messenger.com', 'path': '/'})
        context.add_cookies(cookies_list)

    page = context.new_page()

    # Open conversation
    conversation_url = "https://messenger.com/t/3706975126099243/"
    print(f"📱 Opening: {conversation_url}")
    page.goto(conversation_url, wait_until='domcontentloaded', timeout=60000)

    time.sleep(5)

    print("\n" + "="*80)
    print("DOM STRUCTURE ANALYSIS")
    print("="*80)

    # Get all message containers
    messages = page.query_selector_all('div[dir="auto"]')
    print(f"\n✅ Found {len(messages)} messages")

    print("\n📊 Analyzing last 5 messages:\n")

    for i, msg in enumerate(messages[-5:]):
        msg_text = msg.inner_text().strip()[:50]

        print(f"\n{'─'*80}")
        print(f"Message #{i+1}: {msg_text}...")
        print(f"{'─'*80}")

        # Get parent elements to analyze structure
        parent = msg.query_selector('..')
        grandparent = parent.query_selector('..') if parent else None
        great_grandparent = grandparent.query_selector('..') if grandparent else None

        # Check various attributes
        print(f"\n🔍 Element attributes:")
        print(f"   - dir: {msg.get_attribute('dir')}")
        print(f"   - class: {msg.get_attribute('class')}")
        print(f"   - role: {msg.get_attribute('role')}")
        print(f"   - aria-label: {msg.get_attribute('aria-label')}")

        if parent:
            print(f"\n🔍 Parent attributes:")
            print(f"   - class: {parent.get_attribute('class')}")
            print(f"   - role: {parent.get_attribute('role')}")
            print(f"   - aria-label: {parent.get_attribute('aria-label')}")
            print(f"   - data-*: {[attr for attr in dir(parent) if 'data' in attr.lower()]}")

        if grandparent:
            print(f"\n🔍 Grandparent attributes:")
            print(f"   - class: {grandparent.get_attribute('class')}")
            print(f"   - role: {grandparent.get_attribute('role')}")

        # Check for "You" or alignment indicators
        # Method 1: Check parent text for "You sent"
        if parent:
            parent_text = parent.inner_text()
            has_you_marker = "You sent" in parent_text or "你发送" in parent_text
            print(f"\n📝 Contains 'You sent': {has_you_marker}")

        # Method 2: Check for alignment (right-aligned messages are typically from user)
        # This requires checking computed styles
        bounding_box = msg.bounding_box()
        if bounding_box:
            print(f"\n📐 Bounding box:")
            print(f"   - x: {bounding_box['x']}")
            print(f"   - y: {bounding_box['y']}")
            print(f"   - width: {bounding_box['width']}")

            # Get viewport width
            viewport_width = page.viewport_size['width']
            alignment_percentage = (bounding_box['x'] / viewport_width) * 100
            print(f"   - Alignment: {alignment_percentage:.1f}% from left")
            print(f"   - Likely sender: {'YOU' if alignment_percentage > 50 else 'OTHER'}")

        # Method 3: Check DOM structure - look for specific container patterns
        # Execute JavaScript to get computed styles
        js_result = page.evaluate('''(element) => {
            const styles = window.getComputedStyle(element);
            const parentStyles = element.parentElement ? window.getComputedStyle(element.parentElement) : null;
            const grandparentStyles = element.parentElement?.parentElement ?
                window.getComputedStyle(element.parentElement.parentElement) : null;

            return {
                textAlign: styles.textAlign,
                justifyContent: styles.justifyContent,
                float: styles.float,
                parentJustifyContent: parentStyles?.justifyContent,
                parentFlexDirection: parentStyles?.flexDirection,
                grandparentJustifyContent: grandparentStyles?.justifyContent,
                grandparentFlexDirection: grandparentStyles?.flexDirection,
            };
        }''', msg)

        print(f"\n💅 Computed styles:")
        for key, value in js_result.items():
            print(f"   - {key}: {value}")

    print("\n" + "="*80)
    print("🔍 Looking for container patterns...")
    print("="*80)

    # Try to find the message container that might have sender info
    all_roles = page.query_selector_all('[role]')
    print(f"\n📋 Elements with 'role' attribute: {len(all_roles)}")

    # Look for specific role patterns
    for role_elem in all_roles[-10:]:
        role = role_elem.get_attribute('role')
        aria_label = role_elem.get_attribute('aria-label')
        if aria_label and ('message' in aria_label.lower() or 'you' in aria_label.lower()):
            print(f"   - role='{role}', aria-label='{aria_label[:80]}...'")

    print("\n✅ Analysis complete. Press Ctrl+C to close browser.")
    input("\nPress Enter to close...")

    browser.close()
