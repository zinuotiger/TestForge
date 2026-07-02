import urllib.request, json
body = json.dumps({"code": "def hello(): return 1", "language": "python", "timeout": 30}).encode()
req = urllib.request.Request("http://localhost:9876/api/code/comprehensive-test", data=body, headers={"Content-Type": "application/json"})
try:
    resp = urllib.request.urlopen(req, timeout=30)
    data = json.loads(resp.read())
    print("Status:", data["status"])
    print("Error:", data["error"])
    print("Analysis:", data.get("analysis", {}))
except Exception as e:
    print("Connection error:", e)
