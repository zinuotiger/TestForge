import urllib.request, json
body = json.dumps({"folder_path": r"C:\Users\LENOVO\Desktop\TestForge -  07011951 - hermes\backend\core", "language": "python", "timeout": 10}).encode()
req = urllib.request.Request("http://localhost:9876/api/code/project-test", data=body, headers={"Content-Type": "application/json"})
try:
    resp = urllib.request.urlopen(req, timeout=20)
    data = json.loads(resp.read())
    print("Status:", data["status"])
    print("Total files:", data["total_files"])
    print("Error:", data.get("error", "none"))
except Exception as e:
    print("Error:", e)
