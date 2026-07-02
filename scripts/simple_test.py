#!/usr/bin/env python3
"""简单测试脚本，避免超时限制"""

import sys
import os
sys.path.append('.')

def test_config():
    """测试配置模块"""
    try:
        from backend.config import settings
        print("[CONFIG] 配置模块导入成功")
        print(f"  应用名称: {settings.app_name}")
        print(f"  应用版本: {settings.app_version}")
        print(f"  调试模式: {settings.debug}")
        print(f"  数据库URL: {settings.database_url}")
        print(f"  LLM提供商: {settings.llm_provider}")
        return True
    except Exception as e:
        print(f"[CONFIG] 配置模块导入失败: {type(e).__name__} - {e}")
        return False

def test_dependencies():
    """测试依赖模块"""
    try:
        from backend.core.dependencies import get_config, get_execution_config
        print("[DEPS] 依赖模块导入成功")
        config = get_config()
        exec_config = get_execution_config()
        print(f"  最大工作线程: {exec_config.get('max_workers', '未设置')}")
        print(f"  总超时时间: {exec_config.get('timeout_total', '未设置')}秒")
        return True
    except Exception as e:
        print(f"[DEPS] 依赖模块导入失败: {type(e).__name__} - {e}")
        return False

def test_main_app():
    """测试主应用"""
    try:
        from backend.main import app
        print("[APP] 主应用导入成功")
        print(f"  应用标题: {app.title}")
        print(f"  路由数量: {len([r for r in app.routes])}")
        return True
    except Exception as e:
        print(f"[APP] 主应用导入失败: {type(e).__name__} - {e}")
        return False

def main():
    print("TestForge 优化验证 - 简单测试")
    print("=" * 50)
    
    results = []
    results.append(("配置模块", test_config()))
    results.append(("依赖模块", test_dependencies()))
    results.append(("主应用", test_main_app()))
    
    print("\n" + "=" * 50)
    print("测试结果汇总:")
    
    passed = 0
    for name, success in results:
        status = "PASS" if success else "FAIL"
        print(f"  {name}: {status}")
        if success:
            passed += 1
    
    print(f"\n总计: {passed}/{len(results)} 通过 ({passed/len(results)*100:.1f}%)")
    
    if passed == len(results):
        print("\n所有基础模块验证通过！")
    else:
        print("\n部分模块验证失败，请检查问题。")

if __name__ == "__main__":
    main()