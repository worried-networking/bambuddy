"""Unit tests for material_number_matches: finding a spool by one material number."""

import pytest

from backend.app.services.material_number import material_number_matches


class TestMaterialNumberMatches:
    def test_whole_value(self):
        assert material_number_matches("9319236810491", "9319236810491")

    def test_entry_of_a_list(self):
        assert material_number_matches("15,9319236810491", "9319236810491")
        assert material_number_matches("15,9319236810491", "15")

    @pytest.mark.parametrize("stored", ["15;9319236810491", "15,9319236810491;77", "15, 9319236810491"])
    def test_comma_and_semicolon_separate_entries(self, stored):
        assert material_number_matches(stored, "9319236810491")

    def test_parts_and_search_value_are_trimmed(self):
        assert material_number_matches("  15 ,  9319236810491  ", "9319236810491")
        assert material_number_matches("15", "  15  ")

    def test_case_sensitive(self):
        assert material_number_matches("ab-1", "ab-1")
        assert not material_number_matches("AB-1", "ab-1")

    def test_no_substring(self):
        assert not material_number_matches("9319236810491", "931923681049")
        assert not material_number_matches("1,9319236810491", "931923681049")

    def test_space_is_not_a_separator(self):
        assert material_number_matches("PM 70820", "PM 70820")
        assert not material_number_matches("PM 70820", "PM")
        assert not material_number_matches("PM 70820", "70820")

    @pytest.mark.parametrize("stored", [None, "", ",,", " ; "])
    def test_empty_stored_never_matches(self, stored):
        assert not material_number_matches(stored, "15")
        assert not material_number_matches(stored, "")
