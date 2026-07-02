"""安全扫描（质量层）— 聚合密钥扫描 + 危险代码 + 依赖漏洞

文档第二节 L5 质量验证层安全扫描，与 safety/secret_scan.py 互补：
  - safety/secret_scan.py: 代码级密钥/危险模式检测
  - quality/security.py: 质量门禁视角的聚合安全评估
"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger("testforge")


@dataclass
class SecurityFinding:
    """安全发现项"""
    severity: str          # critical | high | medium | low | info
    category: str          # secret | dangerous_code | dependency | injection
    file: str = ""
    line: int = 0
    description: str = ""
    remediation: str = ""


# 依赖漏洞特征（简化版，实际应用 safety/pip-audit）
KNOWN_VULNERABLE = {
    "requests<2.32": "CVE-2024-35195: 代理认证泄露",
    "jinja2<3.1.4": "CVE-2024-34064: 模板注入",
    "cryptography<42.0.2": "CVE-2024-26130: NULL 指针解引用",
}


class SecurityScanner:
    """安全扫描器（质量门禁视角）"""

    # 危险代码模式（Python）
    DANGEROUS_PATTERNS = [
        (r"\beval\s*\(", "代码注入", "critical", "使用 ast.literal_eval 替代 eval"),
        (r"\bexec\s*\(", "代码注入", "critical", "避免动态执行用户输入"),
        (r"\b__import__\s*\(", "动态导入", "high", "使用 importlib 并校验模块名"),
        (r"\bos\.system\s*\(", "命令注入", "high", "使用 subprocess.run 并传参列表"),
        (r"\bsubprocess\.(call|run|Popen)\s*\(.*shell\s*=\s*True", "命令注入", "high", "设置 shell=False"),
        (r"\bpickle\.loads?\s*\(", "反序列化漏洞", "high", "使用 JSON 替代 pickle"),
        (r"\byaml\.load\s*\(", "YAML 反序列化", "high", "使用 yaml.safe_load"),
        (r"\bshell\s*=\s*True", "Shell 注入风险", "medium", "尽量使用 shell=False"),
        (r"\bassert\s+.*production", "生产环境 assert", "low", "生产环境禁用 assert"),
    ]

    def scan_code(self, code: str, filepath: str = "") -> dict:
        """扫描代码安全问题

        Returns:
            {
                "safe": bool,
                "findings": [SecurityFinding 序列化],
                "summary": {critical, high, medium, low},
                "score": float,  # 0-100，越高越安全
            }
        """
        findings: list[SecurityFinding] = []

        # 1. 危险代码模式
        for pattern, desc, severity, remediation in self.DANGEROUS_PATTERNS:
            for m in re.finditer(pattern, code):
                line = code[:m.start()].count("\n") + 1
                findings.append(SecurityFinding(
                    severity=severity,
                    category="dangerous_code",
                    file=filepath,
                    line=line,
                    description=desc,
                    remediation=remediation,
                ))

        # 2. 调用 safety/secret_scan 做密钥扫描
        try:
            from backend.safety.secret_scan import scan_all
            secret_result = scan_all(code)
            for leak in secret_result.get("secret_leaks", []):
                findings.append(SecurityFinding(
                    severity="critical",
                    category="secret",
                    file=filepath,
                    description=f"密钥泄露: {leak.get('type', 'unknown')}",
                    remediation="将密钥移到环境变量或密钥管理服务",
                ))
        except Exception as e:
            logger.warning("密钥扫描失败: %s", e)

        # 3. 计算安全评分
        summary = self._summarize(findings)
        score = self._calc_score(findings)
        safe = summary["critical"] == 0 and summary["high"] == 0

        return {
            "safe": safe,
            "findings": [self._finding_to_dict(f) for f in findings],
            "summary": summary,
            "score": score,
        }

    def scan_dependencies(self, requirements_text: str = "") -> dict:
        """扫描依赖漏洞（简化版）"""
        findings: list[SecurityFinding] = []
        for line in (requirements_text or "").splitlines():
            line = line.strip().split("#")[0].strip()
            if not line or line.startswith("-"):
                continue
            for pattern, cve in KNOWN_VULNERABLE.items():
                pkg, _, ver = line.partition("==")
                if "<" in pattern:
                    pkg_vuln, _, ver_vuln = pattern.partition("<")
                    if pkg.strip().lower() == pkg_vuln.strip().lower():
                        findings.append(SecurityFinding(
                            severity="high",
                            category="dependency",
                            description=f"{line}: {cve}",
                            remediation=f"升级到 {pkg_vuln}>={ver_vuln}",
                        ))

        summary = self._summarize(findings)
        return {
            "safe": summary["high"] == 0 and summary["critical"] == 0,
            "findings": [self._finding_to_dict(f) for f in findings],
            "summary": summary,
        }

    # ---- 内部 ----

    def _summarize(self, findings: list[SecurityFinding]) -> dict:
        return {
            "critical": sum(1 for f in findings if f.severity == "critical"),
            "high": sum(1 for f in findings if f.severity == "high"),
            "medium": sum(1 for f in findings if f.severity == "medium"),
            "low": sum(1 for f in findings if f.severity == "low"),
            "total": len(findings),
        }

    def _calc_score(self, findings: list[SecurityFinding]) -> float:
        """计算安全评分（100 满分）"""
        penalty = (
            sum(25 for _ in findings if _.severity == "critical")
            + sum(15 for _ in findings if _.severity == "high")
            + sum(5 for _ in findings if _.severity == "medium")
            + sum(1 for _ in findings if _.severity == "low")
        )
        return max(0.0, 100.0 - penalty)

    def _finding_to_dict(self, f: SecurityFinding) -> dict:
        return {
            "severity": f.severity,
            "category": f.category,
            "file": f.file,
            "line": f.line,
            "description": f.description,
            "remediation": f.remediation,
        }


# 全局单例
security_scanner = SecurityScanner()
