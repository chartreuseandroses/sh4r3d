import pytest
from pydantic import ValidationError

from app.models import SlugCreate


class TestSlugCreate:
    def test_valid_min_length(self):
        s = SlugCreate(slug="abc")
        assert s.slug == "abc"

    def test_valid_max_length(self):
        s = SlugCreate(slug="a" * 62 + "bc")  # 64 chars
        assert len(s.slug) == 64

    def test_valid_with_hyphens(self):
        s = SlugCreate(slug="my-cool-slug")
        assert s.slug == "my-cool-slug"

    def test_valid_with_numbers(self):
        s = SlugCreate(slug="slug42")
        assert s.slug == "slug42"

    def test_valid_mixed(self):
        s = SlugCreate(slug="abc-123-xyz")
        assert s.slug == "abc-123-xyz"

    def test_too_short(self):
        with pytest.raises(ValidationError):
            SlugCreate(slug="ab")

    def test_too_long(self):
        with pytest.raises(ValidationError):
            SlugCreate(slug="a" * 65)

    def test_leading_hyphen(self):
        with pytest.raises(ValidationError):
            SlugCreate(slug="-my-slug")

    def test_trailing_hyphen(self):
        with pytest.raises(ValidationError):
            SlugCreate(slug="my-slug-")

    def test_uppercase(self):
        with pytest.raises(ValidationError):
            SlugCreate(slug="MySlug")

    def test_underscore(self):
        with pytest.raises(ValidationError):
            SlugCreate(slug="my_slug")

    def test_space(self):
        with pytest.raises(ValidationError):
            SlugCreate(slug="my slug")

    def test_empty(self):
        with pytest.raises(ValidationError):
            SlugCreate(slug="")
