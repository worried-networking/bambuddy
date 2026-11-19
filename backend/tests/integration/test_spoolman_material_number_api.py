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
    resp = await async_client.get(URL)
    assert resp.status_code == 200
    rows = resp.json()
    # Spoolman order is kept; the archived spool 8 is left out.
    assert [(s["id"], s["spoolman_filament_id"], s["material_number"]) for s in rows] == [
        (1, 10, "9319236810491"),
        (2, 10, "9319236810491"),
        (3, 11, "15, 9319236810492 ;77"),
        (4, 12, None),
        (5, 13, None),
        (6, 14, "10%"),
        (7, 15, "PM 70820"),
    ]
    # Every row has the mapped shape and nothing else.
    from backend.app.api.routes._spoolman_helpers import MappedSpoolFields

    for row in rows:
        assert set(MappedSpoolFields.__annotations__) <= set(row)


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


FILAMENT_URL = "/api/v1/spoolman/inventory/filaments"


def _filament(**extra) -> dict:
    return {
        "id": 7,
        "name": "PLA Basic",
        "material": "PLA",
        "color_hex": "FF0000",
        "weight": 1000,
        "spool_weight": 250.0,
        "vendor": {"id": 3, "name": "Bambu Lab"},
        **extra,
    }


@pytest.fixture
def filament_client():
    client = MagicMock()
    client.base_url = "http://localhost:7912"
    client.get_filament = AsyncMock(return_value=_filament())
    client.patch_filament = AsyncMock(side_effect=lambda fid, data: _filament(**data))
    client.get_filaments = AsyncMock(return_value=[])
    client.get_all_spools = AsyncMock(return_value=[])
    client.update_spool_full = AsyncMock(return_value={})
    with patch("backend.app.api.routes.spoolman_inventory._get_client", AsyncMock(return_value=client)):
        yield client


