from backgrounds.base import Background, BackgroundConfig


def test_background_init():
    """Test background initialization with config."""
    config = BackgroundConfig(name="test_background")
    background = Background(config)
    assert background.name == "test_background"
    assert background.config == config


def test_background_init_default_name():
    """Test background initialization with default name."""
    config = BackgroundConfig()
    background = Background(config)
    assert background.name == "Background"
    assert background.config == config


def test_background_config_kwargs():
    """Test background config with additional kwargs."""
    config = BackgroundConfig(name="test_background", interval=10, retries=3)
    assert config.name == "test_background"
    assert config.interval == 10
    assert config.retries == 3
