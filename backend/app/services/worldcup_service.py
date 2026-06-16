from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional


INITIAL_BANKROLL = 10000.0


_MATCHES: List[Dict[str, Any]] = [
    {
        "match_id": "fwc26-a01",
        "stage": "小组赛",
        "group_name": "A组",
        "kickoff_at": "2026-06-17T02:00:00+08:00",
        "home_team": "英格兰",
        "away_team": "克罗地亚",
        "venue": "波士顿体育场",
        "status": "upcoming",
        "featured_pick": {
            "bet_type": "asian_handicap",
            "side": "英格兰 -0.5",
            "confidence": 76,
            "edge": 4.2,
            "stake_pct": 1.0,
            "stake_amount": 100.0,
            "rationale": [
                "1X2 与让球方向一致，主胜预期集中。",
                "Polymarket 主胜概率高于去水后的欧赔概率。",
                "大小球偏向 2.5 大，利好强队兑现让球。",
            ],
        },
        "key_market": {
            "market_type": "asian_handicap",
            "title": "亚洲让球",
            "line": "-0.5",
            "options": [
                {"label": "英格兰 -0.5", "odds": 1.92, "probability": 0.535},
                {"label": "克罗地亚 +0.5", "odds": 1.96, "probability": 0.525},
            ],
        },
        "markets": [
            {
                "market_type": "h2h",
                "title": "胜平负",
                "options": [
                    {"label": "英格兰", "odds": 1.88, "probability": 0.492},
                    {"label": "平局", "odds": 3.42, "probability": 0.271},
                    {"label": "克罗地亚", "odds": 4.35, "probability": 0.237},
                ],
            },
            {
                "market_type": "asian_handicap",
                "title": "亚洲让球",
                "line": "-0.5",
                "options": [
                    {"label": "英格兰 -0.5", "odds": 1.92, "probability": 0.535},
                    {"label": "克罗地亚 +0.5", "odds": 1.96, "probability": 0.525},
                ],
            },
            {
                "market_type": "totals",
                "title": "大小球",
                "line": "2.5",
                "options": [
                    {"label": "大 2.5", "odds": 1.87, "probability": 0.517},
                    {"label": "小 2.5", "odds": 1.99, "probability": 0.486},
                ],
            },
            {
                "market_type": "polymarket",
                "title": "Polymarket",
                "options": [
                    {"label": "英格兰不败", "odds": 1.41, "probability": 0.709},
                    {"label": "英格兰获胜", "odds": 1.95, "probability": 0.513},
                ],
            },
        ],
        "line_movement": [
            {"label": "开盘", "line": -0.25, "home_odds": 1.98, "away_odds": 1.88},
            {"label": "即时", "line": -0.5, "home_odds": 1.92, "away_odds": 1.96},
        ],
        "polymarket_probabilities": {"home": 0.51, "draw": 0.25, "away": 0.24},
    },
    {
        "match_id": "fwc26-d04",
        "stage": "小组赛",
        "group_name": "D组",
        "kickoff_at": "2026-06-18T09:00:00+08:00",
        "home_team": "美国",
        "away_team": "巴拉圭",
        "venue": "洛杉矶体育场",
        "status": "upcoming",
        "featured_pick": {
            "bet_type": "h2h",
            "side": "美国 胜",
            "confidence": 68,
            "edge": 2.6,
            "stake_pct": 0.6,
            "stake_amount": 60.0,
            "rationale": [
                "主场环境与市场主胜概率方向一致。",
                "让球未明显升深，说明优势有限，适合轻仓。",
                "平局概率仍高于 25%，不宜重仓。",
            ],
        },
        "key_market": {
            "market_type": "h2h",
            "title": "胜平负",
            "options": [
                {"label": "美国", "odds": 2.11, "probability": 0.456},
                {"label": "平局", "odds": 3.16, "probability": 0.289},
                {"label": "巴拉圭", "odds": 3.65, "probability": 0.255},
            ],
        },
        "markets": [
            {
                "market_type": "h2h",
                "title": "胜平负",
                "options": [
                    {"label": "美国", "odds": 2.11, "probability": 0.456},
                    {"label": "平局", "odds": 3.16, "probability": 0.289},
                    {"label": "巴拉圭", "odds": 3.65, "probability": 0.255},
                ],
            },
            {
                "market_type": "asian_handicap",
                "title": "亚洲让球",
                "line": "-0.25",
                "options": [
                    {"label": "美国 -0.25", "odds": 1.94, "probability": 0.528},
                    {"label": "巴拉圭 +0.25", "odds": 1.94, "probability": 0.528},
                ],
            },
            {
                "market_type": "totals",
                "title": "大小球",
                "line": "2.25",
                "options": [
                    {"label": "大 2.25", "odds": 2.01, "probability": 0.482},
                    {"label": "小 2.25", "odds": 1.84, "probability": 0.527},
                ],
            },
        ],
        "line_movement": [
            {"label": "开盘", "line": 0.0, "home_odds": 1.87, "away_odds": 2.0},
            {"label": "即时", "line": -0.25, "home_odds": 1.94, "away_odds": 1.94},
        ],
        "polymarket_probabilities": {"home": 0.47, "draw": 0.27, "away": 0.26},
    },
    {
        "match_id": "fwc26-c08",
        "stage": "小组赛",
        "group_name": "C组",
        "kickoff_at": "2026-06-15T20:00:00+08:00",
        "home_team": "巴西",
        "away_team": "摩洛哥",
        "venue": "休斯敦体育场",
        "status": "settled",
        "home_score": 1,
        "away_score": 1,
        "featured_pick": {
            "bet_type": "totals",
            "side": "小 2.75",
            "confidence": 72,
            "edge": 3.4,
            "stake_pct": 0.75,
            "stake_amount": 75.0,
            "rationale": [
                "大小球持续压低，市场更偏谨慎节奏。",
                "让球未继续升深，说明强弱差未扩张。",
                "Polymarket 对平局的定价偏高，利于小比分路径。",
            ],
        },
        "key_market": {
            "market_type": "totals",
            "title": "大小球",
            "line": "2.75",
            "options": [
                {"label": "大 2.75", "odds": 2.08, "probability": 0.472},
                {"label": "小 2.75", "odds": 1.82, "probability": 0.539},
            ],
        },
        "markets": [
            {
                "market_type": "h2h",
                "title": "胜平负",
                "options": [
                    {"label": "巴西", "odds": 1.76, "probability": 0.541},
                    {"label": "平局", "odds": 3.58, "probability": 0.266},
                    {"label": "摩洛哥", "odds": 4.82, "probability": 0.193},
                ],
            },
            {
                "market_type": "asian_handicap",
                "title": "亚洲让球",
                "line": "-0.75",
                "options": [
                    {"label": "巴西 -0.75", "odds": 1.98, "probability": 0.505},
                    {"label": "摩洛哥 +0.75", "odds": 1.9, "probability": 0.526},
                ],
            },
            {
                "market_type": "totals",
                "title": "大小球",
                "line": "2.75",
                "options": [
                    {"label": "大 2.75", "odds": 2.08, "probability": 0.472},
                    {"label": "小 2.75", "odds": 1.82, "probability": 0.539},
                ],
            },
        ],
        "line_movement": [
            {"label": "开盘", "line": -1.0, "home_odds": 1.94, "away_odds": 1.92},
            {"label": "即时", "line": -0.75, "home_odds": 1.98, "away_odds": 1.9},
        ],
        "polymarket_probabilities": {"home": 0.55, "draw": 0.23, "away": 0.22},
    },
]


