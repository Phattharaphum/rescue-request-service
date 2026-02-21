import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import { validatePatchStatus } from '../utils/validation';
import { parseBody, parsePathParam, success, error } from '../utils/http';
import { checkVersion } from '../domain/optimisticLock';
import { isValidTransition } from '../domain/workflow';
import { isDomainError, NotFoundError, InvalidTransitionError } from '../domain/errors';
import { getRequest, updateRequestStatus } from '../adapters/dynamodb';
import { publishStatusChanged } from '../adapters/sns';
import { logger } from '../utils/logger';

export async function handler(event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> {
  try {
    const requestId = parsePathParam(event, 'id');
    const rawBody = parseBody(event);
    const input = validatePatchStatus(rawBody);

    const existing = await getRequest(requestId);
    if (!existing) {
      throw new NotFoundError(`Rescue request ${requestId} not found`);
    }

    checkVersion(input.version, existing.version);

    if (!isValidTransition(existing.status, input.status)) {
      throw new InvalidTransitionError(
        `Cannot transition from ${existing.status} to ${input.status}`,
      );
    }

    const updatedAt = new Date().toISOString();
    const previousStatus = existing.status;
    const updated = await updateRequestStatus(
      requestId,
      input.status,
      input.version,
      updatedAt,
    );

    await publishStatusChanged(requestId, previousStatus, input.status, input.reason);

    logger.info('Rescue request status updated', {
      requestId,
      previousStatus,
      newStatus: input.status,
    });

    return success(200, updated);
  } catch (err) {
    if (isDomainError(err)) {
      return error(err.statusCode, err.code, err.message);
    }
    if (
      err instanceof Error &&
      (err.message === 'Request body is required' ||
        err.message.startsWith('Missing path parameter'))
    ) {
      return error(400, 'VALIDATION_ERROR', err.message);
    }
    if (err instanceof SyntaxError) {
      return error(400, 'VALIDATION_ERROR', 'Invalid JSON in request body');
    }
    logger.error('Unhandled error in patchStatus', { message: (err as Error).message });
    return error(500, 'INTERNAL_ERROR', 'An unexpected error occurred');
  }
}
