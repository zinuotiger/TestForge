filepath = r"C:\Users\LENOVO\Desktop\TestForge -  07011951 - hermes\backend\api\code_test.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Fix comprehensive-test endpoint
old = '''        # Step 2: AI ??????
        logger.info("[2/4] AI ??????...")
        from backend.generator.router import route_generation
        test_cases = await route_generation(
            req.code,
            req.language,
            req.function_name,
        )
        result.generated_test_count = len(test_cases)
        result.test_cases = [
            {"name": tc.name, "type": tc.type.value, "steps": len(tc.steps)}
            for tc in test_cases
        ]
        logger.info("?? %d ?????", len(test_cases))

        # ??????? pytest ??
        from backend.core.agent import _cases_to_pytest_code
        test_code = _cases_to_pytest_code(test_cases, req.code)

        # Step 3: ????
        logger.info("[3/4] ????...")
        from backend.executors.code_executor import execute_pytest_via_code
        result.execution = await execute_pytest_via_code(test_code, timeout=req.timeout)
        logger.info("??????: %d passed, %d failed")'''

new = '''        # Step 2: AI ??????
        logger.info("[2/4] AI ??????...")
        from backend.generator.router import route_generation
        from backend.core.agent import _cases_to_pytest_code
        test_cases = []
        try:
            test_cases = await route_generation(
                req.code,
                req.language,
                req.function_name,
            )
            result.generated_test_count = len(test_cases)
            result.test_cases = [
                {"name": tc.name, "type": tc.type.value, "steps": len(tc.steps)}
                for tc in test_cases
            ]
            logger.info("?? %d ?????", len(test_cases))
        except Exception as gen_err:
            logger.warning("AI ????: %s", gen_err)
            result.generated_test_count = 0
            result.test_cases = []
            test_cases = []

        # Step 3: ????
        if test_cases:
            logger.info("[3/4] ????...")
            from backend.executors.code_executor import execute_pytest_via_code
            test_code = _cases_to_pytest_code(test_cases, req.code)
            result.execution = await execute_pytest_via_code(test_code, timeout=req.timeout)
            logger.info("??????: %d passed, %d failed")
        else:
            result.execution = {"total": 0, "passed": 0, "failed": 0, "skipped": True, "note": "No AI configured"}
            logger.info("[3/4] ???????? AI?")'''

if old in content:
    content = content.replace(old, new)
    print("Fixed comprehensive-test!")
else:
    print("NOT FOUND")
    # Try finding idx
    idx = content.find('Step 2:')
    if idx > 0:
        print("Content at Step2:", repr(content[idx:idx+100]))

# Also fix the project-test section
old_proj = '''            # 2. ??
            test_cases = await route_generation(code, req.language, "")
            test_code = _cases_to_pytest_code(test_cases, code)
            item.generated_test_count = len(test_cases)

            # 3. ??
            item.execution = await execute_pytest_via_code(test_code, timeout=30)'''

new_proj = '''            # 2. AI ??
            test_cases = []
            try:
                test_cases = await route_generation(code, req.language, "")
                item.generated_test_count = len(test_cases)
            except Exception as gen_err:
                logger.warning("AI gen failed: %s", gen_err)
                item.generated_test_count = 0

            # 3. ??
            if test_cases:
                test_code = _cases_to_pytest_code(test_cases, code)
                item.execution = await execute_pytest_via_code(test_code, timeout=30)
            else:
                item.execution = {"total": 0, "passed": 0, "failed": 0, "skipped": True, "note": "No AI"}'''

if old_proj in content:
    content = content.replace(old_proj, new_proj)
    print("Fixed project-test!")
else:
    print("Project section not found")
    idx = content.find('test_cases = await route_generation(code')
    if idx > 0:
        print("Context:", repr(content[idx:idx+200]))

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
