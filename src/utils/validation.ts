import { z } from 'zod';
import { RescueRequestStatus } from '../domain/models';
import { ValidationError } from '../domain/errors';

export const createRequestSchema = z.object({
  incidentId: z.string().min(1, 'incidentId is required'),
  requesterName: z.string().min(1, 'requesterName is required'),
  description: z.string().min(1, 'description is required'),
  location: z.string().min(1, 'location is required'),
});

export const patchStatusSchema = z.object({
  status: z.nativeEnum(RescueRequestStatus, {
    errorMap: () => ({
      message: `status must be one of: ${Object.values(RescueRequestStatus).join(', ')}`,
    }),
  }),
  reason: z.string().optional(),
  version: z.number().int().positive('version must be a positive integer'),
});

export function validateCreateRequest(data: unknown) {
  const result = createRequestSchema.safeParse(data);
  if (!result.success) {
    throw new ValidationError(result.error.errors.map((e) => e.message).join('; '));
  }
  return result.data;
}

export function validatePatchStatus(data: unknown) {
  const result = patchStatusSchema.safeParse(data);
  if (!result.success) {
    throw new ValidationError(result.error.errors.map((e) => e.message).join('; '));
  }
  return result.data;
}
