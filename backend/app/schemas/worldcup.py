from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class WorldCupMarketPrice(BaseModel):
    label: str
    odds: float
    probability: float


class WorldCupMarket(BaseModel):
    market_type: Literal["h2h", "asian_handicap", "totals", "polymarket"]
    title: str
    line: Optional[str] = None
    options: List[WorldCupMarketPrice]


class WorldCupPick(BaseModel):
    bet_type: Literal["h2h", "asian_handicap", "totals"]
    strategy: str
    side: str
    signal_label: Optional[str] = None
    book_probability: Optional[float] = None
    fair_probability: Optional[float] = None
    confidence: int = Field(..., ge=0, le=100)
    edge: float
    stake_pct: float
    stake_amount: float
    rationale: List[str]


class WorldCupMatchSummary(BaseModel):
    match_id: str
    stage: str
    group_name: Optional[str] = None
    kickoff_at: str
    home_team: str
    away_team: str
    venue: str
    status: Literal["upcoming", "live", "settled"]
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    source: Optional[str] = None
    external_url: Optional[str] = None
    featured_pick: WorldCupPick
    key_market: WorldCupMarket


class WorldCupMatchDetail(WorldCupMatchSummary):
    markets: List[WorldCupMarket]
    line_movement: List[Dict[str, str | float]]
    polymarket_probabilities: Dict[str, float]


class WorldCupBankrollPoint(BaseModel):
    label: str
    bankroll: float
    pnl: float


class WorldCupOverview(BaseModel):
    tournament: str
    bankroll: float
    initial_bankroll: float
    settled_matches: int
    open_positions: int
    roi: float
    max_drawdown: float
    next_match_at: str
    phase_breakdown: List[Dict[str, str | float | int]]
    featured_matches: List[WorldCupMatchSummary]
    bankroll_curve: List[WorldCupBankrollPoint]
    market_heat: List[Dict[str, str | float]]
