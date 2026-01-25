import requests
import json

# 配置
API_KEY = "sk-e0b6c0c0fc1946bc9c8737900612b193"
BASE_URL = "https://api.deepseek.com/chat/completions"

def test_balance_requests():
    print(f"Testing DeepSeek API (using requests)...")
    print(f"URL: {BASE_URL}")
    masked_key = f"{API_KEY[:6]}...{API_KEY[-4:]}"
    print(f"API Key: {masked_key}")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": "Hi"}
        ],
        "max_tokens": 5
    }

    try:
        response = requests.post(BASE_URL, headers=headers, json=data, timeout=10)
        
        print(f"\nHTTP Status Code: {response.status_code}")
        # print(f"Response Text: {response.text}") # 打印全文可能太长，只在出错时打印

        if response.status_code == 200:
            print("\n✅ Success! API is working.")
            print(f"Response: {response.json()['choices'][0]['message']['content']}")
        elif response.status_code == 402:
            print("\n🚨 结论: 确实是余额不足 (Insufficient Balance) - 402 Payment Required。")
            print(f"Details: {response.text}")
        elif response.status_code == 401:
            print("\n🚨 结论: API Key 无效或认证失败 - 401 Unauthorized。")
            print(f"Details: {response.text}")
        else:
            print(f"\n🚨 结论: 其他错误 (Status: {response.status_code})。")
            print(f"Details: {response.text}")

    except Exception as e:
        print(f"\n❌ Request Failed: {e}")

if __name__ == "__main__":
    test_balance_requests()
