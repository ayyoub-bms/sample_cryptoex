import os
from dotenv import load_dotenv
from cryptoex import settings

# FIXME: Temporary -- make sure to have the env variables set
load_dotenv(os.path.join(settings.DATA_PATH, "api-keys"))


settings._setup_logging()
