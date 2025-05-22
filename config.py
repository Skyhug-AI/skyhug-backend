import os
from dotenv import load_dotenv


env = os.getenv('ENVIRONMENT', 'local')

if env == 'local':
    load_dotenv('.env.local')
if env == 'develop':
    load_dotenv('.env.develop')
elif env == 'production':
    load_dotenv('.env.production')


class Config:
    DEBUG = False
    TESTING = False

    # AWS configuration
    SERVER_URL = os.getenv('SERVER_URL')
    FRONTEND_URL = os.getenv('FRONTEND_URL')

    AWS_REGION = os.getenv('AWS_REGION')
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_DYNAMODB_DATABASE_URI = os.getenv('AWS_DYNAMODB_DATABASE_URI')
    AWS_POSTGRES_DATABASE_URI = os.getenv('AWS_POSTGRES_DATABASE_URI')
    AWS_SES_SENDER_EMAIL = os.getenv('AWS_SES_SENDER_EMAIL')

    # Retell configuration
    RETELL_API_ENDPOINT = os.getenv('RETELL_API_ENDPOINT')
    RETELL_API_KEY = os.getenv('RETELL_API_KEY')

    # Thoughtly configuration
    THOUGHTLY_API_ENDPOINT = os.getenv('THOUGHTLY_API_ENDPOINT')
    THOUGHTLY_API_TOKEN = os.getenv('THOUGHTLY_API_TOKEN')
    THOUGHTLY_ACCOUNT_EMAIL = os.getenv('THOUGHTLY_ACCOUNT_EMAIL')
    THOUGHTLY_ACCOUNT_PASS = os.getenv('THOUGHTLY_ACCOUNT_PASS')

    JOTFORM_API_ENDPOINT = os.getenv('JOTFORM_API_ENDPOINT')
    JOTFORM_API_TOKEN = os.getenv('JOTFORM_API_TOKEN'),
    JOTFORM_FORM_ENDPOINT = os.getenv('JOTFORM_FORM_ENDPOINT')

    DESCOPE_PROJECT_ID = os.getenv('DESCOPE_PROJECT_ID')
    DESCOPE_MANAGEMENT_KEY = os.getenv('DESCOPE_MANAGEMENT_KEY')

    PUBLIC_KEY_FILENAME = os.getenv('PUBLIC_KEY_FILENAME')
    PRIVATE_KEY_FILENAME = os.getenv('PRIVATE_KEY_FILENAME')

    CALENDLY_CLIENT_ID = os.getenv('CALENDLY_CLIENT_ID')
    CALENDLY_CLIENT_SECRET = os.getenv('CALENDLY_CLIENT_SECRET')
    CALENDLY_WEBHOOK_SIGNING_KEY = os.getenv('CALENDLY_WEBHOOK_SIGNING_KEY')

    GOOGLE_OAUTH_CLIENT_ID = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
    GOOGLE_OAUTH_CLIENT_SECRET = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')

    REDIS_HOST=os.getenv('REDIS_HOST')
    REDIS_PORT=os.getenv('REDIS_PORT')


class ProductionConfig(Config):
    pass


class DevelopConfig(Config):
    DEBUG = True

class LocalConfig(Config):
    DEBUG = True
    TESTING = True


# Factory to return the appropriate configuration based on the environment
def get_config():
    if env == "production":
        return ProductionConfig()
    elif env == "develop":
        return DevelopConfig()
    elif env == "local":
        return LocalConfig()
    return Config()


# Global config instance based on the current environment
config = get_config()
