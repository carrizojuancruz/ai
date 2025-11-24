import pytest

from app.knowledge.utils import get_subcategory_for_s3_key, get_subcategory_for_url


@pytest.mark.unit
class TestGetSubcategoryForS3Key:

    def test_no_match_returns_empty(self):
        assert get_subcategory_for_s3_key("Other/file.md") == ""
        assert get_subcategory_for_s3_key("") == ""

    def test_partial_match_rejected(self):
        assert get_subcategory_for_s3_key("Prof/file.md") == ""


@pytest.mark.unit
class TestGetSubcategoryForUrl:

    def test_url_match(self):
        assert get_subcategory_for_url("https://example.com/12634022-see-how-you-re-doing-reports-made-simple") == "reports"

    def test_profile_url_match(self):
        assert get_subcategory_for_url("https://example.com/12770905-profile") == "profile"

    def test_no_match_returns_empty(self):
        assert get_subcategory_for_url("https://example.com/other") == ""
        assert get_subcategory_for_url("") == ""
