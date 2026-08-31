from src.minimal_cli import normalize


def test_normalize():
    assert normalize(" Hello ") == "hello"
