import { RescueRequestStatus } from '../domain/models';

export const STATUS_TRANSITIONS: Record<RescueRequestStatus, RescueRequestStatus[]> = {
  [RescueRequestStatus.PENDING]: [RescueRequestStatus.DISPATCHED, RescueRequestStatus.CANCELLED],
  [RescueRequestStatus.DISPATCHED]: [RescueRequestStatus.RESOLVED, RescueRequestStatus.CANCELLED],
  [RescueRequestStatus.RESOLVED]: [],
  [RescueRequestStatus.CANCELLED]: [],
};
