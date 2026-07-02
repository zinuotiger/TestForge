"""
边界测试覆盖分析工具

这个工具分析TestForge项目中所有功能模块的边界测试覆盖情况，
识别需要补充边界测试的场景，并生成改进建议报告。
"""

import os
import re
import ast
import json
from pathlib import Path
from typing import List, Dict, Set, Tuple, Any
import inspect


class BoundaryCoverageAnalyzer:
    """边界测试覆盖分析器"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.backend_dir = self.project_root / "backend"
        self.tests_dir = self.project_root / "tests"
        
        # 边界测试关键词
        self.boundary_keywords = [
            # 通用边界关键词
            "boundary", "edge", "极限", "最大", "最小", "溢出", "overflow",
            "空", "empty", "null", "none", "零", "zero", "invalid", "无效",
            "特殊", "special", "异常", "exception", "错误", "error", "失败", "fail",
            "超时", "timeout", "并发", "concurrent", "竞争", "race",
            "安全", "security", "注入", "injection", "攻击", "attack",
            "性能", "performance", "内存", "memory", "cpu", "资源", "resource",
            "大", "large", "小", "small", "长", "long", "短", "short",
            "高", "high", "低", "low", "多", "many", "少", "few",
            "复杂", "complex", "简单", "simple", "极端", "extreme",
            "边界值", "边界情况", "边界条件", "边界测试",
            "edge case", "edge scenario", "boundary value", "boundary condition"
        ]
        
        # 功能模块映射
        self.module_categories = {
            "agent": ["agent", "核心", "core"],
            "analysis": ["analyzer", "分析", "analyze"],
            "generator": ["generator", "生成", "generate"],
            "executor": ["executor", "执行", "execute"],
            "browser": ["browser", "web", "自动化", "automation"],
            "api": ["api", "接口", "接口测试"],
            "security": ["security", "安全", "扫描", "scan"],
            "quality": ["quality", "质量", "mutation", "变异"],
            "config": ["config", "配置", "settings"],
            "self_healer": ["self_healer", "自愈", "heal"],
            "database": ["database", "db", "存储", "storage"],
            "network": ["network", "网络", "http", "api"],
            "concurrency": ["concurrency", "并发", "parallel", "多线程"],
            "integration": ["integration", "集成", "e2e", "端到端"]
        }
        
        # 边界测试类型
        self.boundary_types = {
            "输入验证": ["输入", "验证", "validation", "input"],
            "输出验证": ["输出", "结果", "output", "result"],
            "状态转换": ["状态", "转换", "state", "transition"],
            "并发处理": ["并发", "多线程", "concurrency", "parallel"],
            "异常处理": ["异常", "错误", "exception", "error"],
            "资源管理": ["资源", "内存", "cpu", "resource"],
            "安全防护": ["安全", "注入", "攻击", "security"],
            "性能边界": ["性能", "速度", "performance", "speed"],
            "网络边界": ["网络", "连接", "network", "connection"],
            "配置边界": ["配置", "环境", "config", "environment"]
        }
    
    def analyze_project_structure(self) -> Dict[str, Any]:
        """分析项目结构，识别所有功能模块"""
        print("分析项目结构...")
        
        modules = {}
        
        # 扫描backend目录
        for root, dirs, files in os.walk(self.backend_dir):
            for file in files:
                if file.endswith('.py'):
                    filepath = Path(root) / file
                    rel_path = filepath.relative_to(self.project_root)
                    
                    # 分析文件内容
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # 提取模块信息
                        module_info = self._analyze_module(filepath, content)
                        if module_info:
                            modules[str(rel_path)] = module_info
                    except Exception as e:
                        print(f"  分析文件 {filepath} 时出错: {e}")
        
        return modules
    
    def _analyze_module(self, filepath: Path, content: str) -> Dict[str, Any]:
        """分析单个模块"""
        module_info = {
            "file": str(filepath),
            "functions": [],
            "classes": [],
            "boundary_needs": [],
            "complexity": 0
        }
        
        try:
            # 解析AST
            tree = ast.parse(content)
            
            # 提取函数和类
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_info = {
                        "name": node.name,
                        "args": len(node.args.args),
                        "has_docstring": bool(ast.get_docstring(node)),
                        "lines": node.end_lineno - node.lineno if node.end_lineno else 0
                    }
                    module_info["functions"].append(func_info)
                    
                    # 分析函数是否需要边界测试
                    boundary_needs = self._analyze_function_boundary_needs(node, content)
                    if boundary_needs:
                        module_info["boundary_needs"].extend(boundary_needs)
                
                elif isinstance(node, ast.ClassDef):
                    class_info = {
                        "name": node.name,
                        "methods": [],
                        "has_docstring": bool(ast.get_docstring(node))
                    }
                    
                    # 提取类的方法
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            method_info = {
                                "name": item.name,
                                "args": len(item.args.args),
                                "has_docstring": bool(ast.get_docstring(item))
                            }
                            class_info["methods"].append(method_info)
                    
                    module_info["classes"].append(class_info)
            
            # 计算复杂度（简单行数估算）
            module_info["complexity"] = len(content.split('\n'))
            
            # 识别模块类别
            module_info["category"] = self._identify_module_category(str(filepath), content)
            
        except Exception as e:
            print(f"  解析AST时出错 {filepath}: {e}")
        
        return module_info
    
    def _analyze_function_boundary_needs(self, func_node: ast.FunctionDef, content: str) -> List[str]:
        """分析函数是否需要边界测试"""
        boundary_needs = []
        
        # 获取函数签名
        func_text = ast.get_source_segment(content, func_node)
        if not func_text:
            return boundary_needs
        
        # 分析参数
        for arg in func_node.args.args:
            arg_name = arg.arg
            
            # 检查参数类型提示
            if arg.annotation:
                type_hint = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else str(arg.annotation)
                
                # 根据类型提示推断边界测试需求
                if 'str' in type_hint.lower():
                    boundary_needs.extend([
                        "空字符串输入",
                        "超长字符串输入",
                        "Unicode字符输入",
                        "特殊字符输入"
                    ])
                elif 'int' in type_hint.lower() or 'float' in type_hint.lower():
                    boundary_needs.extend([
                        "零值输入",
                        "负值输入",
                        "极大值输入",
                        "极小值输入"
                    ])
                elif 'list' in type_hint.lower() or 'dict' in type_hint.lower():
                    boundary_needs.extend([
                        "空集合输入",
                        "单元素集合输入",
                        "超大集合输入"
                    ])
                elif 'bool' in type_hint.lower():
                    boundary_needs.extend([
                        "True/False边界"
                    ])
        
        # 分析函数体中的操作
        for node in ast.walk(func_node):
            # 检查除法操作
            if isinstance(node, ast.Div) or isinstance(node, ast.FloorDiv):
                boundary_needs.append("除零异常处理")
            
            # 检查循环
            elif isinstance(node, ast.While) or isinstance(node, ast.For):
                boundary_needs.append("循环边界条件")
            
            # 检查条件判断
            elif isinstance(node, ast.If):
                boundary_needs.append("条件边界测试")
            
            # 检查函数调用
            elif isinstance(node, ast.Call):
                # 检查是否调用外部资源
                if isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                    if func_name in ['open', 'read', 'write', 'execute', 'connect']:
                        boundary_needs.append("资源操作边界")
        
        return list(set(boundary_needs))
    
    def _identify_module_category(self, filepath: str, content: str) -> str:
        """识别模块所属类别"""
        filepath_lower = filepath.lower()
        content_lower = content.lower()
        
        for category, keywords in self.module_categories.items():
            # 检查文件路径
            if any(keyword in filepath_lower for keyword in keywords):
                return category
            
            # 检查文件内容中的关键词
            if any(keyword in content_lower for keyword in keywords):
                return category
        
        return "其他"
    
    def analyze_existing_boundary_tests(self) -> Dict[str, Any]:
        """分析现有边界测试"""
        print("分析现有边界测试...")
        
        boundary_tests = {
            "files": [],
            "test_count": 0,
            "boundary_test_count": 0,
            "coverage_by_category": {},
            "missing_areas": []
        }
        
        # 扫描测试目录
        for root, dirs, files in os.walk(self.tests_dir):
            for file in files:
                if file.endswith('.py') and file.startswith('test_'):
                    filepath = Path(root) / file
                    
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read().lower()
                        
                        # 检查是否包含边界测试关键词
                        is_boundary_test = any(keyword in content for keyword in self.boundary_keywords)
                        
                        # 统计测试函数数量
                        test_functions = re.findall(r'def test_.*?\(', content)
                        
                        # 统计边界测试函数数量
                        boundary_test_functions = 0
                        for func in re.findall(r'def (test_.*?)\(', content):
                            func_content = content[content.find(f'def {func}'):]
                            # 简单检查函数内容是否包含边界关键词
                            if any(keyword in func_content for keyword in self.boundary_keywords[:20]):
                                boundary_test_functions += 1
                        
                        test_info = {
                            "file": str(filepath.relative_to(self.project_root)),
                            "is_boundary_test": is_boundary_test,
                            "total_tests": len(test_functions),
                            "boundary_tests": boundary_test_functions,
                            "boundary_ratio": boundary_test_functions / max(len(test_functions), 1)
                        }
                        
                        boundary_tests["files"].append(test_info)
                        boundary_tests["test_count"] += len(test_functions)
                        boundary_tests["boundary_test_count"] += boundary_test_functions
                        
                    except Exception as e:
                        print(f"  分析测试文件 {filepath} 时出错: {e}")
        
        return boundary_tests
    
    def identify_missing_boundary_tests(self, modules: Dict[str, Any]) -> List[Dict[str, Any]]:
        """识别缺失的边界测试"""
        print("识别缺失的边界测试...")
        
        missing_tests = []
        
        for filepath, module_info in modules.items():
            # 跳过测试文件
            if 'test' in filepath.lower():
                continue
            
            # 检查模块是否有边界测试需求
            if module_info.get("boundary_needs"):
                missing_tests.append({
                    "module": filepath,
                    "category": module_info.get("category", "未知"),
                    "boundary_needs": module_info["boundary_needs"],
                    "complexity": module_info.get("complexity", 0),
                    "function_count": len(module_info.get("functions", [])),
                    "class_count": len(module_info.get("classes", []))
                })
        
        # 按复杂度和边界需求数量排序
        missing_tests.sort(
            key=lambda x: (x["complexity"] * len(x["boundary_needs"]), x["function_count"]),
            reverse=True
        )
        
        return missing_tests
    
    def generate_recommendations(self, modules: Dict[str, Any], 
                                boundary_tests: Dict[str, Any],
                                missing_tests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成改进建议"""
        print("生成改进建议...")
        
        recommendations = {
            "summary": {
                "total_modules": len(modules),
                "total_tests": boundary_tests.get("test_count", 0),
                "boundary_tests": boundary_tests.get("boundary_test_count", 0),
                "boundary_coverage_percentage": round(
                    boundary_tests.get("boundary_test_count", 0) / max(boundary_tests.get("test_count", 1), 1) * 100, 2
                ),
                "modules_needing_tests": len(missing_tests)
            },
            "high_priority": [],
            "medium_priority": [],
            "low_priority": [],
            "test_files_to_create": [],
            "test_files_to_enhance": []
        }
        
        # 分类优先级
        for test in missing_tests:
            priority_score = self._calculate_priority_score(test)
            
            recommendation = {
                "module": test["module"],
                "category": test["category"],
                "boundary_needs": test["boundary_needs"],
                "priority_score": priority_score,
                "test_file_suggestion": f"test_{test['category']}_boundary.py"
            }
            
            if priority_score >= 8:
                recommendations["high_priority"].append(recommendation)
            elif priority_score >= 5:
                recommendations["medium_priority"].append(recommendation)
            else:
                recommendations["low_priority"].append(recommendation)
        
        # 分析现有测试文件
        for test_file in boundary_tests.get("files", []):
            if test_file["boundary_ratio"] < 0.3:  # 边界测试比例低于30%
                recommendations["test_files_to_enhance"].append({
                    "file": test_file["file"],
                    "boundary_ratio": round(test_file["boundary_ratio"] * 100, 2),
                    "suggestion": "增加边界测试覆盖率"
                })
        
        # 建议创建的新测试文件
        categories_with_tests = set()
        for test_file in boundary_tests.get("files", []):
            if 'boundary' in test_file["file"].lower():
                categories_with_tests.add(test_file["file"].split('_')[1] if '_' in test_file["file"] else "general")
        
        for category in self.module_categories.keys():
            if category not in categories_with_tests:
                recommendations["test_files_to_create"].append({
                    "category": category,
                    "suggested_file": f"test_{category}_boundary.py",
                    "test_scenarios": self._get_test_scenarios_for_category(category)
                })
        
        return recommendations
    
    def _calculate_priority_score(self, test_info: Dict[str, Any]) -> float:
        """计算优先级分数"""
        score = 0.0
        
        # 复杂度权重
        complexity = test_info.get("complexity", 0)
        if complexity > 500:
            score += 3
        elif complexity > 200:
            score += 2
        elif complexity > 100:
            score += 1
        
        # 函数数量权重
        func_count = test_info.get("function_count", 0)
        score += min(func_count / 10, 3)  # 最多3分
        
        # 边界需求数量权重
        boundary_needs = len(test_info.get("boundary_needs", []))
        score += min(boundary_needs / 5, 3)  # 最多3分
        
        # 类别权重
        category = test_info.get("category", "")
        if category in ["agent", "security", "executor"]:
            score += 2
        elif category in ["api", "browser", "database"]:
            score += 1
        
        return min(score, 10)  # 满分10分
    
    def _get_test_scenarios_for_category(self, category: str) -> List[str]:
        """获取类别的测试场景"""
        scenarios = {
            "agent": [
                "空输入处理",
                "极大输入处理",
                "LLM调用超时",
                "工具执行失败",
                "并发执行",
                "内存使用边界",
                "迭代次数限制"
            ],
            "analysis": [
                "不支持的语言",
                "语法错误代码",
                "大文件分析",
                "混合语言代码",
                "Unicode字符处理",
                "特殊字符处理"
            ],
            "generator": [
                "AI服务不可用",
                "无效响应格式",
                "无匹配模板",
                "复杂递归函数",
                "副作用函数",
                "大代码生成"
            ],
            "executor": [
                "无限循环代码",
                "恶意代码执行",
                "内存耗尽",
                "CPU密集型",
                "导入错误",
                "语法错误",
                "除零错误",
                "并发执行"
            ],
            "browser": [
                "404页面处理",
                "页面加载超时",
                "元素不存在",
                "多个匹配元素",
                "无效选择器",
                "JavaScript错误",
                "网络错误",
                "并发会话"
            ],
            "api": [
                "超大请求体",
                "无效JSON",
                "缺少必填字段",
                "SQL注入尝试",
                "XSS攻击尝试",
                "速率限制",
                "并发请求"
            ],
            "security": [
                "恶意代码扫描",
                "安全代码验证",
                "多种攻击向量",
                "边界条件绕过"
            ],
            "quality": [
                "空代码变异",
                "无效语法变异",
                "大代码变异",
                "复杂模式识别"
            ],
            "config": [
                "空环境变量",
                "无效环境变量",
                "缺少必需变量",
                "特殊字符配置",
                "配置覆盖"
            ],
            "self_healer": [
                "空反馈处理",
                "无效反馈处理",
                "冲突反馈处理",
                "多次迭代修复"
            ],
            "integration": [
                "空工作流",
                "大型工作流",
                "错误传播",
                "端到端边界"
            ]
        }
        
        return scenarios.get(category, ["通用边界测试"])
    
    def generate_report(self, output_file: str = "boundary_coverage_report.md"):
        """生成边界测试覆盖报告"""
        print("生成边界测试覆盖报告...")
        
        # 执行分析
        modules = self.analyze_project_structure()
        boundary_tests = self.analyze_existing_boundary_tests()
        missing_tests = self.identify_missing_boundary_tests(modules)
        recommendations = self.generate_recommendations(modules, boundary_tests, missing_tests)
        
        # 生成报告
        report = self._format_report(modules, boundary_tests, missing_tests, recommendations)
        
        # 保存报告
        report_path = self.project_root / output_file
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"报告已保存到: {report_path}")
        
        # 打印摘要
        self._print_summary(recommendations)
        
        return report_path
    
    def _format_report(self, modules: Dict[str, Any], 
                      boundary_tests: Dict[str, Any],
                      missing_tests: List[Dict[str, Any]],
                      recommendations: Dict[str, Any]) -> str:
        """格式化报告"""
        report = f"""# TestForge项目边界测试覆盖分析报告

## 1. 项目概览

- **分析时间**: {self._get_current_time()}
- **项目根目录**: {self.project_root}
- **分析模块数量**: {len(modules)}
- **测试文件数量**: {len(boundary_tests.get('files', []))}
- **总测试函数**: {recommendations['summary']['total_tests']}
- **边界测试函数**: {recommendations['summary']['boundary_tests']}
- **边界测试覆盖率**: {recommendations['summary']['boundary_coverage_percentage']}%
- **需要边界测试的模块**: {recommendations['summary']['modules_needing_tests']}

## 2. 现有边界测试分析

### 2.1 边界测试文件
"""
        
        # 边界测试文件列表
        boundary_files = [f for f in boundary_tests.get('files', []) if f['is_boundary_test']]
        non_boundary_files = [f for f in boundary_tests.get('files', []) if not f['is_boundary_test']]
        
        report += f"""
**专门边界测试文件** ({len(boundary_files)}个):
"""
        for file_info in boundary_files:
            report += f"- `{file_info['file']}`: {file_info['boundary_tests']}/{file_info['total_tests']} 个边界测试 ({file_info['boundary_ratio']*100:.1f}%)\n"
        
        report += f"""
**其他测试文件** ({len(non_boundary_files)}个):
"""
        for file_info in non_boundary_files[:10]:  # 只显示前10个
            report += f"- `{file_info['file']}`: {file_info['boundary_tests']}/{file_info['total_tests']} 个边界测试 ({file_info['boundary_ratio']*100:.1f}%)\n"
        
        if len(non_boundary_files) > 10:
            report += f"- ... 还有 {len(non_boundary_files) - 10} 个文件\n"
        
        report += """
### 2.2 边界测试类型分布
"""
        
        # 分析边界测试类型
        boundary_types_count = {}
        for file_info in boundary_files:
            try:
                with open(self.project_root / file_info['file'], 'r', encoding='utf-8') as f:
                    content = f.read().lower()
                
                for boundary_type, keywords in self.boundary_types.items():
                    if any(keyword in content for keyword in keywords):
                        boundary_types_count[boundary_type] = boundary_types_count.get(boundary_type, 0) + 1
            except:
                pass
        
        for boundary_type, count in sorted(boundary_types_count.items(), key=lambda x: x[1], reverse=True):
            report += f"- **{boundary_type}**: {count} 个文件包含\n"
        
        report += """
## 3. 缺失的边界测试

### 3.1 高优先级模块（需要立即补充）
"""
        
        for rec in recommendations.get('high_priority', [])[:5]:
            report += f"""
#### `{rec['module']}`
- **类别**: {rec['category']}
- **优先级分数**: {rec['priority_score']}/10
- **边界测试需求**:
"""
            for need in rec['boundary_needs'][:5]:  # 只显示前5个
                report += f"  - {need}\n"
            if len(rec['boundary_needs']) > 5:
                report += f"  - ... 还有 {len(rec['boundary_needs']) - 5} 个需求\n"
            report += f"- **建议测试文件**: `tests/{rec['test_file_suggestion']}`\n"
        
        report += """
### 3.2 中优先级模块
"""
        
        for rec in recommendations.get('medium_priority', [])[:5]:
            report += f"- `{rec['module']}` (类别: {rec['category']}, 优先级: {rec['priority_score']}/10)\n"
        
        report += """
### 3.3 低优先级模块
"""
        
        for rec in recommendations.get('low_priority', [])[:5]:
            report += f"- `{rec['module']}` (类别: {rec['category']}, 优先级: {rec['priority_score']}/10)\n"
        
        report += """
## 4. 改进建议

### 4.1 需要创建的测试文件
"""
        
        for file_info in recommendations.get('test_files_to_create', []):
            report += f"""
#### `tests/{file_info['suggested_file']}`
- **类别**: {file_info['category']}
- **测试场景**:
"""
            for scenario in file_info['test_scenarios'][:5]:  # 只显示前5个场景
                report += f"  - {scenario}\n"
            if len(file_info['test_scenarios']) > 5:
                report += f"  - ... 还有 {len(file_info['test_scenarios']) - 5} 个场景\n"
        
        report += """
### 4.2 需要增强的测试文件
"""
        
        for file_info in recommendations.get('test_files_to_enhance', [])[:10]:
            report += f"- `{file_info['file']}`: 边界测试比例仅 {file_info['boundary_ratio']}%，{file_info['suggestion']}\n"
        
        report += """
### 4.3 实施计划

#### 第一阶段（1-2周）：高优先级边界测试
1. 为Agent核心模块创建边界测试
2. 为安全模块创建边界测试  
3. 为执行器模块创建边界测试
4. 增强现有测试文件的边界测试覆盖率

#### 第二阶段（3-4周）：中优先级边界测试
1. 为API模块创建边界测试
2. 为浏览器自动化模块创建边界测试
3. 为数据库模块创建边界测试
4. 为配置模块创建边界测试

#### 第三阶段（5-6周）：低优先级边界测试
1. 为质量模块创建边界测试
2. 为自愈模块创建边界测试
3. 为集成模块创建边界测试
4. 完善所有模块的边界测试

## 5. 具体测试用例示例

### 5.1 Agent模块边界测试
```python
class TestAgentBoundaryScenarios:
    async def test_agent_empty_source_code(self):
        \"\"\"测试空源代码输入\"\"\"
        agent = TestAgent()
        result = await agent.run("", "测试任务")
        assert "error" in result or "status" in result
    
    async def test_agent_large_source_code(self):
        \"\"\"测试极大源代码输入\"\"\"
        large_code = "# " + "x" * 1000000 + "\\ndef test():\\n    pass"
        agent = TestAgent()
        result = await agent.run(large_code, "测试任务")
        assert result is not None
    
    async def test_agent_llm_timeout(self):
        \"\"\"测试LLM调用超时\"\"\"
        with patch('backend.core.agent.TestAgent._call_llm', 
                  side_effect=TimeoutError("LLM timeout")):
            agent = TestAgent()
            result = await agent.run("def test(): pass", "测试")
            assert "error" in result or result["status"] == "timeout"
```

### 5.2 代码分析模块边界测试
```python
class TestCodeAnalysisBoundaryScenarios:
    def test_analyze_unsupported_language(self):
        \"\"\"测试不支持的语言\"\"\"
        result = analyze_code("def test(): pass", "unknown_language")
        assert "error" in result or "unsupported" in str(result).lower()
    
    def test_analyze_malformed_code(self):
        \"\"\"测试语法错误代码\"\"\"
        test_cases = [
            "def incomplete_function(",
            "if True:",
            "for i in range(10):",
        ]
        for code in test_cases:
            result = analyze_code(code, "python")
            assert result is not None
```

### 5.3 测试执行模块边界测试
```python
class TestTestExecutionBoundaryScenarios:
    async def test_execute_infinite_loop(self):
        \"\"\"测试无限循环代码\"\"\"
        infinite_code = "while True:\\n    pass"
        executor = CodeExecutor()
        result = await executor.execute(infinite_code, "python", timeout=2)
        assert result["status"] == "timeout" or result.get("error") is not None
    
    async def test_execute_malicious_code(self):
        \"\"\"测试恶意代码\"\"\"
        malicious_codes = [
            "import os; os.system('rm -rf /')",
            "__import__('os').system('cat /etc/passwd')",
        ]
        executor = CodeExecutor()
        for code in malicious_codes:
            result = await executor.execute(code, "python", timeout=5)
            assert result is not None
```

## 6. 验证方法

### 6.1 运行边界测试
```bash
# 运行所有边界测试
python tests/run_tests.py --boundary

# 运行特定模块的边界测试
python -m pytest tests/test_agent_boundary.py -v
python -m pytest tests/test_executor_boundary.py -v

# 运行新创建的边界测试
python -m pytest tests/test_all_scenarios_boundary.py -v
```

### 6.2 检查边界测试覆盖率
```bash
# 运行分析工具
python analyze_boundary_coverage.py

# 查看报告
cat boundary_coverage_report.md
```

### 6.3 持续集成
建议在CI/CD流水线中添加边界测试检查：
```yaml
- name: 运行边界测试
  run: python tests/run_tests.py --boundary

- name: 检查边界测试覆盖率
  run: python analyze_boundary_coverage.py
```

## 7. 结论

TestForge项目在边界测试方面已经有了一定的基础，但仍有很大的改进空间。通过实施本报告中的建议，可以：

1. **显著提高代码质量**：边界测试能发现隐藏的bug
2. **增强系统稳定性**：确保在各种边界条件下都能正常工作
3. **提高测试覆盖率**：覆盖更多的代码路径和场景
4. **减少生产环境问题**：提前发现和修复边界相关的问题

建议按照优先级顺序逐步实施边界测试，优先处理高风险模块，确保系统的健壮性和可靠性。
"""
        
        return report
    
    def _get_current_time(self) -> str:
        """获取当前时间"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _print_summary(self, recommendations: Dict[str, Any]):
        """打印摘要信息"""
        print("\n" + "="*80)
        print("边界测试覆盖分析摘要")
        print("="*80)
        
        summary = recommendations['summary']
        print(f"总模块数: {summary['total_modules']}")
        print(f"总测试函数: {summary['total_tests']}")
        print(f"边界测试函数: {summary['boundary_tests']}")
        print(f"边界测试覆盖率: {summary['boundary_coverage_percentage']}%")
        print(f"需要边界测试的模块: {summary['modules_needing_tests']}")
        
        print(f"\n高优先级模块: {len(recommendations['high_priority'])}个")
        print(f"中优先级模块: {len(recommendations['medium_priority'])}个")
        print(f"低优先级模块: {len(recommendations['low_priority'])}个")
        
        print(f"\n需要创建的测试文件: {len(recommendations['test_files_to_create'])}个")
        print(f"需要增强的测试文件: {len(recommendations['test_files_to_enhance'])}个")
        
        print("\n建议立即处理的高优先级模块:")
        for rec in recommendations['high_priority'][:3]:
            print(f"  - {rec['module']} (优先级: {rec['priority_score']}/10)")
        
        print("\n" + "="*80)


def main():
    """主函数"""
    project_root = os.path.dirname(os.path.abspath(__file__))
    analyzer = BoundaryCoverageAnalyzer(project_root)
    
    print("开始分析TestForge项目边界测试覆盖情况...")
    print("-" * 80)
    
    # 生成报告
    report_path = analyzer.generate_report()
    
    print(f"\n分析完成！详细报告已保存到: {report_path}")
    print("\n下一步建议:")
    print("1. 查看生成的报告了解详细情况")
    print("2. 优先处理高优先级的边界测试缺失")
    print("3. 运行新创建的边界测试文件: tests/test_all_scenarios_boundary.py")
    print("4. 使用验证脚本检查边界测试覆盖: python verify_boundary_tests.py")


if __name__ == "__main__":
    main()