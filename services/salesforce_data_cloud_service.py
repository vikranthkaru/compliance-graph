from pathlib import Path

from config.loader import load_yaml
from salesforcecdpconnector.connection import SalesforceCDPConnection
from config.loader import load_yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def get_data_cloud_connection() -> SalesforceCDPConnection:
    """
    Creates and returns an authenticated Salesforce Data Cloud connection.
    """

    private_key_file = CONFIG_DIR / "salesforce.key"
    

    with open(private_key_file, "r") as f:
        private_key = f.read()


    config = load_yaml("config.yaml")
    sf_config = config["salesforce"]

    _connection = SalesforceCDPConnection(
        login_url=sf_config["login_url"],
        client_id=sf_config["connected_app"]["client_id"],
        username=sf_config["username"],
        private_key=private_key,
    )

    return _connection