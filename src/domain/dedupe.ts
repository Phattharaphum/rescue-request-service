import { RescueRequest } from './models';

const DUPLICATE_WINDOW_MS = 5 * 60 * 1000; // 5 minutes

export function isDuplicate(
  newRequest: { incidentId: string; requesterName: string },
  existingRequests: RescueRequest[],
): boolean {
  const now = Date.now();
  return existingRequests.some((existing) => {
    if (
      existing.incidentId !== newRequest.incidentId ||
      existing.requesterName !== newRequest.requesterName
    ) {
      return false;
    }
    const createdAt = new Date(existing.createdAt).getTime();
    return now - createdAt <= DUPLICATE_WINDOW_MS;
  });
}
