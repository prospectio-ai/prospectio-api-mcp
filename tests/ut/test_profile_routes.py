"""
Tests for application/api/profile_routes.py - Profile router factory.
"""
import pytest
from unittest.mock import AsyncMock
from fastapi import APIRouter

from application.api.profile_routes import profile_router


class TestProfileRouterFactory:
    """Test suite for the profile_router factory function."""

    def test_returns_api_router(self):
        """profile_router() should return an APIRouter instance."""
        router = profile_router(
            repository=AsyncMock(),
            leads_repository=AsyncMock(),
        )
        assert isinstance(router, APIRouter)

    def test_router_has_profile_endpoints(self):
        """Router should have all expected profile endpoints."""
        router = profile_router(
            repository=AsyncMock(),
            leads_repository=AsyncMock(),
        )
        route_paths = [r.path for r in router.routes]
        assert "/profile/upsert" in route_paths
        assert "/profile" in route_paths
        assert "/profile/upload-resume" in route_paths
        assert "/profile/reset" in route_paths

    def test_router_has_correct_methods(self):
        """Endpoints should have correct HTTP methods."""
        router = profile_router(
            repository=AsyncMock(),
            leads_repository=AsyncMock(),
        )
        routes_dict = {r.path: r.methods for r in router.routes if hasattr(r, 'methods')}

        assert "POST" in routes_dict.get("/profile/upsert", set())
        assert "GET" in routes_dict.get("/profile", set())
        assert "POST" in routes_dict.get("/profile/upload-resume", set())
        assert "DELETE" in routes_dict.get("/profile/reset", set())
