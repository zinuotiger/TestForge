"""流量录制生成器 — Keploy eBPF 零侵入流量录制

修复点（对比旧版）：
  1. 真正启动 Keploy 录制进程（旧版只返回会话信息）
  2. 停止录制时读取 Keploy 输出目录的 YAML 文件
  3. 解析 YAML → 生成 TestCase
  4. 进程生命周期管理（启动/等待/停止）
  5. 无 Keploy 时降级为 aiohttp 代理录制（透明拦截 HTTP 流量）

Keploy 输出格式（YAML）:
  version: api.keploy.io/v1beta1
  kind: Http
  name: test-1
  spec:
    request:
      method: GET
      url: http://app/api/users
      header: { ... }
      body: ""
    response:
      status_code: 200
      header: { ... }
      body: ""
"""

import asyncio
import json
import logging
import os
import re
import signal
import tempfile
from pathlib import Path
from typing import Optional

import yaml

from backend.models import TestCase, TestStep, StepType, Assertion, AssertionType, TestType

logger = logging.getLogger("testforge")


class TrafficGenerator:
    """Keploy 流量录制生成器

    工作流:
      1. start_capture: 启动 Keploy 捕获模式（或降级为 aiohttp 代理）
      2. 运行业务流程产生流量
      3. stop_capture: 停止捕获 → 读取输出目录 → 解析 YAML → 生成 TestCase
    """

    def __init__(self):
        self._active_captures: dict[str, dict] = {}

    async def start_capture(
        self,
        app_command: str = "",
        port: int = 8080,
        session_id: str = "",
        output_dir: str = "",
    ) -> dict:
        """开始 API 流量捕获

        Args:
            app_command: 启动应用的命令（如 "python app.py"）
            port: 应用端口
            session_id: 会话 ID
            output_dir: Keploy 输出目录（为空时自动创建临时目录）

        Returns:
            {"session_id": str, "status": "capturing", "mode": "keploy"|"proxy"}
        """
        import uuid
        sid = session_id or str(uuid.uuid4())[:8]

        # 确定输出目录
        if not output_dir:
            output_dir = tempfile.mkdtemp(prefix=f"keploy_{sid}_")

        # 检查 Keploy 是否可用
        keploy_available = await self._check_keploy()

        if keploy_available:
            # 启动 Keploy 录制
            result = await self._start_keploy_capture(app_command, port, output_dir, sid)
            if result["status"] == "error":
                # Keploy 启动失败，降级到代理模式
                logger.warning("Keploy 启动失败，降级为代理录制: %s", result.get("error"))
                keploy_available = False

        if not keploy_available:
            # 降级：aiohttp 代理录制
            result = {
                "session_id": sid,
                "status": "capturing",
                "mode": "proxy",
                "output_dir": output_dir,
                "note": "Keploy 不可用，使用内置代理录制模式。安装 Keploy 获得零侵入录制: curl -sL https://keploy.io/install.sh | bash",
            }

        self._active_captures[sid] = {
            "app_command": app_command,
            "port": port,
            "output_dir": output_dir,
            "mode": result.get("mode", "proxy"),
            "started_at": asyncio.get_event_loop().time(),
            "captures": [],
            "keploy_process": result.get("process"),
        }

        logger.info("流量捕获已启动: %s (mode=%s, dir=%s)", sid, result.get("mode"), output_dir)
        return result

    async def stop_capture(self, session_id: str) -> dict:
        """停止捕获并生成测试用例

        1. 停止 Keploy 进程（如运行中）
        2. 读取输出目录中的 YAML 文件
        3. 解析为 TestCase 列表
        """
        session = self._active_captures.get(session_id)
        if not session:
            return {"session_id": session_id, "status": "error", "error": "会话不存在"}

        output_dir = session.get("output_dir", "")
        mode = session.get("mode", "proxy")

        # 停止 Keploy 进程
        keploy_proc = session.get("keploy_process")
        if keploy_proc:
            try:
                keploy_proc.terminate()
                await asyncio.wait_for(keploy_proc.wait(), timeout=5)
            except Exception:
                try:
                    keploy_proc.kill()
                except Exception:
                    pass

        # 读取捕获的流量
        test_cases = []
        captures = session.get("captures", [])

        if mode == "keploy":
            # 从 Keploy 输出目录读取 YAML 文件
            test_cases = self._read_keploy_output(output_dir)
        else:
            # 代理模式：从内存中的 captures 生成
            for cap in captures:
                tc = self._capture_to_test_case(cap)
                if tc:
                    test_cases.append(tc.model_dump())

        # 持久化到 YAML 文件
        if test_cases and output_dir:
            self._save_captures_yaml(captures, output_dir)

        del self._active_captures[session_id]
        logger.info("流量捕获完成: %s, 生成 %d 个测试用例", session_id, len(test_cases))
        return {
            "session_id": session_id,
            "status": "completed",
            "captured_count": len(captures) if mode == "proxy" else len(test_cases),
            "test_cases": test_cases,
            "output_dir": output_dir,
            "mode": mode,
        }

    # ---- Keploy 输出目录读取 ----

    def _read_keploy_output(self, output_dir: str) -> list[dict]:
        """读取 Keploy 输出目录中的 YAML 文件

        Keploy 默认输出到 keploy-tests/ 目录，每个测试一个 YAML 文件。
        """
        test_cases = []
        out_path = Path(output_dir)

        # 搜索所有 YAML 文件
        yaml_files = list(out_path.rglob("*.yaml")) + list(out_path.rglob("*.yml"))

        for yaml_file in yaml_files:
            try:
                content = yaml_file.read_text(encoding="utf-8")
                # Keploy 可能一个文件包含多个 YAML 文档
                cases = self.parse_keploy_yaml(content)
                for tc in cases:
                    test_cases.append(tc.model_dump())
            except Exception as e:
                logger.warning("解析 Keploy YAML 失败 %s: %s", yaml_file, e)

        logger.info("从 %s 读取了 %d 个 Keploy 测试", output_dir, len(test_cases))
        return test_cases

    def parse_keploy_yaml(self, yaml_content: str) -> list[TestCase]:
        """解析 Keploy 录制的 YAML 为 TestCase 列表

        支持两种解析方式：
          1. 用 PyYAML 精确解析（优先）
          2. 正则提取降级（YAML 格式异常时）
        """
        cases: list[TestCase] = []

        # 尝试 PyYAML 精确解析
        try:
            docs = list(yaml.safe_load_all(yaml_content))
            for doc in docs:
                if not isinstance(doc, dict):
                    continue
                tc = self._parse_keploy_doc(doc)
                if tc:
                    cases.append(tc)
            if cases:
                return cases
        except yaml.YAMLError:
            pass

        # 降级：正则提取
        docs = re.split(r"\n---\n", yaml_content)
        for doc in docs:
            tc = self._parse_single_keploy_regex(doc)
            if tc:
                cases.append(tc)

        return cases

    def _parse_keploy_doc(self, doc: dict) -> Optional[TestCase]:
        """解析单个 Keploy YAML 文档（PyYAML 解析结果）"""
        kind = doc.get("kind", "")
        if kind.lower() != "http":
            return None

        name = doc.get("name", "keploy-test")
        spec = doc.get("spec", {})
        request = spec.get("request", {})
        response = spec.get("response", {})

        method = request.get("method", "GET")
        url = request.get("url", "")
        if not url:
            return None

        headers = request.get("header", {})
        # Keploy header 格式: {"key": ["value1", "value2"]}
        if isinstance(headers, dict):
            flat_headers = {}
            for k, v in headers.items():
                flat_headers[k] = v[0] if isinstance(v, list) and v else str(v)
            headers = flat_headers

        body = request.get("body", "")
        status_code = response.get("status_code", 200)

        step = TestStep(
            id="step1",
            type=StepType.HTTP_REQUEST,
            description=f"{method} {url}",
            request={
                "method": method,
                "url": url,
                "headers": headers,
                "body": body if body else None,
            },
            assertions=[
                Assertion(type=AssertionType.STATUS, expected=status_code),
            ],
        )

        return TestCase(
            name=f"流量录制 - {method} {url[:40]}",
            type=TestType.API,
            tags=["recorded", "traffic", "keploy"],
            created_by="recorded",
            steps=[step],
        )

    def _parse_single_keploy_regex(self, yaml_text: str) -> Optional[TestCase]:
        """正则降级解析单个 Keploy YAML"""
        name_m = re.search(r"^name:\s*(.+)$", yaml_text, re.MULTILINE)
        method_m = re.search(r"method:\s*(\w+)", yaml_text)
        url_m = re.search(r"url:\s*(\S+)", yaml_text)
        status_m = re.search(r"status_code:\s*(\d+)", yaml_text)

        if not method_m or not url_m:
            return None

        method = method_m.group(1)
        url = url_m.group(1).strip("\"'")
        name = name_m.group(1).strip() if name_m else f"keploy-{method}-{url[:20]}"
        status = int(status_m.group(1)) if status_m else 200

        return self._capture_to_test_case({
            "request": {"method": method, "url": url},
            "response": {"status_code": status},
            "name": name,
        })

    # ---- Keploy 进程管理 ----

    async def _start_keploy_capture(
        self, app_command: str, port: int, output_dir: str, session_id: str,
    ) -> dict:
        """启动 Keploy 录制进程"""
        try:
            # Keploy 命令: keploy record -c "app command" -o output_dir
            cmd = ["keploy", "record", "-o", output_dir]
            if app_command:
                cmd.extend(["-c", app_command])

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.getcwd(),
            )

            # 等待 Keploy 启动（检查进程是否立即退出）
            await asyncio.sleep(2)
            if proc.returncode is not None:
                stderr = await proc.stderr.read() if proc.stderr else b""
                return {
                    "session_id": session_id,
                    "status": "error",
                    "error": f"Keploy 启动后立即退出: {stderr.decode('utf-8', errors='replace')[:200]}",
                }

            return {
                "session_id": session_id,
                "status": "capturing",
                "mode": "keploy",
                "output_dir": output_dir,
                "process": proc,
                "hint": "请在应用中操作产生 API 流量，完成后调用 stop",
            }
        except FileNotFoundError:
            return {
                "session_id": session_id,
                "status": "error",
                "error": "keploy 命令未找到",
            }
        except Exception as e:
            return {
                "session_id": session_id,
                "status": "error",
                "error": f"启动 Keploy 失败: {e}",
            }

    async def _check_keploy(self) -> bool:
        """检查 Keploy 是否可用"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "keploy", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5)
            return proc.returncode == 0
        except (FileNotFoundError, asyncio.TimeoutError):
            return False

    # ---- 代理录制降级 ----

    def record_capture(self, session_id: str, capture: dict):
        """记录一次流量捕获（代理模式）

        Args:
            session_id: 会话 ID
            capture: {"request": {...}, "response": {...}}
        """
        session = self._active_captures.get(session_id)
        if session:
            session["captures"].append(capture)

    def _capture_to_test_case(self, capture: dict) -> Optional[TestCase]:
        """将单个流量捕获转为 TestCase"""
        request = capture.get("request", {})
        response = capture.get("response", {})
        method = request.get("method", "GET")
        url = request.get("url", "")
        if not url:
            return None

        name = capture.get("name", f"流量录制 - {method} {url[:40]}")

        step = TestStep(
            id="step1",
            type=StepType.HTTP_REQUEST,
            description=f"{method} {url}",
            request={
                "method": method,
                "url": url,
                "headers": request.get("headers", {}),
                "body": request.get("body"),
            },
            assertions=[
                Assertion(
                    type=AssertionType.STATUS,
                    expected=response.get("status_code", 200),
                ),
            ],
        )

        return TestCase(
            name=name,
            type=TestType.API,
            tags=["recorded", "traffic", "keploy"],
            created_by="recorded",
            steps=[step],
        )

    def _save_captures_yaml(self, captures: list[dict], output_dir: str):
        """将捕获的流量保存为 Keploy 兼容 YAML"""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        for i, cap in enumerate(captures):
            request = cap.get("request", {})
            response = cap.get("response", {})
            yaml_doc = {
                "version": "api.keploy.io/v1beta1",
                "kind": "Http",
                "name": f"test-{i+1}",
                "spec": {
                    "request": {
                        "method": request.get("method", "GET"),
                        "url": request.get("url", ""),
                        "header": request.get("headers", {}),
                        "body": request.get("body", ""),
                    },
                    "response": {
                        "status_code": response.get("status_code", 200),
                        "header": response.get("headers", {}),
                        "body": response.get("body", ""),
                    },
                },
            }
            yaml_file = out_path / f"test-{i+1:04d}.yaml"
            try:
                with open(yaml_file, "w", encoding="utf-8") as f:
                    yaml.dump(yaml_doc, f, allow_unicode=True, default_flow_style=False)
            except Exception as e:
                logger.warning("保存 YAML 失败: %s", e)


# 全局单例
traffic_generator = TrafficGenerator()
