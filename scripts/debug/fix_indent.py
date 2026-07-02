filepath = r"C:\Users\LENOVO\Desktop\TestForge -  07011951 - hermes\backend\api\code_test.py"
with open(filepath, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Fix the try-except indentation issue at line 99-100
for i, line in enumerate(lines):
    if i == 98:  # 0-indexed line 99
        # Should be "        try:"
        lines[i] = "        try:\n"
    elif i == 99:  # Should be indented
        lines[i] = "            test_cases = await route_generation(\n"

with open(filepath, "w", encoding="utf-8") as f:
    f.writelines(lines)
print("Fixed!")
