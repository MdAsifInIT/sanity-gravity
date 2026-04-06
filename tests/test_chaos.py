def test_intentional_failure():
    """This test intentionally fails to verify the CI integration test gate."""
    print("Running chaos test...")
    assert False, "Test failed: CI integration test gate should have blocked this." 
