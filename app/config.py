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
    SUPABASE_URL        = os.getenv("SUPABASE_URL")
    SERVICE_ROLE_KEY    = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    OPENAI_API_KEY      = os.getenv("OPENAI_API_KEY")
    ELEVENLABS_API_KEY  = os.getenv("ELEVENLABS_API_KEY")
    ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")


class ProductionConfig(Config): pass
class DevelopConfig(Config):   DEBUG = True
class LocalConfig(Config):     DEBUG = True; TESTING = True


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
