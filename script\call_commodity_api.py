"""
商品相关数据获取脚本

通过调用商家 MCP 服务的 HTTP 接口获取店铺商品数据。
仅流式展示通过商家MCP服务返回的数据，无需进行其他的分析处理。

使用方式：
    python call_commodity_api.py --wdid <钉钉ID> --auth-code <鉴权码> --shop-id <店铺ID> --tool-code <工具码> [--item-ids <商品ID列表>]

参数说明：
    --wdid       钉钉用户 ID（WDID）
    --auth-code  商家鉴权码（WNTK），用于 sk 请求头
    --shop-id    店铺 ID
    --tool-code  工具码，例如：
                   wk-mcp-spu-agentitemdefensesoaservice-getagentitemdefense
                   wk-mcp-spu-agentitemdefensesoaservice-listitemsbyitemids
    --item-ids   商品 ID 列表（JSON 数组格式，可选），例如：[123, 456]
"""

import argparse
import json
import sys

import requests

MCP_STREAM_URL = "https://open.shop.ele.me/OpenapiMcpWK/mcp/stream"
API_KEY = "ak-29412662d1a8819c-bff4-4739-bd06-d6e5f94efe0e"


def build_request_headers(wdid: str, shop_id: str, auth_code: str) -> dict:
    return {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "apiKey": API_KEY,
        "sk": auth_code,
        "WDID": wdid,
        "shopId": shop_id,
        "x-shard": f"shopId={shop_id}",
    }


def build_request_body(tool_code: str, shop_id: str, item_ids) -> dict:
    biz_params = {
        "tool_code": tool_code,
        "shopId": shop_id,
    }
    if item_ids is not None:
        biz_params["itemIds"] = item_ids

    return {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "callLLMStack",
            "_meta": {
                "progressToken": "13123123",
            },
            "arguments": {
                "query": "xxx",
                "bizScene": "wukong_commodity_defense",
                "bizParams": biz_params,
            },
        },
    }


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


def call_commodity_api(wdid: str, shop_id: str, tool_code: str, auth_code: str, item_ids=None) -> str:
    """
    调用商家 MCP 服务接口，返回解析后的 output 内容。
    """
    headers = build_request_headers(wdid, shop_id, auth_code)
    body = build_request_body(tool_code, shop_id, item_ids)

    try:
        response = requests.post(MCP_STREAM_URL, headers=headers, json=body, stream=True, timeout=30)
        response.raise_for_status()
    except requests.HTTPError as http_error:
        print(f"错误：HTTP 请求失败，状态码 {http_error.response.status_code}：{http_error}", file=sys.stderr)
        sys.exit(1)
    except requests.ConnectionError as conn_error:
        print(f"错误：网络连接失败：{conn_error}", file=sys.stderr)
        sys.exit(1)
    except requests.Timeout:
        print("错误：请求超时，请检查网络或稍后重试", file=sys.stderr)
        sys.exit(1)

    # 真正的流式逐行读取，避免大响应时一次性加载到内存
    raw_lines = []
    for line in response.iter_lines(decode_unicode=True):
        if line:
            raw_lines.append(line)

    return parse_sse_output(raw_lines)


def main():
    parser = argparse.ArgumentParser(description="调用商家 MCP 服务获取商品相关数据")
    parser.add_argument("--wdid", required=True, help="钉钉用户 ID（WDID）")
    parser.add_argument("--auth-code", required=True, help="商家鉴权码（WNTK），用于 sk 请求头")
    parser.add_argument("--shop-id", required=True, help="店铺 ID")
    parser.add_argument("--tool-code", required=True, help="工具码（tool_code）")
    parser.add_argument("--item-ids", default=None, help="商品 ID 列表（JSON 数组格式，可选），例如：[123, 456]")
    args = parser.parse_args()

    item_ids = None
    if args.item_ids:
        try:
            item_ids = json.loads(args.item_ids)
        except json.JSONDecodeError:
            print("错误：--item-ids 参数格式不正确，请传入合法的 JSON 数组，例如：[123, 456]", file=sys.stderr)
            sys.exit(1)

    result = call_commodity_api(
        wdid=args.wdid,
        shop_id=args.shop_id,
        tool_code=args.tool_code,
        auth_code=args.auth_code,
        item_ids=item_ids,
    )
    print(result)


if __name__ == "__main__":
    main()
