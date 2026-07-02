"""搜索进化测试生成器 — EvoSuite (Java) / UTBot 封装

文档第二节 L2 测试生成层五策略之一：搜索进化。
通过 Docker 封装调用 EvoSuite，不可用时 AI 生成兜底。
"""

import asyncio
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger("testforge")


class SearchGenerator:
    """搜索进化测试生成器

    策略：
      - Java: 调用 EvoSuite (Docker 封装，锁定 Java 11 + EvoSuite 版本)
      - Python: 退化到 AI 生成 (无成熟搜索工具)
      - 不可用时: 返回空列表，由 router 兜底
    """

    # EvoSuite Docker 镜像
    EVOSUITE_IMAGE = "evosuite/evosuite:1.2.0-java11"

    async def generate(
        self,
        source_code: str,
        language: str = "java",
        class_name: str = "",
        timeout: int = 120,
    ) -> list[dict]:
        """搜索进化生成测试

        Args:
            source_code: 源代码
            language: 语言 (仅支持 java，其他语言返回空)
            class_name: 类名（Java 必须）
            timeout: 超时秒数

        Returns:
            生成的测试用例列表 [{name, code, strategy}]
        """
        if language != "java":
            logger.info("搜索生成器暂不支持 %s，跳过", language)
            return []

        if not self._check_docker_available():
            logger.warning("Docker 不可用，搜索生成器降级为空（由 AI 兜底）")
            return []

        return await self._run_evosuite(source_code, class_name, timeout)

    def _check_docker_available(self) -> bool:
        """检查 Docker 是否可用"""
        try:
            import shutil
            return shutil.which("docker") is not None
        except Exception:
            return False

    async def _run_evosuite(
        self, source_code: str, class_name: str, timeout: int
    ) -> list[dict]:
        """通过 Docker 运行 EvoSuite"""
        if not class_name:
            # 从源码推断类名
            import re
            m = re.search(r"\bclass\s+(\w+)", source_code)
            class_name = m.group(1) if m else "Generated"

        with tempfile.TemporaryDirectory(prefix="testforge_evo_") as tmpdir:
            tmp = Path(tmpdir)
            # 写入源码
            src_file = tmp / f"{class_name}.java"
            src_file.write_text(source_code, encoding="utf-8")

            cmd = [
                "docker", "run", "--rm",
                "-v", f"{tmp}:/workspace",
                "-w", "/workspace",
                self.EVOSUITE_IMAGE,
                "-generateSuite",
                "-class", class_name,
                "-projectCP", "/workspace",
            ]

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )

                if proc.returncode != 0:
                    logger.warning(
                        "EvoSuite 执行失败 (exit=%s): %s",
                        proc.returncode,
                        stderr.decode()[:500],
                    )
                    return []

                # EvoSuite 生成 <ClassName>_ESTest.java
                test_file = tmp / f"{class_name}_ESTest.java"
                if not test_file.exists():
                    logger.warning("EvoSuite 未生成测试文件")
                    return []

                test_code = test_file.read_text(encoding="utf-8")
                return [{
                    "name": f"{class_name}_ESTest",
                    "code": test_code,
                    "strategy": "search_evosuite",
                    "language": "java",
                }]

            except asyncio.TimeoutError:
                logger.warning("EvoSuite 执行超时 (%ss)", timeout)
                return []
            except Exception as e:
                logger.warning("EvoSuite 调用异常: %s", e)
                return []


# 全局单例
search_generator = SearchGenerator()
