#!/usr/bin/env python3
"""
API测试脚本
用于验证Flask后端功能
"""

import requests
import json
import sys

BASE_URL = "http://localhost:5001"

def test_health_check():
    """测试健康检查端点"""
    print("🔍 测试健康检查...")
    try:
        response = requests.get(f"{BASE_URL}/")
        response.raise_for_status()
        data = response.json()

        if data.get('status') == 'running':
            print(f"✅ 健康检查通过")
            print(f"   服务: {data.get('service')}")
            print(f"   版本: {data.get('version')}")
            return True
        else:
            print(f"❌ 健康检查失败: {data}")
            return False
    except Exception as e:
        print(f"❌ 无法连接到服务器: {e}")
        return False

def test_conversation_suggest():
    """测试对话建议端点"""
    print("\n🔍 测试对话建议生成...")

    test_cases = [
        {
            "name": "简单问题",
            "message": "你好",
            "context": {"scenario": "general"}
        },
        {
            "name": "面试问题",
            "message": "你对我们公司有什么了解？",
            "context": {
                "scenario": "interview",
                "user_background": "5年软件开发经验",
                "conversation_goal": "获得offer"
            }
        },
        {
            "name": "社交问题",
            "message": "你平时有什么爱好？",
            "context": {"scenario": "social"}
        }
    ]

    all_passed = True

    for test in test_cases:
        print(f"\n  测试案例: {test['name']}")
        print(f"  问题: {test['message']}")

        try:
            response = requests.post(
                f"{BASE_URL}/api/conversation-suggest",
                json={
                    "message": test['message'],
                    "context": test.get('context', {})
                },
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            data = response.json()

            if data.get('success') and data.get('data'):
                suggestion = data['data']['suggestion']
                analysis = data['data'].get('analysis', 'N/A')
                confidence = data['data'].get('confidence', 0)

                print(f"  ✅ 测试通过")
                print(f"     建议: {suggestion[:100]}...")
                print(f"     分析: {analysis}")
                print(f"     可信度: {confidence}")
            else:
                print(f"  ❌ 测试失败: {data}")
                all_passed = False

        except Exception as e:
            print(f"  ❌ 请求失败: {e}")
            all_passed = False

    return all_passed

def test_scenarios():
    """测试场景列表端点"""
    print("\n🔍 测试场景列表...")
    try:
        response = requests.get(f"{BASE_URL}/api/scenarios")
        response.raise_for_status()
        data = response.json()

        if data.get('success') and data.get('data'):
            scenarios = data['data']
            print(f"✅ 场景列表获取成功")
            for scenario in scenarios:
                print(f"   - {scenario['name']}: {scenario['description']}")
            return True
        else:
            print(f"❌ 获取场景列表失败: {data}")
            return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

def test_conversation_history():
    """测试对话历史功能"""
    print("\n🔍 测试对话历史...")
    try:
        # 先清空历史
        response = requests.delete(f"{BASE_URL}/api/conversation-history")
        response.raise_for_status()
        print("  清空历史记录")

        # 发送一条测试消息
        requests.post(
            f"{BASE_URL}/api/conversation-suggest",
            json={"message": "测试历史记录"}
        )

        # 获取历史
        response = requests.get(f"{BASE_URL}/api/conversation-history")
        response.raise_for_status()
        data = response.json()

        if data.get('success') and data.get('data'):
            history = data['data']
            print(f"✅ 对话历史测试通过")
            print(f"   历史记录数量: {len(history)}")
            return True
        else:
            print(f"❌ 获取历史失败: {data}")
            return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

def test_error_handling():
    """测试错误处理"""
    print("\n🔍 测试错误处理...")

    all_passed = True

    # 测试空消息
    print("  测试空消息...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/conversation-suggest",
            json={"message": ""}
        )

        if response.status_code == 400:
            print("  ✅ 正确拒绝空消息")
        else:
            print(f"  ❌ 应该返回400，实际返回 {response.status_code}")
            all_passed = False
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
        all_passed = False

    # 测试无效JSON
    print("  测试无效请求...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/conversation-suggest",
            data="invalid json"
        )

        if response.status_code >= 400:
            print("  ✅ 正确拒绝无效请求")
        else:
            print(f"  ❌ 应该返回错误，实际返回 {response.status_code}")
            all_passed = False
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
        all_passed = False

    return all_passed

def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("🧪 Flask后端API测试套件")
    print("=" * 60)

    results = {
        "健康检查": test_health_check(),
        "对话建议生成": test_conversation_suggest(),
        "场景列表": test_scenarios(),
        "对话历史": test_conversation_history(),
        "错误处理": test_error_handling()
    }

    print("\n" + "=" * 60)
    print("📊 测试结果总结")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test_name}: {status}")

    all_passed = all(results.values())

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过！系统运行正常。")
        print("=" * 60)
        return 0
    else:
        print("⚠️  部分测试失败，请检查上述错误。")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
