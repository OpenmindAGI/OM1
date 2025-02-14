from simulators.base import Simulator, SimulatorConfig


def test_simulator_init():
    """Test simulator initialization with config."""
    config = SimulatorConfig(name="test_sim")
    simulator = Simulator(config)
    assert simulator.name == "test_sim"
    assert simulator.config == config


def test_simulator_init_default_name():
    """Test simulator initialization with default name."""
    config = SimulatorConfig()
    simulator = Simulator(config)
    assert simulator.name == "Simulator"
    assert simulator.config == config


def test_simulator_config_kwargs():
    """Test simulator config with additional kwargs."""
    config = SimulatorConfig(name="test_sim", host="localhost", port=8000)
    assert config.name == "test_sim"
    assert config.host == "localhost"
    assert config.port == 8000
