#!/usr/bin/env python3
"""为测试文件添加pytest标记的脚本"""

import re
import os
from pathlib import Path

def add_mark_to_methods(file_path, class_name, mark_name):
    """为指定类的测试方法添加pytest标记"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找类定义
    class_pattern = rf'class {class_name}:\s*\n(?:.*?\n)*?(?=\nclass|\Z)'
    class_match = re.search(class_pattern, content, re.DOTALL | re.MULTILINE)
    
    if not class_match:
        print(f"在 {file_path} 中未找到类 {class_name}")
        return False
    
    class_content = class_match.group(0)
    
    # 查找所有测试方法（以def test_开头）
    test_method_pattern = r'(\s*)(def test_[a-zA-Z0-9_]+)'
    
    def add_mark(match):
        indent = match.group(1)
        method_def = match.group(2)
        
        # 检查是否已经有@pytest.mark
        lines_before = content[:match.start()].split('\n')
        if len(lines_before) >= 2:
            line_before = lines_before[-1]
            if '@pytest.mark.' in line_before:
                return match.group(0)  # 已经有标记，不添加
        
        # 添加标记
        return f"{indent}@{mark_name}\n{indent}{method_def}"
    
    # 只在类内容中替换
    start_idx = match.start()
    end_idx = match.end()
    before_class = content[:start_idx]
    class_content_updated = re.sub(test_method_pattern, add_mark, class_content)
    after_class = content[end_idx:]
    
    new_content = before_class + class_content_updated + after_class
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"已为 {file_path} 中的 {class_name} 类添加 {mark_name} 标记")
    return True

def main():
    """主函数"""
    test_files = [
        ("test_agent_core.py", [
            ("TestAgentCore", "pytest.mark.agent"),
            ("TestAgentToolExecution", "pytest.mark.agent"),
            ("TestAgentIntegration", "pytest.mark.agent"),
            ("TestAgentEdgeCases", "pytest.mark.agent"),
        ]),
        ("test_e2e_integration.py", [
            ("TestEndToEndPipeline", "pytest.mark.integration"),
            ("TestEndToEndPipeline", "pytest.mark.e2e"),
            ("TestMultiLanguageSupport", "pytest.mark.integration"),
            ("TestMultiLanguageSupport", "pytest.mark.e2e"),
            ("TestErrorHandlingAndRecovery", "pytest.mark.integration"),
            ("TestErrorHandlingAndRecovery", "pytest.mark.e2e"),
            ("TestPerformanceAndConcurrency", "pytest.mark.integration"),
            ("TestPerformanceAndConcurrency", "pytest.mark.e2e"),
            ("TestConfigurationIntegration", "pytest.mark.integration"),
            ("TestConfigurationIntegration", "pytest.mark.e2e"),
        ]),
        ("test_e2e_browser_agent.py", [
            ("", "pytest.mark.integration"),  # 整个文件
            ("", "pytest.mark.e2e"),
        ]),
    ]
    
    for file_name, class_marks in test_files:
        file_path = Path(__file__).parent / file_name
        if not file_path.exists():
            print(f"警告: 文件 {file_path} 不存在")
            continue
        
        for class_name, mark_name in class_marks:
            if class_name:  # 为特定类添加
                add_mark_to_methods(file_path, class_name, mark_name)
            else:  # 为整个文件添加（在文件顶部）
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # 检查是否已经有import pytest
                has_pytest_import = any('import pytest' in line for line in lines)
                has_mark = any(mark_name.replace('pytest.', '') in line for line in lines)
                
                if not has_mark:
                    # 在文件开始处添加标记
                    new_lines = []
                    for i, line in enumerate(lines):
                        new_lines.append(line)
                        if line.strip().startswith('import pytest') or (i > 0 and lines[i-1].strip().startswith('import pytest')):
                            # 在import pytest后添加标记
                            new_lines.append(f'\n{mark_name}\n')
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.writelines(new_lines)
                    
                    print(f"已为 {file_path} 添加文件级标记 {mark_name}")

if __name__ == "__main__":
    main()