import requests
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_api.py <path_to_audio>")
        sys.exit(1)
        
    audio_path = sys.argv[1]
    
    print("Testing GET /health...")
    try:
        health_resp = requests.get("http://localhost:8000/health")
        print(health_resp.json())
    except Exception as e:
        print(f"Failed to connect to API: {e}")
        sys.exit(1)
        
    print(f"\nTesting POST /api/v1/analyze with {audio_path}...")
    try:
        with open(audio_path, "rb") as f:
            files = {"file": f}
            analyze_resp = requests.post("http://localhost:8000/api/v1/analyze", files=files)
            
        print(f"Status Code: {analyze_resp.status_code}")
        print(analyze_resp.json())
    except Exception as e:
        print(f"Failed to analyze: {e}")

if __name__ == "__main__":
    main()
