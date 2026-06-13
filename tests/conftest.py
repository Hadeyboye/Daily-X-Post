"""
tests/conftest.py
Pytest fixtures (expand as needed).
"""
import pytest


@pytest.fixture(scope="session")
def sample_config():
    return {
        "platform": {"version": "test"},
        "brand": {"name": "TestBrand", "voice": "Direct.", "handle": "@test"},
        "niche": {"primary": "tech_ai", "keywords": ["agents"]},
        "executor": {"dry_run": True},
        "safety": {"enabled": True, "blocked_keywords": ["scam"]},
    }
