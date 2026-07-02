#!/usr/bin/env python3
"""测试运行脚本 - 运行特定测试套件"""

import sys
import os
import subprocess
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_pytest(test_paths, markers=None, verbose=False, coverage=False):
    """运行pytest测试"""
    cmd = [sys.executable, "-m", "pytest"]
    
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend(["--cov=backend", "--cov-report=term", "--cov-report=html"])
    
    if markers:
        for marker in markers:
            cmd.extend(["-m", marker])
    
    cmd.extend(test_paths)
    
    print(f"运行命令: {' '.join(cmd)}")
    print("=" * 70)
    
    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode


def run_agent_tests():
    """运行Agent相关测试"""
    print("运行Agent系统测试...")
    print("=" * 70)
    
    test_files = [
        "tests/test_agent_core.py",
        "tests/test_advanced.py::TestAgent"
    ]
    
    return run_pytest(test_files, markers=["agent"], verbose=True)


def run_integration_tests():
    """运行集成测试"""
    print("运行集成测试...")
    print("=" * 70)
    
    test_files = [
        "tests/test_e2e_integration.py",
        "tests/test_e2e_browser_agent.py"
    ]
    
    return run_pytest(test_files, markers=["integration", "e2e"], verbose=True)


def run_boundary_tests():
    """运行边界测试"""
    print("运行边界测试...")
    print("=" * 70)
    
    test_files = [
        "tests/test_boundary_cases.py",
        "tests/test_advanced_boundary_cases.py"
    ]
    
    return run_pytest(test_files, verbose=True)


def run_all_tests():
    """运行所有测试"""
    print("运行所有测试...")
    print("=" * 70)
    
    test_dirs = [
        "tests/",
    ]
    
    return run_pytest(test_dirs, verbose=True, coverage=True)


def run_specific_module(module_name):
    """运行特定模块测试"""
    print(f"运行模块测试: {module_name}")
    print("=" * 70)
    
    test_path = f"tests/test_{module_name}.py"
    if not os.path.exists(test_path):
        test_path = f"tests/{module_name}/"
        if not os.path.exists(test_path):
            print(f"错误: 找不到测试模块 {module_name}")
            return 1
    
    return run_pytest([test_path], verbose=True)


def main():
    parser = argparse.ArgumentParser(description="运行TestForge测试")
    parser.add_argument(
        "--agent",
        action="store_true",
        help="运行Agent系统测试"
    )
    parser.add_argument(
        "--integration",
        action="store_true",
        help="运行集成测试"
    )
    parser.add_argument(
        "--boundary",
        action="store_true",
        help="运行边界测试"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="运行所有测试（包含覆盖率）"
    )
    parser.add_argument(
        "--module",
        type=str,
        help="运行特定模块测试（如: analyzer, executor, generator）"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有测试文件"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="详细输出"
    )
    
    args = parser.parse_args()
    
    # 列出测试文件
    if args.list:
        print("测试文件列表:")
        print("=" * 70)
        for root, dirs, files in os.walk("tests"):
            for file in files:
                if file.endswith(".py") and file.startswith("test_"):
                    rel_path = os.path.join(root, file)
                    print(f"  {rel_path}")
        return 0
    
    # 运行测试
    if args.agent:
        return run_agent_tests()
    elif args.integration:
        return run_integration_tests()
    elif args.boundary:
        return run_boundary_tests()
    elif args.module:
        return run_specific_module(args.module)
    elif args.all:
        return run_all_tests()
    else:
        # 默认运行Agent和集成测试
        print("默认运行Agent和集成测试...")
        print("=" * 70)
        
        agent_result = run_agent_tests()
        if agent_result != 0:
            return agent_result
        
        print("\n" + "=" * 70)
        integration_result = run_integration_tests()
        return integration_result


if __name__ == "__main__":
    # 确保在项目根目录运行
    os.chdir(project_root)
    
    # 设置环境变量
    os.environ['PYTHONPATH'] = str(project_root)
    os.environ['TEST_MODE'] = 'true'
    
    sys.exit(main())