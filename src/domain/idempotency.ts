import { createHash } from 'crypto';
import { CreateRequestInput, RescueRequest } from './models';

export function generateIdempotencyKey(input: CreateRequestInput): string {
  const normalized = JSON.stringify({
    incidentId: input.incidentId.trim().toLowerCase(),
    requesterName: input.requesterName.trim().toLowerCase(),
    description: input.description.trim().toLowerCase(),
    location: input.location.trim().toLowerCase(),
  });
  return createHash('sha256').update(normalized).digest('hex');
}

export function checkIdempotency(
  key: string,
  existingRequest: RescueRequest | null,
): RescueRequest | null {
  if (existingRequest && existingRequest.idempotencyKey === key) {
    return existingRequest;
  }
  return null;
}
