from flask import Flask
from apis import api
from containers import Container
from middlewares.logging import log_request_info, log_response_info
from extensions.db import db
from extensions.aws import init_aws
from extensions.descope import init_descope
from background.scheduler import start_scheduler
from extensions.dynamo import init_dynamo
from extensions.ses import init_ses
from extensions.casbin import init_casbin
from common.exceptions import handle_exceptions
from config import config
from flask_cors import CORS
import os
import logging

def create_app(log_request_info, log_response_info):
    app = Flask(__name__)

    # Determine the environment
    app.config.from_object(config)

    logging.info(f'environment: {os.getenv("ENVIRONMENT")}')

    app.config['SQLALCHEMY_DATABASE_URI'] = config.AWS_POSTGRES_DATABASE_URI

    db.init_app(app)
    with app.app_context():
        init_aws(app)
        init_dynamo(app)
        init_ses(app)
        init_descope(app)
        init_casbin(app)

    # Register the middleware
    app.before_request(log_request_info)
    app.after_request(log_response_info)

    with app.app_context():
        container = Container()
        container.init_resources()
        container.wire(modules=[
            'apis.health_check',
            'apis.account',
            'apis.doctor',
            'apis.patient',
            'apis.appointment',
            'apis.question',
            'apis.schedule',
            'apis.form_template',
            'apis.response',
            'apis.symptom_log',
            'apis.webhook',
            'apis.keys',
            'apis.calendly',
            'apis.thoughtly',
            'apis.llm',
            'background.scheduler'
        ])
        app.container = container

    api.init_app(app)

    with app.app_context():
        start_scheduler()

    # Enable CORS for the app, allowing localhost:3000
    # CORS(app, origins=["https://dev-app.zora-health.com", "https://app.zora-health.com", "http://localhost:3000", "http://localhost:8080"])
    CORS(app, origins="*")

    # @app.errorhandler(Exception)
    # def global_error_handler(e):
    #     return handle_exceptions(e)

    return app

application = create_app(log_request_info, log_response_info)

if __name__ == '__main__':
    application.run(port=8000)