_BANKROLL_CURVE: List[Dict[str, Any]] = [
    {"label": "开赛前", "bankroll": 10000.0, "pnl": 0.0},
    {"label": "第1场", "bankroll": 10125.0, "pnl": 125.0},
    {"label": "第2场", "bankroll": 10042.0, "pnl": -83.0},
    {"label": "第3场", "bankroll": 10196.0, "pnl": 154.0},
    {"label": "当前", "bankroll": 10196.0, "pnl": 196.0},
]


_PHASE_BREAKDOWN: List[Dict[str, Any]] = [
    {"phase": "小组赛", "matches": 13, "roi": 1.96, "hit_rate": 53.8},
    {"phase": "32强", "matches": 0, "roi": 0.0, "hit_rate": 0.0},
    {"phase": "16强", "matches": 0, "roi": 0.0, "hit_rate": 0.0},
]


_MARKET_HEAT: List[Dict[str, Any]] = [
    {"label": "主胜信号占比", "value": 58.0},
    {"label": "让球方向一致率", "value": 64.0},
    {"label": "大球市场偏热", "value": 41.0},
]


class WorldCupService:
    @staticmethod
    async def get_overview() -> Dict[str, Any]:
        settled_matches = sum(1 for match in _MATCHES if match["status"] == "settled")
        open_positions = sum(1 for match in _MATCHES if match["status"] != "settled")
        bankroll = _BANKROLL_CURVE[-1]["bankroll"]
        roi = round((bankroll - INITIAL_BANKROLL) / INITIAL_BANKROLL * 100, 2)

        return {
            "tournament": "2026 FIFA World Cup",
            "bankroll": bankroll,
            "initial_bankroll": INITIAL_BANKROLL,
            "settled_matches": settled_matches,
            "open_positions": open_positions,
            "roi": roi,
            "max_drawdown": -1.4,
            "next_match_at": _MATCHES[0]["kickoff_at"],
            "phase_breakdown": deepcopy(_PHASE_BREAKDOWN),
            "featured_matches": [WorldCupService._summary(match) for match in _MATCHES[:3]],
            "bankroll_curve": deepcopy(_BANKROLL_CURVE),
            "market_heat": deepcopy(_MARKET_HEAT),
        }

    @staticmethod
    async def list_matches(stage: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        matches = deepcopy(_MATCHES)
        if stage:
            matches = [match for match in matches if match["stage"] == stage]
        if status:
            matches = [match for match in matches if match["status"] == status]
        return [WorldCupService._summary(match) for match in matches]

    @staticmethod
    async def get_match_detail(match_id: str) -> Optional[Dict[str, Any]]:
        match = next((item for item in _MATCHES if item["match_id"] == match_id), None)
        if not match:
            return None
        return deepcopy(match)

    @staticmethod
    def _summary(match: Dict[str, Any]) -> Dict[str, Any]:
        summary = {
            "match_id": match["match_id"],
            "stage": match["stage"],
            "group_name": match.get("group_name"),
            "kickoff_at": match["kickoff_at"],
            "home_team": match["home_team"],
            "away_team": match["away_team"],
            "venue": match["venue"],
            "status": match["status"],
            "home_score": match.get("home_score"),
            "away_score": match.get("away_score"),
            "featured_pick": deepcopy(match["featured_pick"]),
            "key_market": deepcopy(match["key_market"]),
        }
        return summary

