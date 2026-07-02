import urllib.request, json

body = json.dumps({"folder_path": r"C:\Users\LENOVO\Desktop\TestForge -  07011951 - hermes\backend\core", "language": "python", "timeout": 60}).encode()
req = urllib.request.Request("http://localhost:9876/api/code/project-test", data=body, headers={"Content-Type": "application/json"})
try:
    resp = urllib.request.urlopen(req, timeout=30)
    data = json.loads(resp.read())
    print("Status:", data["status"])
    print("Total files:", data["total_files"])
    for f in data.get("files", []):
        s = f.get("summary", {})
        print("  ", f["filename"], ":", f["status"], "| funcs=", s.get("functions",0), "tests=", s.get("test_count",0), "rate=", s.get("pass_rate",0), "%")
except Exception as e:
    print("Error:", e)
