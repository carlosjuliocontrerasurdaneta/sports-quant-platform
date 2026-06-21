"""Provider interfaces. Stats vendors for NBA/NFL/NHL/etc. are NOT assumed:
implement these interfaces with your licensed vendor. Unconfigured providers
raise ProviderNotConfiguredError explicitly.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from sqp.exceptions import ProviderNotConfiguredError


class ResultsProvider(ABC):
    """Historical final scores: required to build ratings."""

    @abstractmethod
    def fetch_results(self, league: str, days_back: int = 365) -> list[dict]:
        """Each dict: {date, home, away, home_score, away_score, neutral}."""


class StatsProvider(ABC):
    """Advanced stats / injuries / lineups. Vendor-specific."""

    @abstractmethod
    def fetch_team_stats(self, league: str) -> dict:
        ...


class NotConfiguredProvider(ResultsProvider, StatsProvider):
    def __init__(self, name: str):
        self.name = name

    def fetch_results(self, league: str, days_back: int = 365) -> list[dict]:
        raise ProviderNotConfiguredError(
            f"Results provider '{self.name}' is not configured for league '{league}'. "
            "Configure a vendor or run in demo mode (SQP_MODE=demo).")

    def fetch_team_stats(self, league: str) -> dict:
        raise ProviderNotConfiguredError(
            f"Stats provider '{self.name}' is not configured for league '{league}'.")
