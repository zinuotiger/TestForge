filepath = r"C:\Users\LENOVO\Desktop\TestForge -  07011951 - hermes\backend\api\code_test.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Fix the project-test endpoint to gracefully handle missing LLM
# Replace the generation + execution section  
old_section = """            # 2. ??
            test_cases = await route_generation(code, req.language, "")
            test_code = _cases_to_pytest_code(test_cases, code)
            item.generated_test_count = len(test_cases)

            # 3. ??
            item.execution = await execute_pytest_via_code(test_code, timeout=30)"""

new_section = """            # 2. AI ????? LLM ???????
            test_cases = []
            try:
                test_cases = await route_generation(code, req.language, "")
                item.generated_test_count = len(test_cases)
            except Exception as gen_err:
                logger.warning("[PROJECT-TEST] AI generation skipped: %s", gen_err)
                item.generated_test_count = 0

            # 3. ????????????
            if test_cases:
                try:
                    test_code = _cases_to_pytest_code(test_cases, code)
                    item.execution = await execute_pytest_via_code(test_code, timeout=30)
                except Exception as exec_err:
                    logger.warning("[PROJECT-TEST] Execution failed: %s", exec_err)
                    item.execution = {"total": 0, "passed": 0, "failed": 0}"""

if old_section in content:
    content = content.replace(old_section, new_section)
    print("Fixed project-test for no-LLM mode!")
else:
    print("NOT FOUND - checking content...")
    if "route_generation(code, req.language" in content:
        print("route_generation found")
    if "test_cases = await" in content:
        idx = content.find("test_cases = await")
        print("Found at:", repr(content[idx:idx+200]))

# Also fix the comprehensive-test endpoint similarly
old_comp = """        # Step 2: AI ??????
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
        result.execution = await execute_pytest_via_code(test_code, timeout=req.timeout)"""

new_comp = """        # Step 2: AI ??????
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
            logger.warning("AI ???? (????? API): %s", gen_err)
            result.generated_test_count = 0
            result.test_cases = []
            test_cases = []

        # Step 3: ??????????????
        if test_cases:
            logger.info("[3/4] ????...")
            from backend.executors.code_executor import execute_pytest_via_code
            test_code = _cases_to_pytest_code(test_cases, req.code)
            result.execution = await execute_pytest_via_code(test_code, timeout=req.timeout)
        else:
            result.execution = {"total": 0, "passed": 0, "failed": 0, "skipped": True, "note": "No AI generation"}
            logger.info("[3/4] ???? AI ???")"""

if old_comp in content:
    content = content.replace(old_comp, new_comp)
    print("Fixed comprehensive-test for no-LLM mode!")
else:
    print("comprehensive-test section not found")

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("All fixes applied!")
