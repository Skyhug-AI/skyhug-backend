from dependency_injector import containers, providers
from extensions.db import db
from services.llm.llm_client import OpenAIClient
from common.helpers import Logger
from repository.account import AccountRepository
from repository.doctor import DoctorRepository
from repository.patient import PatientRepository
from repository.question import QuestionRepository
from repository.question_response import QuestionResponseRepository
from repository.schedule import ScheduleRepository
from repository.schedule_response import ScheduleResponseRepository
from repository.symptom import SymptomRepository
from repository.symptom_log import SymptomLogRepository
from repository.audit_log import AuditLogRepository
from repository.role import RoleRepository
from repository.scheduled_question import ScheduledQuestionRepository
from repository.organization_patients_list import OrganizationPatientsListRepository
from redis import Redis
from config import config

from services.fhir.ehr_service_factory import EHRServiceFactory
from repository.form_template import FormTemplateRepository
from flask import current_app
from repository.job_queue import JobQueueRepository
from background.workflows.call_workflow import CallWorkflow
from background.workflows.sms_workflow import SMSWorkflow
from background.workflows.email_workflow import EmailWorkflow
from background.workflows.appointment_workflow import AppointmentWorkflow
from services.thoughtly.api import ThoughtlyService
from services.retell.api import RetellService
from services.jotform.api import JotformService
from services.calendly.api import CalendlyService
from services.google.google_calendar import GoogleCalendarService
from services.aws.simple_email_service import SimpleEmailService
from services.analytics.ops import AnalyticsOpsService
from services.notes.variants import NoteVariantsService
from services.llm.llm_service import LLMService
from services.llm.llm_client import LLMClient
from services.llm.llm_handler import LLMHandler
from services.llm.llm_utils import LLMCache
from services.llm.llm_advice_service import LLMAdviceService, LLMAdviceCache


class Container(containers.DeclarativeContainer):
    logger = providers.Resource(Logger)

    sqlalchemy_db = providers.Object(db)
    dynamo_client = providers.Resource(lambda: current_app.extensions['dynamo'].client)

    ses_client = providers.Resource(lambda: current_app.extensions['ses'].client)
    descope_client = providers.Resource(lambda: current_app.extensions['descope'].client)

    job_queue_repository = providers.Factory(
        JobQueueRepository,
        dynamo=dynamo_client
    )

    thoughtly_service = providers.Factory(ThoughtlyService)
    retell_service = providers.Factory(RetellService)

    jotform_service = providers.Factory(
        JotformService
    )

    google_calendar_service = providers.Factory(
        GoogleCalendarService
    )

    simple_email_service = providers.Factory(
        SimpleEmailService,
        simple_email_service=ses_client
    )

    open_ai_client = providers.Factory(
        OpenAIClient
    )

    analytics_ops_service = providers.Factory(
        AnalyticsOpsService,
        openai=open_ai_client
    )

    account_repository = providers.Factory(
        AccountRepository,
        db=sqlalchemy_db,
        descope=descope_client
    )

    doctor_repository = providers.Factory(
        DoctorRepository,
        db=sqlalchemy_db,
        descope=descope_client
    )

    organization_patients_list_repository = providers.Factory(
        OrganizationPatientsListRepository,
        db=sqlalchemy_db
    )

    role_repository = providers.Factory(
        RoleRepository,
        db=sqlalchemy_db
    )

    patient_repository = providers.Factory(
        PatientRepository,
        db=sqlalchemy_db
    )

    question_repository = providers.Factory(
        QuestionRepository,
        db=sqlalchemy_db
    )

    question_response_repository = providers.Factory(
        QuestionResponseRepository,
        db=sqlalchemy_db
    )

    schedule_repository = providers.Factory(
        ScheduleRepository,
        db=sqlalchemy_db,
        job_queue=job_queue_repository
    )

    scheduled_question_repository = providers.Factory(
        ScheduledQuestionRepository,
        db=sqlalchemy_db
    )

    form_template_repository = providers.Factory(
        FormTemplateRepository,
        db=sqlalchemy_db
    )

    schedule_response_repository = providers.Factory(
        ScheduleResponseRepository,
        db=sqlalchemy_db
    )

    symptom_repository = providers.Factory(
        SymptomRepository,
        db=sqlalchemy_db
    )

    symptom_log_repository = providers.Factory(
        SymptomLogRepository,
        db=sqlalchemy_db
    )

    ehr_service_factory = providers.Factory(
        EHRServiceFactory,
        db=sqlalchemy_db
    )

    note_variants_service = providers.Factory(
        NoteVariantsService,
        openai=open_ai_client
    )

    calendly_service = providers.Factory(
        CalendlyService,
        doctor_repository=doctor_repository
    )

    call_workflow = providers.Factory(
        CallWorkflow,
        job_queue=job_queue_repository,
        thoughtly_service=thoughtly_service,
        doctor_repository=doctor_repository,
        patient_repository=patient_repository,
        schedule_repository=schedule_repository,
        # response_repository=response_repository
    )

    sms_workflow = providers.Factory(
        SMSWorkflow,
        job_queue=job_queue_repository,
        thoughtly_service=thoughtly_service,
        doctor_repository=doctor_repository,
        patient_repository=patient_repository,
        schedule_repository=schedule_repository,
        schedule_response_repository=schedule_response_repository
    )

    email_workflow = providers.Factory(
        EmailWorkflow,
        job_queue=job_queue_repository,
        jotform_service=jotform_service,
        simple_email_service=simple_email_service,
        doctor_repository=doctor_repository,
        patient_repository=patient_repository,
        schedule_repository=schedule_repository,
        account_repository=account_repository,
        form_template_repository=form_template_repository,
        schedule_response_repository=schedule_response_repository,
        question_repository=question_repository
    )

    appointment_workflow = providers.Factory(
        AppointmentWorkflow,
        google_calendar_service=google_calendar_service,
        retell_service=retell_service,
        calendly_service=calendly_service,
        doctor_repository=doctor_repository
    )

    redis_client = providers.Factory(
        Redis, host=config.REDIS_HOST, port=config.REDIS_PORT, db=0
    )

    audit_log_repository = providers.Factory(
        AuditLogRepository
    )

    llm_client = providers.Factory(
        LLMClient,
        open_ai_client
    )

    llm_handler = providers.Factory(
        LLMHandler,
        llm_client
    )

    llm_cache = providers.Factory(
        LLMCache,
        redis_client,
        audit_log_repository
    )

    llm_advice_cache = providers.Factory(
        LLMAdviceCache,
        redis_client
    )

    llm_advice_service = providers.Factory(
        LLMAdviceService,
        llm_advice_cache
    )

    llm_service = providers.Factory(
        LLMService,
        llm_client,
        llm_handler,
        llm_cache,
        llm_advice_service,
        audit_log_repository
    )
