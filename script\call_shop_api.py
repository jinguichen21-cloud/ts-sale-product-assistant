"""
门店信息查询脚本

通过调用商家 MCP 服务的 HTTP 接口查询当前授权商家下的门店列表。
仅流式展示通过商家MCP服务返回的数据，无需进行其他的分析处理。

使用方式：
    python call_shop_api.py <auth_code> <wdid>

参数说明：
    auth_code  商家鉴权码（WNTK），从浏览器 LocalStorage 中获取
    wdid       钉钉用户 ID（WDID）
"""

import json
import sys
import uuid

import requests

MCP_STREAM_URL = "https://open.shop.ele.me/OpenapiMcpWK/mcp/stream"
API_KEY = "ak-29412662d1a8819c-bff4-4739-bd06-d6e5f94efe0e"


def parse_sse_output(raw_lines: list) -> str:
    """
    解析 SSE 流式响应行列表，提取有效数据。
    兼容两种响应格式：
      - processData.output：流式过程数据，提取 output 字段
      - result：最终结果数据，序列化整个 result 对象
    返回所有片段拼接后的结果。
    """
    collected_outputs = []
    for line in raw_lines:
        line = line.strip()
        if not line.startswith("data:"):
            continue
        json_str = line[5:]
        if json_str == "[done]":
            continue
        try:
            data = json.loads(json_str)
            if "processData" in data:
                output = data["processData"].get("output", "")
                if output:
                    collected_outputs.append(output)
            elif "result" in data:
                collected_outputs.append(json.dumps(data["result"], ensure_ascii=False))
        except (json.JSONDecodeError, KeyError):
            pass
    return "\n".join(collected_outputs)


def call_shop_api(auth_code: str, wdid: str) -> str:
    """
    调用商家 MCP 服务接口查询门店列表，返回解析后的 output 内容。
    """
    progress_token = uuid.uuid4().hex + uuid.uuid4().hex

    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "apiKey": API_KEY,
        "sk": auth_code,
        "WDID": wdid,
    }

    body = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "NaposCodeToShop",
            "_meta": {
                "progressToken": progress_token,
            },
            "arguments": {
                "code": auth_code,
            },
        },
    }

    response = requests.post(MCP_STREAM_URL, headers=headers, json=body, stream=True, timeout=30)
    response.raise_for_status()

    # 真正的流式逐行读取，避免大响应时一次性加载到内存
    raw_lines = []
    for line in response.iter_lines(decode_unicode=True):
        if line:
            print(line, flush=True)
            raw_lines.append(line)

    return parse_sse_output(raw_lines)


def main(context: dict) -> dict:
    """
    从上下文获取参数并调用接口。
    context 包含：auth_code, wdid
    """
    auth_code = context.get("auth_code")
    wdid = context.get("wdid")

    if not auth_code or not wdid:
        return {"error": "缺少必要参数：auth_code, wdid"}

    try:
        result_text = call_shop_api(auth_code, wdid)
        return {"output": result_text}
    except requests.HTTPError as http_error:
        return {"isError": True, "error": f"HTTP 请求失败：{http_error}"}
    except Exception as error:
        return {"isError": True, "error": str(error)}


if __name__ == "__main__":
    # 支持命令行直接传参：python call_shop_api.py <auth_code> <wdid>
    if len(sys.argv) != 3:
        print("用法: python call_shop_api.py <auth_code> <wdid>")
        sys.exit(1)

    context = {
        "auth_code": sys.argv[1],
        "wdid": sys.argv[2],
    }

    result = main(context)
    print(json.dumps(result, ensure_ascii=False, indent=2))
