import sys
import os
import traceback

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Testing backend imports...")

# 测试导入config
try:
    from backend.config import settings
    print("[OK] Successfully imported backend.config")
except Exception as e:
    print(f"[ERROR] Failed to import backend.config: {e}")
    traceback.print_exc()

# 测试导入main
try:
    from backend.main import app
    print("[OK] Successfully imported backend.main")
    
    # 测试启动
    print("\nStarting server...")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9876, log_level="info")
    
except Exception as e:
    print(f"[ERROR] Failed to import or start backend: {e}")
    traceback.print_exc()