#!/usr/bin/env python3
"""快速启动验证优化程序 - 只运行前两个测试"""

import sys
import os
sys.path.append('.')

def test_config_module():
    """测试配置模块"""
    print("=" * 60)
    print("测试配置模块")
    print("=" * 60)
    
    from backend.config import settings
    
    print(f"1. 应用配置:")
    print(f"   - 名称: {settings.app_name}")
    print(f"   - 版本: {settings.app_version}")
    print(f"   - 调试模式: {settings.debug}")
    print(f"   - 生产环境: {settings.is_production}")
    
    print(f"\n2. 安全配置:")
    print(f"   - CORS来源: {settings.cors_origin_list}")
    print(f"   - 数据库URL: {settings.database_url}")
    print(f"   - SMTP配置: {settings.is_smtp_configured}")
    print(f"   - LLM配置: {settings.is_llm_configured}")
    
    print(f"\n3. 执行配置:")
    exec_config = settings.get_execution_config()
    print(f"   - 最大工作线程: {exec_config['max_workers']}")
    print(f"   - HTTP并发数: {exec_config['http_test_max_concurrency']}")
    print(f"   - HTTP超时: {exec_config['http_test_timeout']}s")
    
    return True

def main():
    print("TestForge 优化验证 - 快速启动")
    print("=" * 60)
    
    try:
        success = test_config_module()
        if success:
            print("\n[OK] 配置模块测试通过！")
            print("\n验证程序可以正常运行。")
            print("要运行完整验证，请执行: python 验证优化.py")
        else:
            print("\n[ERROR] 配置模块测试失败")
    except Exception as e:
        print(f"\n[ERROR] 启动失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())