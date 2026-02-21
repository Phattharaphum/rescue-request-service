import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import { parsePathParam, success, error } from '../utils/http';
import { getRequest } from '../adapters/dynamodb';
import { isDomainError, NotFoundError } from '../domain/errors';
import { logger } from '../utils/logger';

export async function handler(event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> {
  try {
    const requestId = parsePathParam(event, 'id');
    const request = await getRequest(requestId);

    if (!request) {
      throw new NotFoundError(`Rescue request ${requestId} not found`);
    }

    return success(200, request);
  } catch (err) {
    if (isDomainError(err)) {
      return error(err.statusCode, err.code, err.message);
    }
    if (err instanceof Error && err.message.startsWith('Missing path parameter')) {
      return error(400, 'VALIDATION_ERROR', err.message);
    }
    logger.error('Unhandled error in getRequest', { message: (err as Error).message });
    return error(500, 'INTERNAL_ERROR', 'An unexpected error occurred');
  }
}
