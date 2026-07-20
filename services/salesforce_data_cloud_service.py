from config.loader import load_yaml
from config.security import get_private_key
from salesforcecdpconnector.connection import SalesforceCDPConnection



def get_data_cloud_connection() -> SalesforceCDPConnection:
    """
    Creates and returns an authenticated Salesforce Data Cloud connection.
    """
    config = load_yaml("config.yaml")
    sf_config = config["salesforce"]

    _connection = SalesforceCDPConnection(
        login_url=sf_config["login_url"],
        client_id=sf_config["connected_app"]["client_id"],
        username=sf_config["username"],
        private_key=get_private_key(),
    )

    return _connection