"""
Webhook功能测试脚本

这个脚本用于测试Browser Use后端的webhook回调功能。
它包含两个部分:
1. Mock Webhook服务器 - 接收webhook回调
2. 测试客户端 - 发送带有webhook_url的任务请求
"""

import asyncio
import json
from datetime import datetime
from fastapi import FastAPI, Request
import uvicorn
import httpx
import threading
import time


# ============= Mock Webhook服务器 =============

webhook_app = FastAPI()
received_webhooks = []


@webhook_app.post("/webhook")
async def receive_webhook(request: Request):
    """接收webhook回调"""
    body = await request.json()
    timestamp = datetime.now().isoformat()
    
    print(f"\n{'='*60}")
    print(f"🔔 Webhook接收时间: {timestamp}")
    print(f"{'='*60}")
    print(json.dumps(body, indent=2, ensure_ascii=False))
    print(f"{'='*60}\n")
    
    received_webhooks.append({
        "timestamp": timestamp,
        "data": body
    })
    
    return {"status": "success", "message": "Webhook received"}


def run_webhook_server():
    """在后台线程运行webhook服务器"""
    uvicorn.run(webhook_app, host="127.0.0.1", port=5555, log_level="warning")


# ============= 测试客户端 =============

async def test_webhook_callback():
    """测试webhook回调功能"""
    
    # Browser Use API的基础URL
    base_url = "http://localhost:8000"
    
    # Webhook服务器URL
    webhook_url = "http://127.0.0.1:5555/webhook"
    
    print("\n" + "="*60)
    print("🧪 开始测试Webhook回调功能")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        # 1. 创建一个简单的任务,配置webhook
        print("\n📤 步骤 1: 创建带webhook配置的任务...")
        task_payload = {
            "task": "访问 https://www.baidu.com 并获取页面标题",
            "ai_provider": "openai",
            "webhook_url": webhook_url,
            "webhook_events": ["task.completed", "task.failed"]
        }
        
        try:
            response = await client.post(
                f"{base_url}/api/v1/run-task",
                json=task_payload,
                timeout=30.0
            )
            response.raise_for_status()
            task_data = response.json()
            task_id = task_data["id"]
            print(f"✅ 任务创建成功!")
            print(f"   Task ID: {task_id}")
            print(f"   Status: {task_data['status']}")
            print(f"   Live URL: {task_data['live_url']}")
        except Exception as e:
            print(f"❌ 创建任务失败: {e}")
            return
        
        # 2. 等待任务完成 (通过轮询状态)
        print(f"\n⏳ 步骤 2: 等待任务完成...")
        max_wait_time = 120  # 最多等待2分钟
        poll_interval = 3  # 每3秒轮询一次
        elapsed = 0
        
        while elapsed < max_wait_time:
            try:
                response = await client.get(
                    f"{base_url}/api/v1/task/{task_id}/status",
                    timeout=10.0
                )
                response.raise_for_status()
                status_data = response.json()
                current_status = status_data["status"]
                
                print(f"   当前状态: {current_status} (已等待 {elapsed}s)")
                
                if current_status in ["finished", "failed", "stopped"]:
                    print(f"\n✅ 任务已完成! 最终状态: {current_status}")
                    if status_data.get("result"):
                        print(f"   结果: {status_data['result'][:200]}...")
                    if status_data.get("error"):
                        print(f"   错误: {status_data['error']}")
                    break
                
            except Exception as e:
                print(f"   查询状态失败: {e}")
            
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        
        if elapsed >= max_wait_time:
            print(f"\n⚠️ 任务超时 (等待了{max_wait_time}秒)")
        
        # 3. 检查是否收到webhook回调
        print(f"\n🔍 步骤 3: 检查webhook回调...")
        await asyncio.sleep(2)  # 等待2秒确保webhook已发送
        
        if received_webhooks:
            print(f"✅ 成功接收到 {len(received_webhooks)} 个webhook回调!")
            for i, webhook in enumerate(received_webhooks):
                print(f"\n   Webhook #{i+1}:")
                print(f"   接收时间: {webhook['timestamp']}")
                print(f"   事件类型: {webhook['data'].get('event')}")
                print(f"   任务ID: {webhook['data'].get('task_id')}")
                print(f"   状态: {webhook['data'].get('status')}")
        else:
            print(f"❌ 未收到webhook回调")
        
        # 4. 获取完整任务信息
        print(f"\n📊 步骤 4: 获取完整任务信息...")
        try:
            response = await client.get(
                f"{base_url}/api/v1/task/{task_id}",
                timeout=10.0
            )
            response.raise_for_status()
            full_task = response.json()
            print(f"✅ 任务详细信息:")
            print(f"   ID: {full_task.get('id')}")
            print(f"   状态: {full_task.get('status')}")
            print(f"   创建时间: {full_task.get('created_at')}")
            print(f"   完成时间: {full_task.get('finished_at')}")
            print(f"   Webhook URL: {full_task.get('webhook_url')}")
            print(f"   Webhook Events: {full_task.get('webhook_events')}")
        except Exception as e:
            print(f"❌ 获取任务信息失败: {e}")
    
    print("\n" + "="*60)
    print("🎉 测试完成!")
    print("="*60 + "\n")


# ============= 主函数 =============

def main():
    """主函数"""
    print("\n" + "="*60)
    print("🚀 Browser Use Webhook功能测试")
    print("="*60)
    print("\n📝 测试说明:")
    print("   1. 确保Browser Use服务运行在 http://localhost:8000")
    print("   2. 确保已安装httpx依赖: pip install httpx")
    print("   3. 本脚本会启动一个Mock Webhook服务器在端口5555")
    print("   4. 然后发送测试任务并等待webhook回调")
    print("\n⏰ 启动倒计时: 3秒后开始...")
    
    for i in range(3, 0, -1):
        print(f"   {i}...")
        time.sleep(1)
    
    # 启动webhook服务器在后台线程
    print("\n🌐 启动Mock Webhook服务器 (端口5555)...")
    webhook_thread = threading.Thread(target=run_webhook_server, daemon=True)
    webhook_thread.start()
    time.sleep(2)  # 等待服务器启动
    print("✅ Webhook服务器已启动\n")
    
    # 运行测试
    try:
        asyncio.run(test_webhook_callback())
    except KeyboardInterrupt:
        print("\n\n⚠️ 测试被用户中断")
    except Exception as e:
        print(f"\n\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
