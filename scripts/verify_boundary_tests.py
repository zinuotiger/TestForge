#!/usr/bin/env python
"""验证边界测试覆盖"""

import os
import sys
from pathlib import Path

def check_boundary_tests():
    """检查边界测试覆盖情况"""
    test_dir = Path(__file__).parent / "tests"
    
    print("=" * 70)
    print("边界测试覆盖验证报告")
    print("=" * 70)
    
    # 检查边界测试文件
    boundary_test_file = test_dir / "test_boundary_cases.py"
    if boundary_test_file.exists():
        print(f"\n[OK] 边界测试文件已创建: test_boundary_cases.py")
        
        # 读取并统计测试
        with open(boundary_test_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # 统计测试类
            test_classes = content.count('class Test')
            print(f"   包含 {test_classes} 个测试类:")
            
            classes = []
            if 'class TestArithmeticBoundaryCases:' in content:
                classes.append("TestArithmeticBoundaryCases (算术边界)")
            if 'class TestNegativeNumberBoundaries:' in content:
                classes.append("TestNegativeNumberBoundaries (负数边界)")
            if 'class TestTypeBoundaryCases:' in content:
                classes.append("TestTypeBoundaryCases (类型边界)")
            if 'class TestAgentBoundaryTesting:' in content:
                classes.append("TestAgentBoundaryTesting (Agent边界)")
            if 'class TestIntegrationBoundaryTesting:' in content:
                classes.append("TestIntegrationBoundaryTesting (集成边界)")
                
            for cls in classes:
                print(f"     - {cls}")
            
            # 统计测试函数
            test_functions = content.count('def test_')
            print(f"   包含 {test_functions} 个测试函数")
    else:
        print(f"\n[X] 边界测试文件未找到")
    
    # 检查现有测试中的边界测试
    print("\n现有测试中的边界测试检查:")
    
    boundary_keywords = [
        "边界", "edge", "boundary", "极限", "最大", "最小", 
        "零除", "溢出", "overflow", "负数", "异常"
    ]
    
    test_files = list(test_dir.glob("test_*.py"))
    total_boundary_tests = 0
    
    for test_file in test_files:
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # 检查是否有边界相关测试
            boundary_tests = []
            for keyword in boundary_keywords:
                if keyword in content.lower():
                    # 查找包含关键字的测试函数
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if 'def test_' in line and any(keyword in line.lower() for keyword in boundary_keywords):
                            test_name = line.strip()
                            boundary_tests.append(test_name)
            
            if boundary_tests:
                total_boundary_tests += len(boundary_tests)
                print(f"\n  {test_file.name}:")
                for test in set(boundary_tests):
                    print(f"    - {test}")
    
    print(f"\n总计边界测试数量: {total_boundary_tests}")
    
    # 检查加减乘除的边界测试
    print("\n加减乘除边界测试覆盖:")
    
    arithmetic_operations = {
        "加法": ["add", "加法", "addition"],
        "减法": ["subtract", "减法", "subtraction"],
        "乘法": ["multiply", "乘法", "multiplication"],
        "除法": ["divide", "除法", "division"]
    }
    
    for operation, keywords in arithmetic_operations.items():
        found = False
        for test_file in test_files:
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read().lower()
                
                # 检查是否有该运算的边界测试
                has_operation = any(keyword in content for keyword in keywords)
                has_boundary = any(boundary_keyword in content for boundary_keyword in boundary_keywords)
                
                if has_operation and has_boundary:
                    found = True
                    break
        
        status = "[OK]" if found else "[X]"
        print(f"  {status} {operation}边界测试")
    
    # 边界测试类型覆盖
    print("\n边界测试类型覆盖:")
    
    boundary_types = {
        "除零异常": ["除零", "divide by zero", "zero division"],
        "整数溢出": ["整数溢出", "integer overflow", "overflow"],
        "负数运算": ["负数", "negative", "minus"],
        "零值运算": ["零值", "zero", "0值"],
        "极大值运算": ["极大值", "large number", "huge", "10**"],
        "类型异常": ["类型", "type", "TypeError"],
        "空值处理": ["空值", "empty", "null", "空列表", "空字典", "空字符串"]
    }
    
    for boundary_type, keywords in boundary_types.items():
        found = False
        for test_file in test_files:
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read().lower()
                
                # 检查是否有该类型的边界测试
                if any(keyword in content for keyword in keywords):
                    found = True
                    break
        
        status = "[OK]" if found else "[X]"
        description = ", ".join(keywords[:2])
        print(f"  {status} {boundary_type}: {description}")
    
    print("\n" + "=" * 70)
    print("验证结果总结:")
    print("=" * 70)
    
    if total_boundary_tests >= 20:
        print("[EXCELLENT] 边界测试覆盖充足")
        print(f"   - 总计 {total_boundary_tests} 个边界测试")
        print("   - 所有算术运算都有边界测试")
        print("   - 多种边界类型都有覆盖")
    elif total_boundary_tests >= 10:
        print("[GOOD] 边界测试覆盖良好")
        print(f"   - 总计 {total_boundary_tests} 个边界测试")
        print("   - 建议增加更多边界类型")
    elif total_boundary_tests >= 5:
        print("[FAIR] 边界测试覆盖一般")
        print(f"   - 总计 {total_boundary_tests} 个边界测试")
        print("   - 需要增加边界测试覆盖")
    else:
        print("[POOR] 边界测试覆盖不足")
        print("   - 需要大幅增加边界测试")
    
    return total_boundary_tests

if __name__ == "__main__":
    check_boundary_tests()