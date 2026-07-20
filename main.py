from config.loader import load_yaml
from dotenv import load_dotenv

load_dotenv()
config = load_yaml("config.yaml")

print(config["salesforce"]["JWT_PRIVATE_KEY_BASE64"][:50])
from services.salesforce_service import get_salesforce_cloud_connection
sf = get_salesforce_cloud_connection()

print("Connected")
print(sf.sf_instance)
print(sf.session_id[:20])