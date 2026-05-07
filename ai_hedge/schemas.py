from pydantic import BaseModel, Field
from typing import Literal


class WarrenBuffettSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")
    holding_period: str = Field(description="Recommended holding period")


class CharlieMungerSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int
    reasoning: str
    holding_period: str = Field(description="Recommended holding period")


class BenGrahamSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str
    holding_period: str = Field(description="Recommended holding period")


class BillAckmanSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str
    holding_period: str = Field(description="Recommended holding period")


class CathieWoodSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str
    holding_period: str = Field(description="Recommended holding period")


class MichaelBurrySignal(BaseModel):
    """Schema returned by the LLM."""

    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float  # 0–100
    reasoning: str
    holding_period: str = Field(description="Recommended holding period")


class NassimTalebSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")
    holding_period: str = Field(description="Recommended holding period")


class PeterLynchSignal(BaseModel):
    """
    Container for the Peter Lynch-style output signal.
    """
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str
    holding_period: str = Field(description="Recommended holding period")


class PhilFisherSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str
    holding_period: str = Field(description="Recommended holding period")


class StanleyDruckenmillerSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str
    holding_period: str = Field(description="Recommended holding period")


class MohnishPabraiSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str
    holding_period: str = Field(description="Recommended holding period")


class RakeshJhunjhunwalaSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str
    holding_period: str = Field(description="Recommended holding period")


class AswathDamodaranSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float          # 0‒100
    reasoning: str
    holding_period: str = Field(description="Recommended holding period")


class NewsSentimentSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float = Field(description="Confidence level 0-100")
    reasoning: str = Field(description="Brief reasoning for the sentiment assessment")
    holding_period: str = Field(description="Recommended holding period")


class Sentiment(BaseModel):
    """Represents the sentiment of a news article."""

    sentiment: Literal["positive", "negative", "neutral"]
    confidence: int = Field(description="Confidence 0-100")


class PortfolioDecision(BaseModel):
    action: Literal["buy", "sell", "short", "cover", "hold"]
    quantity: int = Field(description="Number of shares to trade")
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")
    duration: str = Field(description="Recommended holding duration synthesized from analyst signals")


class PortfolioManagerOutput(BaseModel):
    decisions: dict[str, PortfolioDecision] = Field(description="Dictionary of ticker to trading decisions")


class SwingSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float = Field(description="Confidence 0-100")
    reasoning: str
    entry_price: float = Field(description="Suggested entry price")
    target_price: float = Field(description="Target exit price")
    stop_loss: float = Field(description="Stop loss price")
    timeframe: str = Field(description="Expected holding period, e.g. '5-10 trading days'")


class SwingPortfolioDecision(BaseModel):
    action: Literal["buy", "sell", "short", "cover", "hold"]
    entry_price: float = Field(description="Entry price level")
    target_price: float = Field(description="Target price")
    stop_loss: float = Field(description="Stop loss price")
    risk_reward_ratio: str = Field(description="Risk reward ratio e.g. '3.2:1'")
    timeframe: str = Field(description="Expected trade duration")
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str


class DayTradeSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float = Field(description="Confidence 0-100")
    reasoning: str
    entry_trigger: str = Field(description="Entry condition, e.g. 'break above 248.50'")
    target_1: float = Field(description="First target price")
    target_2: float = Field(description="Second target price")
    stop_loss: float = Field(description="Stop loss price")
    risk_reward: str = Field(description="Risk reward ratio")
    time_window: str = Field(description="When the setup is valid, e.g. 'first 2 hours'")


class DayTradePortfolioDecision(BaseModel):
    setup_name: str = Field(description="Name of the trade setup")
    direction: Literal["long", "short", "no_trade"]
    entry_trigger: str = Field(description="Entry condition")
    targets: list[float] = Field(description="Target prices in order")
    stop_loss: float = Field(description="Stop loss price")
    position_size: str = Field(description="Position sizing guidance")
    time_window: str = Field(description="When the setup is valid")
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str


class HeadTraderSignal(BaseModel):
    consensus_signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Synthesis of all strategy signals")
    agent_agreement_pct: float = Field(description="Percentage of agents that agree with consensus")
    key_conflicts: str = Field(description="Summary of main disagreements between agents")
    recommended_action: str = Field(description="Recommended trade action based on synthesis")


