import sys
sys.stdout.reconfigure(encoding='utf-8')

filepath = r"C:\Users\LENOVO\Desktop\TestForge -  07011951 - hermes\frontend\src\App.tsx"
with open(filepath, "r", encoding="utf-8", errors="replace") as f:
    content = f.read()

replacements = {
    "\u59d2\u642d\u00a7": "\u6982\u89c8",
    "\u99c3\u6428\u0033": "\ud83d\udcc8",
    "\u5a34\u5b2d\u762b": "\u6d4b\u8bd5",
    "\u99c3\u5e39": "\ud83c\udfa8",
    "\u5a34\u5b2d\u762b\u7498\u62c8\u9352\u5663?": "\u6d4b\u8bd5\u8bbe\u8ba1\u5668",
    "\u99c3\u643c": "\ud83d\udcf0",
    "\u5a34\u5b2d\u762b\u9352\u5217\u3014\u3017": "\u6d4b\u8bd5\u5217\u8868",
    "\u99c3\u6bcc": "\ud83d\udec0",
    "\u93b2\u6261\u0044\u703e\u7e3e": "\u6267\u884c\u4e2d\u5fc3",
    "\u99c3\u5bd9": "\ud83c\udf10",
    "\u7f03\u7720\u73d5\u5a34\u5b2d\u762b": "\u7f51\u7ad9\u6d4b\u8bd5",
    "\u99c3\u042a": "\ud83d\udcbb",
    "\u6d60\u7804\u721c\u5a34\u5b2d\u762b": "\u4ee3\u7801\u6d4b\u8bd5",
    "\u93c5\u9d3b\u516e": "\u667a\u80fd",
    "\u99c3": "\ud83e\udd16",
    "\u9234?": "\u23f0",
    "\u7039\u6e2d\u6630\u00b0\u56c1": "\u5b9a\u65f6\u5de1\u5bdf",
    "\u99c3\u0418": "\ud83e\udde0",
    "\u9470\u7e47\u7565\u9352?": "\u81ea\u8fdb\u5316",
    "\u9352\u253e\u00a0\u69b0": "\u5206\u6790",
    "\u99c3\u5e46": "\ud83c\udfaf",
    "\u894c\u5c75\u7426\u9352\u253e\u00a0\u69b0": "\u5f71\u54cd\u5206\u6790",
    "\u99c3\u6335": "\ud83d\udcb5",
    "Token \u9422\u7528\u5629": "Token \u7528\u91cf",
    "\u99c3\u6431": "\ud83d\udcf1",
    "\u93b2\u6cd8\u6194": "\u62a5\u544a",
    "\u7f06\u7325\u7e7a": "\u7cfb\u7edf",
    "\u923f\u6b59\u4e43\u7b0d": "\u2699\ufe0f",
    "\u7488\u5289\u7646": "\u8bbe\u7f6e",
    "\u923f\u6390\u4e43\u7b0d TestForge": "\u26a1 TestForge",
    "\u95ab\u0080\u9155\u6d53?": "\u9000\u51fa",
    "\u9421\u7676\u6b7b\u6eb6": "\u767b\u51fa",
    "\u9362\u6aac\u6d57\u4e43?..": "\u52a0\u8f7d\u4e2d...",
}

for old, new in replacements.items():
    if old in content:
        content = content.replace(old, new)
        print(f"Fixed: {repr(old)} -> {repr(new)}")
    else:
        print(f"NOT FOUND: {repr(old)}")

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Done")
