"""Engineered feature datasets for ML models (ported from the ML project).

Builds temporally-correct rolling-form training datasets for the major team
sports from this platform's CSV results store. Pregame features use only past
games (no leakage); see sqp.features.builders and sqp.storage.feature_store.
"""
