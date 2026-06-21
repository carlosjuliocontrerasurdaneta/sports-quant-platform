#!/usr/bin/env python
"""List active sport keys from The Odds API (verifies live coverage,
including currently active tennis tournaments)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.config import Settings
from sqp.providers.odds_api import OddsAPIClient

settings = Settings.load()
client = OddsAPIClient(settings.odds_api_key)
for s in client.list_sports():
    print(f"{s['key']:55s} active={s.get('active')} {s.get('title','')}")