class TestFilamentMaterialNumber:
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_filaments_list_has_material_number(self, async_client, spoolman_settings, filament_client):
        filament_client.get_filaments.return_value = [
            _filament(id=1, article_number="  9319236810491 "),
            _filament(id=2, article_number="   "),
            _filament(id=3),
        ]
        resp = await async_client.get(FILAMENT_URL)
        assert resp.status_code == 200
        assert {f["id"]: f["material_number"] for f in resp.json()} == {1: "9319236810491", 2: None, 3: None}

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_patch_sends_article_number(self, async_client, spoolman_settings, filament_client):
        resp = await async_client.patch(f"{FILAMENT_URL}/7", json={"material_number": "a,b"})
        assert resp.status_code == 200
        filament_client.patch_filament.assert_called_once_with(7, {"article_number": "a,b"})
        assert resp.json()["material_number"] == "a,b"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_patch_trims_the_value(self, async_client, spoolman_settings, filament_client):
        resp = await async_client.patch(f"{FILAMENT_URL}/7", json={"material_number": "  15  "})
        assert resp.status_code == 200
        filament_client.patch_filament.assert_called_once_with(7, {"article_number": "15"})

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_patch_blank_clears(self, async_client, spoolman_settings, filament_client):
        resp = await async_client.patch(f"{FILAMENT_URL}/7", json={"material_number": "  "})
        assert resp.status_code == 200
        filament_client.patch_filament.assert_called_once_with(7, {"article_number": None})
        assert resp.json()["material_number"] is None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_patch_explicit_null_clears(self, async_client, spoolman_settings, filament_client):
        resp = await async_client.patch(f"{FILAMENT_URL}/7", json={"material_number": None})
        assert resp.status_code == 200
        filament_client.patch_filament.assert_called_once_with(7, {"article_number": None})

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_patch_without_field_sends_no_article_number(self, async_client, spoolman_settings, filament_client):
        resp = await async_client.patch(f"{FILAMENT_URL}/7", json={"name": "PLA Matte"})
        assert resp.status_code == 200
        filament_client.patch_filament.assert_called_once_with(7, {"name": "PLA Matte"})

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_patch_too_long_is_rejected(self, async_client, spoolman_settings, filament_client):
        resp = await async_client.patch(f"{FILAMENT_URL}/7", json={"material_number": "9" * 65})
        assert resp.status_code == 422
        filament_client.patch_filament.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_padded_value_is_held_to_64_after_trim(self, async_client, spoolman_settings, filament_client):
        resp = await async_client.patch(f"{FILAMENT_URL}/7", json={"material_number": " " + "9" * 64 + " "})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_weight_patch_does_not_touch_the_number(self, async_client, spoolman_settings, filament_client):
        resp = await async_client.patch(f"{FILAMENT_URL}/7", json={"spool_weight": 196.0})
        assert resp.status_code == 200
        filament_client.patch_filament.assert_called_once_with(7, {"spool_weight": 196.0})

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_number_with_weight_stamps_spools_as_before(self, async_client, spoolman_settings, filament_client):
        filament_client.get_all_spools.return_value = [{"id": 42, "spool_weight": None, "filament": {"id": 7}}]
        resp = await async_client.patch(f"{FILAMENT_URL}/7", json={"material_number": "5", "spool_weight": 196.0})
        assert resp.status_code == 200
        filament_client.patch_filament.assert_called_once_with(7, {"article_number": "5", "spool_weight": 196.0})
        filament_client.update_spool_full.assert_called_once_with(spool_id=42, spool_weight=196.0)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_number_alone_does_not_restamp_spools(self, async_client, spoolman_settings, filament_client):
        resp = await async_client.patch(f"{FILAMENT_URL}/7", json={"material_number": "5"})
        assert resp.status_code == 200
        filament_client.get_all_spools.assert_not_called()
        filament_client.update_spool_full.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_spoolman_404_maps_to_404(self, async_client, spoolman_settings, filament_client):
        from backend.app.services.spoolman import SpoolmanNotFoundError

        filament_client.get_filament.side_effect = SpoolmanNotFoundError("gone")
        resp = await async_client.patch(f"{FILAMENT_URL}/7", json={"material_number": "5"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_spoolman_5xx_maps_to_502(self, async_client, spoolman_settings, filament_client):
        from backend.app.services.spoolman import SpoolmanClientError

        filament_client.patch_filament.side_effect = SpoolmanClientError("boom", status_code=500)
        resp = await async_client.patch(f"{FILAMENT_URL}/7", json={"material_number": "5"})
        assert resp.status_code == 502

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_spoolman_unreachable_maps_to_503(self, async_client, spoolman_settings, filament_client):
        from backend.app.services.spoolman import SpoolmanUnavailableError

        filament_client.patch_filament.side_effect = SpoolmanUnavailableError("down")
        resp = await async_client.patch(f"{FILAMENT_URL}/7", json={"material_number": "5"})
        assert resp.status_code == 503

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_patch_broadcasts_inventory_changed(self, async_client, spoolman_settings, filament_client):
        # Open Inventory pages refetch on this, like after a spool write.
        with patch("backend.app.api.routes.spoolman_inventory.ws_manager") as mock_ws:
            mock_ws.broadcast = AsyncMock()
            resp = await async_client.patch(f"{FILAMENT_URL}/7", json={"material_number": "5"})
        assert resp.status_code == 200
        mock_ws.broadcast.assert_awaited_once_with({"type": "inventory_changed"})

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_failed_patch_does_not_broadcast(self, async_client, spoolman_settings, filament_client):
        from backend.app.services.spoolman import SpoolmanUnavailableError

        filament_client.patch_filament.side_effect = SpoolmanUnavailableError("down")
        with patch("backend.app.api.routes.spoolman_inventory.ws_manager") as mock_ws:
            mock_ws.broadcast = AsyncMock()
            resp = await async_client.patch(f"{FILAMENT_URL}/7", json={"material_number": "5"})
        assert resp.status_code == 503
        mock_ws.broadcast.assert_not_called()
