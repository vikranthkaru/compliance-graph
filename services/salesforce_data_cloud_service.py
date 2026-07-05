from pathlib import Path

import yaml
from salesforcecdpconnector.connection import SalesforceCDPConnection


CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def get_data_cloud_connection() -> SalesforceCDPConnection:
    """
    Creates and returns an authenticated Salesforce Data Cloud connection.
    """

    config_file = CONFIG_DIR / "config.yaml"
    private_key_file = CONFIG_DIR / "salesforce.key"

    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

    with open(private_key_file, "r") as f:
        private_key = f.read()

    sf_config = config["salesforce"]

    _connection = SalesforceCDPConnection(
        login_url=sf_config["login_url"],
        client_id=sf_config["connected_app"]["client_id"],
        username=sf_config["username"],
        private_key=private_key,
    )

    return _connection