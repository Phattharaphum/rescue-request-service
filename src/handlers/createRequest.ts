import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import { v4 as uuidv4 } from 'uuid';
import { validateCreateRequest } from '../utils/validation';
import { parseBody, success, error } from '../utils/http';
import { generateIdempotencyKey, checkIdempotency } from '../domain/idempotency';
import { isDuplicate } from '../domain/dedupe';
import { isDomainError } from '../domain/errors';
import { RescueRequestStatus } from '../domain/models';
import { createRequest, getRequestByIdempotencyKey, searchByIncidentId } from '../adapters/dynamodb';
import { publishCreated } from '../adapters/sns';
import { getIncident } from '../adapters/incidentClient';
import { logger } from '../utils/logger';

export async function handler(event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> {
  try {
    const rawBody = parseBody(event);
    const input = validateCreateRequest(rawBody);

    const idempotencyKey = generateIdempotencyKey(input);

    // Strong idempotency check
    const existing = await getRequestByIdempotencyKey(idempotencyKey, input.incidentId);
    const idempotentResult = checkIdempotency(idempotencyKey, existing);
    if (idempotentResult) {
      logger.info('Returning idempotent response', { requestId: idempotentResult.requestId });
      return success(200, idempotentResult);
    }

    // Weak duplicate check
    const existingRequests = await searchByIncidentId(input.incidentId);
    if (isDuplicate(input, existingRequests)) {
      return error(409, 'CONFLICT', 'A similar rescue request was already submitted within the last 5 minutes.');
    }

    // Validate incident exists
    await getIncident(input.incidentId);

    const now = new Date().toISOString();
    const newRequest = {
      requestId: uuidv4(),
      incidentId: input.incidentId,
      requesterName: input.requesterName,
      description: input.description,
      location: input.location,
      status: RescueRequestStatus.PENDING,
      version: 1,
      createdAt: now,
      updatedAt: now,
      idempotencyKey,
    };

    const created = await createRequest(newRequest);
    await publishCreated(created);

    logger.info('Rescue request created', { requestId: created.requestId });
    return success(201, created);
  } catch (err) {
    if (isDomainError(err)) {
      return error(err.statusCode, err.code, err.message);
    }
    if (err instanceof Error && err.message === 'Request body is required') {
      return error(400, 'VALIDATION_ERROR', err.message);
    }
    if (err instanceof SyntaxError) {
      return error(400, 'VALIDATION_ERROR', 'Invalid JSON in request body');
    }
    logger.error('Unhandled error in createRequest', { message: (err as Error).message });
    return error(500, 'INTERNAL_ERROR', 'An unexpected error occurred');
  }
}
