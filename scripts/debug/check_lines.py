with open(r"C:\Users\LENOVO\Desktop\TestForge -  07011951 - hermes\frontend\src\pages\CodeTester.tsx", "r", encoding="utf-8") as f:
    content = f.read()

lines = content.split("\n")
for i, line in enumerate(lines):
    if "???" in line:
        for j in range(i, min(i+3, len(lines))):
            print(j+1, repr(lines[j][:120]))
