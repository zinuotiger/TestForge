filepath = r"C:\Users\LENOVO\Desktop\TestForge -  07011951 - hermes\backend\api\code_test.py"
with open(filepath, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find and fix the comprehensive-test section (around lines 80-120)
# Find the line with "test_cases = await route_generation(" in the comprehensive test
for i, line in enumerate(lines):
    if "route_generation(" in line and i < 120:
        # This is the comprehensive test section
        # Replace lines i-1 through i+20 with try/except wrapper
        start = i - 2  # "# Step 2" comment
        end = i + 18   # Past the execution part
        
        new_block = [
            "        # Step 2: AI \u751f\u6210\u6d4b\u8bd5\u7528\u4f8b\n",
            '        logger.info("[2/4] AI \u751f\u6210\u6d4b\u8bd5\u7528\u4f8b...")\n',
            "        from backend.generator.router import route_generation\n",
            "        from backend.core.agent import _cases_to_pytest_code\n",
            "        test_cases = []\n",
            "        try:\n",
            lines[i],   # call to route_generation
            lines[i+1], # req.code
            lines[i+2], # req.language
            lines[i+3], # req.function_name
            lines[i+4], # )
            lines[i+5], # result.generated_test_count
            lines[i+6], # result.test_cases = [
            lines[i+7], # {"name": ...
            lines[i+8], # for tc in test_cases
            lines[i+9], # ]
            '        logger.info("\u751f\u6210 %d \u4e2a\u6d4b\u8bd5\u7528\u4f8b", len(test_cases))\n',
            "        except Exception as gen_err:\n",
            '            logger.warning("AI \u751f\u6210\u5931\u8d25: %s", gen_err)\n',
            "            result.generated_test_count = 0\n",
            "            result.test_cases = []\n",
            "            test_cases = []\n",
            "\n",
            '        # Step 3: \u6267\u884c\u6d4b\u8bd5\n',
            "        if test_cases:\n",
            '            logger.info("[3/4] \u6267\u884c\u6d4b\u8bd5...")\n',
            "            from backend.executors.code_executor import execute_pytest_via_code\n",
            "            test_code = _cases_to_pytest_code(test_cases, req.code)\n",
            "            result.execution = await execute_pytest_via_code(test_code, timeout=req.timeout)\n",
            '            logger.info("\u6d4b\u8bd5\u6267\u884c\u5b8c\u6210: %d passed, %d failed",\n',
            '                         result.execution.get("passed", 0),\n',
            '                         result.execution.get("failed", 0))\n',
            "        else:\n",
            '            result.execution = {"total": 0, "passed": 0, "failed": 0, "skipped": True, "note": "\u672a\u914d\u7f6e AI API"}\n',
            '            logger.info("[3/4] \u8df3\u8fc7\u6267\u884c\uff08\u672a\u914d\u7f6e AI\uff09")\n',
        ]
        
        lines[start:end] = new_block
        print(f"Fixed comprehensive-test at line {start+1}")
        break

# Find and fix project-test section  
for i, line in enumerate(lines):
    if 'test_cases = await route_generation(code, req.language, "")' in line and i > 200:
        start = i - 1  # comment line
        end = i + 3    # past execution line
        
        new_block = [
            "            # 2. AI \u751f\u6210\n",
            "            test_cases = []\n",
            "            try:\n",
            '                test_cases = await route_generation(code, req.language, "")\n',
            "                item.generated_test_count = len(test_cases)\n",
            "            except Exception as gen_err:\n",
            '                logger.warning("AI gen failed: %s", gen_err)\n',
            "                item.generated_test_count = 0\n",
            "\n",
            "            # 3. \u6267\u884c\n",
            "            if test_cases:\n",
            "                test_code = _cases_to_pytest_code(test_cases, code)\n",
            "                item.execution = await execute_pytest_via_code(test_code, timeout=30)\n",
            "            else:\n",
            '                item.execution = {"total": 0, "passed": 0, "failed": 0, "skipped": True, "note": "\u672a\u914d\u7f6e AI"}\n',
        ]
        
        lines[start:end] = new_block
        print(f"Fixed project-test at line {start+1}")
        break

with open(filepath, "w", encoding="utf-8") as f:
    f.writelines(lines)
print("All done!")
