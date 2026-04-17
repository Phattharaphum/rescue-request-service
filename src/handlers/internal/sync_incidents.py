from src.application.usecases import sync_incident_catalog


def handler(event, context):
    return sync_incident_catalog.execute()
