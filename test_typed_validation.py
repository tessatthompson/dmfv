#!/usr/bin/env python3
"""Integration test for typed Pydantic validation."""
import asyncio
import sys
from pathlib import Path

from pydantic import ValidationError

from dmfv.proxy import versioned


async def test_basic_validation():
    """Test basic input/output validation."""
    print("Test 1: Basic validation (v1.0.0)")
    repos_dir = Path("example/repos").resolve()  # Use absolute path

    async with versioned(repos_dir / "bar", version="1.0.0") as bar:
        # Check schemas are available
        assert "handler" in bar.schemas, "handler should be in schemas"
        assert "input" in bar.schemas["handler"], "input schema should exist"
        assert "output" in bar.schemas["handler"], "output schema should exist"

        # Call with valid input
        result = await bar.handler({"name": "test"})
        assert result["result"] == "bar: test", f"Expected 'bar: test', got {result['result']}"
        assert result["version"] == "1.0.0", f"Expected version 1.0.0, got {result['version']}"

        print("  ✓ Valid input works")


async def test_reserved_field_stripping():
    """Test that reserved fields are stripped before validation."""
    print("\nTest 2: Reserved field stripping")
    repos_dir = Path("example/repos").resolve()

    async with versioned(repos_dir / "bar", version="1.0.0") as bar:
        # Pre-validate should strip reserved fields
        validated = bar.handler.validate({"name": "test", "version": "1.0.0", "fallback": "2.0.0"})
        assert "version" not in validated, "version should be stripped"
        assert "fallback" not in validated, "fallback should be stripped"
        assert validated["name"] == "test", "name should be preserved"

        # Call with reserved fields should still work
        result = await bar.handler({"name": "test", "version": "1.0.0"})
        assert result["result"] == "bar: test"

        print("  ✓ Reserved fields stripped correctly")


async def test_validation_error_on_input():
    """Test that invalid input raises ValidationError."""
    print("\nTest 3: Validation error on invalid input")
    repos_dir = Path("example/repos").resolve()

    async with versioned(repos_dir / "bar", version="1.0.0") as bar:
        try:
            # Missing required field
            result = await bar.handler({})
            assert False, "Should have raised ValidationError"
        except ValidationError as e:
            print(f"  ✓ ValidationError raised: {e.error_count()} error(s)")
        except RuntimeError as e:
            # Runner wraps ValidationError in error dict
            if "ValidationError" in str(e):
                print(f"  ✓ ValidationError raised (wrapped in RuntimeError)")
            else:
                raise


async def test_version_differences():
    """Test that v1 and v2 have different schemas."""
    print("\nTest 4: Version schema differences")
    repos_dir = Path("example/repos").resolve()

    async with versioned(repos_dir / "bar", version="1.0.0") as bar_v1:
        v1_schema = bar_v1.schemas["handler"]["input"]
        v1_required = set(v1_schema.get("required", []))
        v1_props = set(v1_schema.get("properties", {}).keys())
        print(f"  v1.0.0 required: {v1_required}")
        print(f"  v1.0.0 props: {v1_props}")

    async with versioned(repos_dir / "bar", version="2.0.0") as bar_v2:
        v2_schema = bar_v2.schemas["handler"]["input"]
        v2_required = set(v2_schema.get("required", []))
        v2_props = set(v2_schema.get("properties", {}).keys())
        print(f"  v2.0.0 required: {v2_required}")
        print(f"  v2.0.0 props: {v2_props}")

        # v2 should have 'count' field
        assert "count" in v2_props, "v2 should have count field"

        # Test v2 with count
        result = await bar_v2.handler({"name": "test", "count": 3})
        assert result["result"] == "bat: testtesttest", f"Expected repeated name, got {result['result']}"

        print("  ✓ Version schemas differ correctly")


async def test_optional_pre_validation():
    """Test that caller can optionally pre-validate."""
    print("\nTest 5: Optional pre-validation")
    repos_dir = Path("example/repos").resolve()

    async with versioned(repos_dir / "bar", version="1.0.0") as bar:
        # Pre-validate
        validated = bar.handler.validate({"name": "test"})
        assert validated["name"] == "test"

        # Then call (subprocess validates again)
        result = await bar.handler(validated)
        assert result["result"] == "bar: test"

        print("  ✓ Pre-validation works")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("TYPED VALIDATION INTEGRATION TESTS")
    print("=" * 60)

    try:
        await test_basic_validation()
        await test_reserved_field_stripping()
        await test_validation_error_on_input()
        await test_version_differences()
        await test_optional_pre_validation()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
