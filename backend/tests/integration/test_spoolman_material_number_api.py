"""Finding Spoolman spools by material number (Spoolman's filament.article_number).

GET /spoolman/inventory/spools?material_number=X filters the raw spools on the
filament's article number before they are mapped.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


def _spool(spool_id: int, filament_id: int, article_number: str | None, *, archived: bool = False) -> dict:
    filament = {
        "id": filament_id,
        "name": "PLA Basic",
        "material": "PLA",
        "color_hex": "FF0000",
        "weight": 1000,
        "vendor": {"id": 3, "name": "Bambu Lab"},
    }
    if article_number is not None:
        filament["article_number"] = article_number
    return {
        "id": spool_id,
        "filament": filament,
        "used_weight": 0.0,
        "archived": archived,
        "registered": "2024-01-01T00:00:00+00:00",
        "extra": {},
    }


SPOOLS = [
    _spool(1, 10, "9319236810491"),
    _spool(2, 10, "9319236810491"),
    _spool(3, 11, "15, 9319236810492 ;77"),
    _spool(4, 12, None),
    _spool(5, 13, "  "),
    _spool(6, 14, "10%"),
    _spool(7, 15, "PM 70820"),
    _spool(8, 16, "9319236810491", archived=True),
]


@pytest.fixture
async def spoolman_settings(db_session):
    from backend.app.models.settings import Settings

    db_session.add(Settings(key="spoolman_enabled", value="true"))
    db_session.add(Settings(key="spoolman_url", value="http://localhost:7912"))
    await db_session.commit()


@pytest.fixture
def mock_spoolman_client():
    client = MagicMock()
    client.base_url = "http://localhost:7912"
    client.health_check = AsyncMock(return_value=True)
    client.get_distinct_locations = AsyncMock(return_value=[])

    async def get_all_spools(allow_archived: bool = False):
        return [s for s in SPOOLS if allow_archived or not s["archived"]]

    client.get_all_spools = AsyncMock(side_effect=get_all_spools)
    with (
        patch(
            "backend.app.api.routes.spoolman_inventory.get_spoolman_client",
            AsyncMock(return_value=client),
        ),
        patch(
            "backend.app.api.routes.spoolman_inventory.init_spoolman_client",
            AsyncMock(return_value=client),
        ),
    ):
        yield client


URL = "/api/v1/spoolman/inventory/spools"


async def _ids(async_client: AsyncClient, **params) -> list[int]:
    resp = await async_client.get(URL, params=params)
    assert resp.status_code == 200, resp.text
    return sorted(s["id"] for s in resp.json())


@pytest.mark.asyncio
@pytest.mark.integration
async def test_without_parameter_lists_all_unarchived(async_client, spoolman_settings, mock_spoolman_client):
    assert await _ids(async_client) == [1, 2, 3, 4, 5, 6, 7]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_matches_whole_number(async_client, spoolman_settings, mock_spoolman_client):
    assert await _ids(async_client, material_number="9319236810491") == [1, 2]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_matches_an_entry_of_a_list(async_client, spoolman_settings, mock_spoolman_client):
    assert await _ids(async_client, material_number="9319236810492") == [3]
    assert await _ids(async_client, material_number="15") == [3]
    assert await _ids(async_client, material_number="77") == [3]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_no_substring_match(async_client, spoolman_settings, mock_spoolman_client):
    assert await _ids(async_client, material_number="931923681049") == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_space_is_not_a_separator(async_client, spoolman_settings, mock_spoolman_client):
    assert await _ids(async_client, material_number="PM 70820") == [7]
    assert await _ids(async_client, material_number="PM") == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_archived_left_out_unless_requested(async_client, spoolman_settings, mock_spoolman_client):
    assert await _ids(async_client, material_number="9319236810491", include_archived="true") == [1, 2, 8]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_empty_parameter_is_rejected(async_client, spoolman_settings, mock_spoolman_client):
    resp = await async_client.get(URL, params={"material_number": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
@pytest.mark.integration
async def test_too_long_parameter_is_rejected(async_client, spoolman_settings, mock_spoolman_client):
    resp = await async_client.get(URL, params={"material_number": "9" * 65})
    assert resp.status_code == 422


@pytest.mark.asyncio
@pytest.mark.integration
async def test_wildcards_are_literal(async_client, spoolman_settings, mock_spoolman_client):
    assert await _ids(async_client, material_number="10%") == [6]
    assert await _ids(async_client, material_number="%") == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mapped_spools_carry_the_filament_id(async_client, spoolman_settings, mock_spoolman_client):
    resp = await async_client.get(URL)
    assert resp.status_code == 200
    assert {s["id"]: s["spoolman_filament_id"] for s in resp.json()} == {
        1: 10,
        2: 10,
        3: 11,
        4: 12,
        5: 13,
        6: 14,
        7: 15,
    }
