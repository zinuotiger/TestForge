filepath = r"C:\Users\LENOVO\Desktop\TestForge -  07011951 - hermes\backend\api\code_test.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Add debug logging at the start of project_code_test
old = "    start_total = time.time()\n    folder = os.path.abspath(req.folder_path)"
new = """    start_total = time.time()
    folder = os.path.abspath(req.folder_path)
    logger.info("[PROJECT-TEST] Received folder_path: %s", req.folder_path)
    logger.info("[PROJECT-TEST] Resolved path: %s", folder)
    logger.info("[PROJECT-TEST] Is directory: %s", os.path.isdir(folder))"""

content = content.replace(old, new)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
print("Debug logging added!")
