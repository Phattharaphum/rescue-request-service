import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import { handler as createRequestHandler } from './handlers/createRequest';
import { handler as getRequestHandler } from './handlers/getRequest';
import { handler as searchRequestsHandler } from './handlers/searchRequests';
import { handler as patchStatusHandler } from './handlers/patchStatus';
import { error } from './utils/http';
import { logger } from './utils/logger';

export async function handler(event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> {
  const { httpMethod, resource } = event;

  logger.info('Incoming request', { httpMethod, resource });

  if (resource === '/v1/requests') {
    if (httpMethod === 'POST') return createRequestHandler(event);
    if (httpMethod === 'GET') return searchRequestsHandler(event);
  }

  if (resource === '/v1/requests/{id}') {
    if (httpMethod === 'GET') return getRequestHandler(event);
  }

  if (resource === '/v1/requests/{id}/status') {
    if (httpMethod === 'PATCH') return patchStatusHandler(event);
  }

  logger.warn('Route not found', { httpMethod, resource });
  return error(404, 'NOT_FOUND', `Route ${httpMethod} ${resource} not found`);
}
