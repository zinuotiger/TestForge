filepath = r"C:\Users\LENOVO\Desktop\TestForge -  07011951 - hermes\frontend\src\pages\CodeTester.tsx"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Fix 1: Mode button label - add project test label
old_mode_label = '"comprehensive" ? "\U0001f52c \u7efc\u5408\u6d4b\u8bd5" : m === "generate" ? "\U0001f9ec \u4ec5\u751f\u6210" : "\u26a1 \u4ec5\u6267\u884c"'
new_mode_label = '"comprehensive" ? "\U0001f52c \u7efc\u5408\u6d4b\u8bd5" : m === "generate" ? "\U0001f9ec \u4ec5\u751f\u6210" : m === "execute" ? "\u26a1 \u4ec5\u6267\u884c" : "\U0001f4c1 \u9879\u76ee\u6d4b\u8bd5"'

if old_mode_label in content:
    content = content.replace(old_mode_label, new_mode_label)
    print("Mode button label fixed!")
else:
    print("NOT FOUND: mode button label")
    # Find actual text
    idx = content.find("\u4ec5\u751f\u6210")
    if idx > 0:
        print("Found around:", repr(content[idx-50:idx+80]))

# Fix 2: Action button text - add project test text  
old_action = '"comprehensive" ? "\U0001f680 \u4e00\u952e\u6d4b\u8bd5" : mode === "generate" ? "\U0001f9ec \u751f\u6210\u6d4b\u8bd5" : "\u26a1 \u6267\u884c\u6d4b\u8bd5"'
new_action = '"comprehensive" ? "\U0001f680 \u4e00\u952e\u6d4b\u8bd5" : mode === "generate" ? "\U0001f9ec \u751f\u6210\u6d4b\u8bd5" : mode === "execute" ? "\u26a1 \u6267\u884c\u6d4b\u8bd5" : "\U0001f4c1 \u9879\u76ee\u6d4b\u8bd5"'

if old_action in content:
    content = content.replace(old_action, new_action)
    print("Action button text fixed!")
else:
    print("NOT FOUND: action button text")
    idx = content.find("\u751f\u6210\u6d4b\u8bd5")
    if idx > 0:
        print("Found around:", repr(content[idx-80:idx+80]))

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Done!")
