import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import { parseQueryParam, success, error } from '../utils/http';
import { searchByIncidentId } from '../adapters/dynamodb';
import { isDomainError } from '../domain/errors';
import { logger } from '../utils/logger';

export async function handler(event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> {
  try {
    const incidentId = parseQueryParam(event, 'incidentId');

    if (!incidentId) {
      return error(400, 'VALIDATION_ERROR', 'Query parameter "incidentId" is required');
    }

    const requests = await searchByIncidentId(incidentId);
    return success(200, requests);
  } catch (err) {
    if (isDomainError(err)) {
      return error(err.statusCode, err.code, err.message);
    }
    logger.error('Unhandled error in searchRequests', { message: (err as Error).message });
    return error(500, 'INTERNAL_ERROR', 'An unexpected error occurred');
  }
}
