import urllib.request, json

folder = r"C:\Users\LENOVO\Desktop\TestForge -  07011951 - hermes\tests"
body = json.dumps({"folder_path": folder, "language": "python", "timeout": 60}).encode()
req = urllib.request.Request("http://localhost:9876/api/code/project-test", data=body, headers={"Content-Type": "application/json"})
try:
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    print("Status:", data["status"])
    print("Total files:", data["total_files"])
    print("Error:", data.get("error", "none"))
    for f in data.get("files", []):
        print("  ", f["filename"], f["status"], f.get("error", ""))
except Exception as e:
    print("Error:", e)