class ResearchReport(BaseModel):
    bull_case: str = Field(description="Summary of bullish arguments across all agents")
    bear_case: str = Field(description="Summary of bearish arguments across all agents")
    key_metrics: dict = Field(description="Important financial and technical metrics")
    risks: list[str] = Field(description="Key risk factors identified")
    agent_breakdown: dict = Field(description="Per-agent signal summary")
    overall_sentiment: Literal["bullish", "bearish", "neutral", "mixed"]
    confidence_range: str = Field(description="Range of confidence across agents, e.g. '45-92'")


class TickerExplanation(BaseModel):
    verdict: str = Field(description="One-sentence verdict with confidence")
    bull_case: str = Field(description="Plain English bull case paragraph")
    bear_case: str = Field(description="Plain English bear case paragraph")
    key_numbers: dict[str, str] = Field(description="Metric name → value + plain English explanation")
    risk_summary: str = Field(description="Plain English risk paragraph")


class ExplainerOutput(BaseModel):
    tldr: str = Field(description="2-3 sentence plain English summary")
    narrative: str = Field(description="Multi-paragraph story explaining the analysis")
    per_ticker: dict[str, TickerExplanation] = Field(description="Per-ticker educational breakdown")
    concepts: dict[str, str] = Field(description="Glossary of technical terms used, in plain English")


# ── System B Stage 3 perspective + judge schemas ─────────────────────────
# Loud-crash validation: malformed agent JSON raises pydantic.ValidationError
# with a detailed traceback instead of silently degrading downstream.

class BullPerspectiveOutput(BaseModel):
    ticker: str
    setup_direction: Literal["long", "short"]
    bull_strength: int  # 1-10
    entry_zone: dict   # {"low": float, "high": float}
    target: float
    stop: float
    expected_holding_days: int
    top_3_arguments: list[str]
    risks_acknowledged: list[str]
    web_sources_last_7d: list[str]


class BearPerspectiveOutput(BaseModel):
    ticker: str
    setup_direction: Literal["long", "short"]
    bear_strength: int  # 1-10
    top_3_arguments: list[str]
    bull_acknowledgements: list[str]
    web_sources_last_7d: list[str]
    # Optional fields used by some bear variants
    setup_invalidation_levels: list[float] | None = None
    thesis_crack_level: Literal["none", "minor", "moderate", "severe"] | None = None


class JudgeApprovedTrade(BaseModel):
    ticker: str
    direction: Literal["long", "short"]
    entry_price: float
    stop_loss: float
    target_price: float
    target_price_2: float | None = None
    quantity: int
    expected_holding_days: int
    setup_type: str
    conviction: int  # 1-10
    rationale: str
    risk_usd: float
    position_size_class: Literal["standard", "small_scaled"] = "standard"
    entry_valid_until: str | None = None  # ISO 8601 UTC; null = end-of-decision-day at 16:00 ET


class JudgeOutput(BaseModel):
    ticker: str
    approved: list[JudgeApprovedTrade]
    rejected: list[dict]   # {"ticker": str, "reason": str}
    summary: str


# ── System B Stage 3 news researcher schema ──────────────────────────────
# A single-purpose WebSearch agent that runs BEFORE the bull/bear perspectives.
# Produces runs/<run_id>/news/<TICKER>.json. The bull/bear facts builder merges
# its `news_items` into `recent_news_7d` so the perspective agents have a
# pre-populated authoritative news window and never need to invoke WebSearch
# themselves. raw_search_files must contain at least one entry — the pipeline
# verification step counts raw files on disk and aborts if any are missing.

class NewsItem(BaseModel):
    headline: str
    url: str
    date: str  # YYYY-MM-DD
    sentiment: Literal["positive", "negative", "neutral"]
    summary: str


class AnalystConsensus(BaseModel):
    rating: Literal["buy", "hold", "sell", "mixed", "unknown"]
    avg_price_target: float | None = None
    recent_changes: str


class EarningsContext(BaseModel):
    next_earnings_date: str | None = None  # YYYY-MM-DD
    days_until_next: int | None = None
    notes: str


class NewsResearcherOutput(BaseModel):
    ticker: str
    researched_at: str  # ISO 8601 UTC
    news_items: list[NewsItem]
    analyst_consensus: AnalystConsensus
    earnings_context: EarningsContext
    raw_search_files: list[str] = Field(min_length=1)
