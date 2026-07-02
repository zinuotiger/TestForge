"""密钥/危险代码扫描"""

import re

# 危险代码模式
DANGEROUS_PATTERNS = [
    (r"\beval\s*\(", "eval() 调用"),
    (r"\bexec\s*\(", "exec() 调用"),
    (r"\bos\.system\s*\(", "os.system() 调用"),
    (r"\bsubprocess\.", "subprocess 调用"),
    (r"\brm\s+-rf\b", "rm -rf 危险命令"),
    (r"\b__import__\s*\(", "__import__() 动态导入"),
    (r"\bcompile\s*\(", "compile() 动态编译"),
]

# 密钥泄露模式
SECRET_PATTERNS = [
    (r"(?:api[_-]?key|apikey)\s*[:=]\s*['\"]?[\w-]{20,}['\"]?", "API Key"),
    (r"(?:access[_-]?token|auth[_-]?token)\s*[:=]\s*['\"]?[\w.-]{20,}['\"]?", "Access Token"),
    (r"(?:secret[_-]?key|secretkey)\s*[:=]\s*['\"]?[\w-]{20,}['\"]?", "Secret Key"),
    (r"A[K-P][A-Z0-9]{16,}", "AWS Access Key"),
    (r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----", "私钥"),
    (r"(?:password|passwd|pwd)\s*[:=]\s*['\"][^'\"]{3,}['\"]", "硬编码密码"),
]


def scan_dangerous_code(code: str) -> list[dict]:
    """扫描危险代码"""
    findings = []
    for pattern, desc in DANGEROUS_PATTERNS:
        for match in re.finditer(pattern, code, re.IGNORECASE):
            findings.append({
                "type": "dangerous_code",
                "pattern": desc,
                "line": code[:match.start()].count("\n") + 1,
                "match": match.group()[:50],
            })
    return findings


def scan_secrets(code: str) -> list[dict]:
    """扫描密钥泄露"""
    findings = []
    for pattern, desc in SECRET_PATTERNS:
        for match in re.finditer(pattern, code, re.IGNORECASE):
            findings.append({
                "type": "secret_leak",
                "pattern": desc,
                "line": code[:match.start()].count("\n") + 1,
                "match": match.group()[:30] + "...",
            })
    return findings


def scan_all(code: str) -> dict:
    """全量安全扫描"""
    dangerous = scan_dangerous_code(code)
    secrets = scan_secrets(code)

    return {
        "dangerous_code": dangerous,
        "secret_leaks": secrets,
        "total_findings": len(dangerous) + len(secrets),
        "safe": len(dangerous) == 0 and len(secrets) == 0,
    }
