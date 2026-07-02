"""OpenAPI/Swagger 解析器 — 从 URL 或文件提取 API 端点信息"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin

import aiohttp
import yaml

logger = logging.getLogger("testforge")


@dataclass
class Endpoint:
    """API 端点定义"""
    path: str
    method: str                  # GET/POST/PUT/DELETE/PATCH
    summary: str = ""
    operation_id: str = ""
    parameters: list[dict] = field(default_factory=list)     # path/query 参数
    request_body: Optional[dict] = None                        # 请求体 schema
    responses: dict = field(default_factory=dict)             # 响应码 → schema
    tags: list[str] = field(default_factory=list)


@dataclass
class ApiSpec:
    """解析后的 API 规范"""
    title: str
    version: str
    base_url: str
    endpoints: list[Endpoint] = field(default_factory=list)


async def parse_openapi_url(url: str, timeout: int = 15) -> ApiSpec:
    """从 URL 获取并解析 OpenAPI/Swagger 文档。

    支持:
      - JSON 格式 (.json)
      - YAML 格式 (.yaml/.yml)
      - Swagger 2.0 和 OpenAPI 3.x
    """
    raw = await _fetch_document(url, timeout)
    return parse_openapi_content(raw, base_url=_infer_base_url(url))


async def _fetch_document(url: str, timeout: int) -> str:
    """获取文档内容"""
    timeout_cfg = aiohttp.ClientTimeout(total=timeout)
    async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise ValueError(f"获取文档失败: HTTP {resp.status}")
            return await resp.text()


def parse_openapi_content(content: str, base_url: str = "") -> ApiSpec:
    """解析 OpenAPI/Swagger 文档内容（字符串）"""
    # 尝试 JSON，失败则 YAML
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(f"文档格式无法解析 (非 JSON/YAML): {e}")

    # Swagger 2.0 vs OpenAPI 3.x
    if "swagger" in data:
        return _parse_swagger2(data, base_url)
    elif "openapi" in data:
        return _parse_openapi3(data, base_url)
    else:
        raise ValueError("无法识别的文档格式（缺少 swagger/openapi 版本字段）")


def _parse_swagger2(data: dict, base_url: str) -> ApiSpec:
    """解析 Swagger 2.0"""
    info = data.get("info", {})
    host = data.get("host", "")
    base_path = data.get("basePath", "")
    if host:
        scheme = (data.get("schemes") or ["http"])[0]
        base_url = f"{scheme}://{host}{base_path}"

    endpoints = []
    for path, methods in data.get("paths", {}).items():
        for method, spec in methods.items():
            if method not in ("get", "post", "put", "delete", "patch"):
                continue
            endpoints.append(_build_endpoint(path, method, spec))

    return ApiSpec(
        title=info.get("title", "Unknown API"),
        version=info.get("version", "1.0.0"),
        base_url=base_url.rstrip("/"),
        endpoints=endpoints,
    )


def _parse_openapi3(data: dict, base_url: str) -> ApiSpec:
    """解析 OpenAPI 3.x"""
    info = data.get("info", {})
    servers = data.get("servers", [])
    if servers and not base_url:
        base_url = servers[0].get("url", "")

    endpoints = []
    for path, methods in data.get("paths", {}).items():
        for method, spec in methods.items():
            if method not in ("get", "post", "put", "delete", "patch"):
                continue
            endpoints.append(_build_endpoint(path, method, spec))

    return ApiSpec(
        title=info.get("title", "Unknown API"),
        version=info.get("version", "1.0.0"),
        base_url=base_url.rstrip("/"),
        endpoints=endpoints,
    )


def _build_endpoint(path: str, method: str, spec: dict) -> Endpoint:
    """构建单个端点"""
    parameters = spec.get("parameters", [])
    request_body = spec.get("requestBody")  # OpenAPI 3
    if not request_body and "parameters" in spec:
        # Swagger 2 body 参数
        for p in parameters:
            if p.get("in") == "body":
                request_body = p.get("schema")

    return Endpoint(
        path=path,
        method=method.upper(),
        summary=spec.get("summary", ""),
        operation_id=spec.get("operationId", ""),
        parameters=parameters,
        request_body=request_body,
        responses=spec.get("responses", {}),
        tags=spec.get("tags", []),
    )


def _infer_base_url(url: str) -> str:
    """从文档 URL 推断 API base URL"""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def spec_to_dict(spec: ApiSpec) -> dict:
    """将 ApiSpec 序列化为字典"""
    return {
        "title": spec.title,
        "version": spec.version,
        "base_url": spec.base_url,
        "endpoint_count": len(spec.endpoints),
        "endpoints": [
            {
                "path": e.path,
                "method": e.method,
                "summary": e.summary,
                "operation_id": e.operation_id,
                "tags": e.tags,
                "has_request_body": e.request_body is not None,
                "response_codes": list(e.responses.keys()),
            }
            for e in spec.endpoints
        ],
    }
