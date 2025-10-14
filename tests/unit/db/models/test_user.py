"""Unit tests for app.db.models.user module."""

from app.db.models.user import UserContextORM


class TestUserContextORM:
    """Tests for UserContextORM model."""

    def test_model_instantiation_with_basic_and_complex_fields(self):
        """Test model instantiation with basic and complex JSONB fields."""
        # Test basic fields
        basic_user = UserContextORM(
            email="test@example.com",
            preferred_name="Test User",
            language="en-US"
        )
        assert basic_user.email == "test@example.com"
        assert basic_user.preferred_name == "Test User"
        assert basic_user.language == "en-US"

        # Test complex fields (JSONB, arrays, numeric)
        complex_user = UserContextORM(
            email="complex@example.com",
            dependents=2,
            rent_mortgage=2000.0,
            social_signals_consent=True,
            age=30,
            money_feelings=["anxious", "hopeful"],
            expenses=[{"category": "rent", "amount": 2000}],
            identity={"gender": "non-binary"},
            goals=[{"type": "savings", "target": 10000}],
        )
        assert complex_user.email == "complex@example.com"
        assert complex_user.dependents == 2
        assert complex_user.rent_mortgage == 2000.0
        assert complex_user.age == 30
        assert len(complex_user.money_feelings) == 2
        assert complex_user.social_signals_consent is True

