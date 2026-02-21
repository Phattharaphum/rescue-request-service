import { STATUS_TRANSITIONS } from '../config/constants';
import { RescueRequestStatus } from './models';

export function isValidTransition(
  from: RescueRequestStatus,
  to: RescueRequestStatus,
): boolean {
  const allowed = STATUS_TRANSITIONS[from];
  return allowed.includes(to);
}
