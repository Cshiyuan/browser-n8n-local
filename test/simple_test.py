#!/usr/bin/env python3
"""
最简单的测试脚本 - 直接在 IDE 中点击运行
"""
import unittest
import json
import time
import requests
from typing import Optional, Dict, Any

# ============== 配置 ==============
BASE_URL = "http://localhost:8000"
AI_PROVIDER = "google"
HEADFUL = True  # 显示浏览器窗口


# ============== 工具函数 ==============

def make_request(method: str, url: str, data: Optional[Dict] = None, task_id: Optional[str] = None) -> Optional[Dict]:
    """
    统一的请求封装函数

    Args:
        method: HTTP 方法 (GET, POST, PUT, DELETE)
        url: 请求 URL
        data: 请求 Body（POST/PUT 时使用）
        task_id: 任务 ID（用于日志显示）

    Returns:
        响应的 JSON 数据，失败时返回 None
    """
    print(f"\n📤 发送请求到: {url}")

    if task_id:
        print(f"📋 任务 ID: {task_id}")

    # 打印请求 Body
    if data:
        print(f"\n📦 请求 Body:")
        print(json.dumps(data, indent=2, ensure_ascii=False))

    # 发送请求
    try:
        if method.upper() == "GET":
            response = requests.get(url)
        elif method.upper() == "POST":
            response = requests.post(url, json=data)
        elif method.upper() == "PUT":
            response = requests.put(url, json=data)
        elif method.upper() == "DELETE":
            response = requests.delete(url)
        else:
            print(f"❌ 不支持的 HTTP 方法: {method}")
            return None
    except Exception as e:
        print(f"\n❌ 请求异常: {e}")
        return None

    # 打印响应信息
    print(f"\n📥 响应状态码: {response.status_code}")
    print(f"\n📦 响应 Body:")

    try:
        response_data = response.json()
        print(json.dumps(response_data, indent=2, ensure_ascii=False))

        if response.status_code == 200:
            return response_data
        else:
            print(f"\n❌ 请求失败: {response.status_code}")
            return None
    except Exception:
        print(response.text)
        return None


def get_latest_task_id() -> Optional[str]:
    """获取最新的任务 ID"""
    try:
        with open('latest_task_id.txt', 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        print("\n❌ 未找到任务 ID，请先运行 test_run_task()")
        return None


def save_task_id(task_id: str):
    """保存任务 ID"""
    with open('latest_task_id.txt', 'w') as f:
        f.write(task_id)


# ============== 测试函数 ==============
# ============== 测试函数 ==============\n
class TestBrowserN8N(unittest.TestCase):

    def test_run_task(self):
        """创建并运行任务"""
        print("=" * 60)
        print("测试：创建任务")
        print("=" * 60)

        url = f"{BASE_URL}/api/v1/run-task"
        data = {
            "task": "访问 google.com 并搜索 'browser-use'",
            "ai_provider": AI_PROVIDER,
            "headful": HEADFUL,
            "use_vision": "auto",
            "use_custom_chrome": "False"
        }

        result = make_request("POST", url, data)

        if result:
            task_id = result.get('id')
            print(f"\n✅ 任务创建成功!")
            print(f"📋 任务 ID: {task_id}")
            print(f"📊 初始状态: {result.get('status')}")
            print(f"🔗 实时查看: {BASE_URL}{result.get('live_url')}")

            save_task_id(task_id)
            return task_id
        else:
            print(f"\n❌ 任务创建失败")
            return None


    def test_get_task_status(self):
        """查询最近任务的状态"""
        print("=" * 60)
        print("测试：查询任务状态")
        print("=" * 60)

        task_id = get_latest_task_id()
        if not task_id:
            return None

        url = f"{BASE_URL}/api/v1/task/{task_id}/status"
        result = make_request("GET", url, task_id=task_id)

        if result:
            print(f"\n✅ 查询成功!")
            print(f"📊 当前状态: {result.get('status')}")

            if result.get('result'):
                print(f"\n📄 任务结果:")
                print(result.get('result'))

            if result.get('error'):
                print(f"\n⚠️ 错误信息:")
                print(result.get('error'))

        return result


    def test_get_task_details(self):
        """获取任务完整详情"""
        print("=" * 60)
        print("测试：获取任务详情")
        print("=" * 60)

        task_id = get_latest_task_id()
        if not task_id:
            return None

        url = f"{BASE_URL}/api/v1/task/{task_id}"
        result = make_request("GET", url, task_id=task_id)

        if result:
            print(f"\n✅ 获取任务详情成功!")

        return result


    def test_stop_task(self):
        """停止正在运行的任务"""
        print("=" * 60)
        print("测试：停止任务")
        print("=" * 60)

        task_id = get_latest_task_id()
        if not task_id:
            return None

        url = f"{BASE_URL}/api/v1/stop-task/{task_id}"
        result = make_request("PUT", url, task_id=task_id)

        if result:
            print(f"\n✅ {result.get('message')}")
            return result
        else:
            print(f"\n❌ 停止失败")
            return None


    def test_complete_flow(self):
        """完整流程：创建任务 -> 等待 -> 查询状态"""
        print("=" * 60)
        print("完整流程测试")
        print("=" * 60)

        # 1. 创建任务
        task_id = self.test_run_task()

        if not task_id:
            return

        # 2. 等待几秒
        print("\n⏳ 等待 5 秒让任务开始运行...")
        time.sleep(5)

        # 3. 查询状态
        self.test_get_task_status()

        # 4. 等待更长时间
        print("\n⏳ 等待 10 秒...")
        time.sleep(10)

        # 5. 再次查询
        self.test_get_task_status()


    def test_with_custom_task(self, task_description: str):
        """使用自定义任务描述"""
        print("=" * 60)
        print(f"自定义任务测试: {task_description}")
        print("=" * 60)

        url = f"{BASE_URL}/api/v1/run-task"
        data = {
            "task": task_description,
            "ai_provider": AI_PROVIDER,
            "headful": HEADFUL,
            "use_vision": "auto"
        }

        result = make_request("POST", url, data)

        if result:
            task_id = result.get('id')
            print(f"\n✅ 任务创建成功!")
            print(f"📋 任务 ID: {task_id}")
            print(f"📊 初始状态: {result.get('status')}")
            print(f"🔗 实时查看: {BASE_URL}{result.get('live_url')}")

            save_task_id(task_id)
            return task_id
        else:
            print(f"\n❌ 任务创建失败")
            return None


