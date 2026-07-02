#!/usr/bin/env python3
"""运行验证优化的简单脚本"""

import sys
import os
sys.path.append('.')

def main():
    print('开始验证TestForge优化配置...')
    print('=' * 60)
    
    # 测试1：检查配置模块
    try:
        from backend.config import settings
        print('[OK] 配置模块导入成功')
        print('应用名称:', settings.app_name)
        print('应用版本:', settings.app_version)
        print('调试模式:', settings.debug)
        print('数据库URL:', settings.database_url)
        config_success = True
    except Exception as e:
        print('[ERROR] 配置模块导入失败:', e)
        config_success = False
    
    # 测试2：检查依赖模块
    try:
        from backend.core.dependencies import get_config, get_execution_config
        print('[OK] 依赖模块导入成功')
        config = get_config()
        exec_config = get_execution_config()
        print('最大工作线程:', exec_config.get('max_workers', '未设置'))
        deps_success = True
    except Exception as e:
        print('[ERROR] 依赖模块导入失败:', e)
        deps_success = False
    
    # 测试3：检查主应用
    try:
        from backend.main import app
        print('[OK] 主应用导入成功')
        print('应用标题:', app.title)
        routes = [r for r in app.routes]
        print('路由数量:', len(routes))
        main_success = True
    except Exception as e:
        print('[ERROR] 主应用导入失败:', e)
        main_success = False
    
    print('=' * 60)
    print('验证结果:')
    print('配置模块:', '[PASS]' if config_success else '[FAIL]')
    print('依赖模块:', '[PASS]' if deps_success else '[FAIL]')
    print('主应用:', '[PASS]' if main_success else '[FAIL]')
    
    total = 3
    passed = sum([config_success, deps_success, main_success])
    print('总计:', f'{passed}/{total} 通过 ({passed/total*100:.1f}%)')
    
    if passed == total:
        print('所有基础模块验证通过！')
        return 0
    else:
        print('部分模块验证失败，请检查问题。')
        return 1

if __name__ == '__main__':
    sys.exit(main())