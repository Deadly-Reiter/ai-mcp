from __future__ import annotations

from agent_orchestration.shared.models import ToolCall


class ResourceServer:
    def __init__(self, service_name: str, domain: str, prices: dict[str, float]) -> None:
        self.service_name = service_name
        self.domain = domain
        self.prices = prices

    def quote(self, resource: str) -> float:
        return self.prices[resource]

    async def fetch(self, call: ToolCall) -> dict:
        if self.domain not in call.allowed_domains:
            raise PermissionError(f"domain {self.domain} is not allowed")
        if self.quote(call.tool_name) > call.max_per_call + 1e-9:
            raise PermissionError(f"resource {call.tool_name} exceeds max_per_call")
        if call.tool_name == "get_price":
            symbol = call.arguments.get("symbol", "SOL")
            return {"symbol": symbol, "price": 145.2 if symbol == "SOL" else 62000.0}
        if call.tool_name == "get_onchain_metrics":
            protocol = call.arguments.get("protocol", "SOL")
            return {"protocol": protocol, "tvl_m": 980.0, "volume_m": 240.0}
        if call.tool_name == "summarize":
            return {"summary": f"LLM summary for {call.arguments.get('topic', 'task')}"}
        if call.tool_name == "backtest":
            asset = call.arguments.get("asset", "SOL")
            return {"asset": asset, "sharpe": 1.42, "win_rate": 0.57}
        if call.tool_name == "score_signal":
            asset = call.arguments.get("asset", "SOL")
            return {"asset": asset, "signal": "bullish", "score": 0.73}
        raise ValueError(f"unknown resource {call.tool_name}")
