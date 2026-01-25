import requests
import json

# 待测试的配置列表
configs = [
    {
        "name": "ModelScope (阿里云)",
        # 修正 base_url，OpenAI 兼容接口通常以 /chat/completions 结尾
        "base_url": "https://api-inference.modelscope.cn/v1/chat/completions", 
        "api_key": "ms-b3ea64d3-5c65-4146-aec9-5dddd1cb5ee7",
        # 尝试注释中的模型ID，如果不对应可能会报错
        "model": "deepseek-ai/DeepSeek-V3", 
    },
    {
        "name": "DashScope (通义千问)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "api_key": "sk-6d60ccdfae2041db8df70ec3d50fe36e",
        # 尝试注释中的模型ID
        "model": "deepseek-v3", 
    }
]

def test_config(config):
    print(f"\n--- Testing {config['name']} ---")
    print(f"URL: {config['base_url']}")
    masked_key = f"{config['api_key'][:6]}...{config['api_key'][-4:]}"
    print(f"API Key: {masked_key}")
    print(f"Model: {config['model']}")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['api_key']}"
    }

    data = {
        "model": config['model'],
        "messages": [
            {"role": "user", "content": "Hi"}
        ],
        "max_tokens": 5
    }

    try:
        response = requests.post(config['base_url'], headers=headers, json=data, timeout=15)
        
        print(f"HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                res_json = response.json()
                content = res_json['choices'][0]['message']['content']
                print(f"✅ Success! Response: {content}")
                return True
            except Exception as e:
                print(f"⚠️  Success status but parsing failed: {e}")
                print(f"Raw response: {response.text}")
                return False
        else:
            print(f"❌ Failed. Details: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Request Error: {e}")
        return False

if __name__ == "__main__":
    print("Starting connectivity tests for alternative providers...")
    for conf in configs:
        test_config(conf)

