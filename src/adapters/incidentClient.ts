import axios, { AxiosError } from 'axios';
import { config } from '../config/env';
import { UnprocessableEntityError } from '../domain/errors';
import { logger } from '../utils/logger';

interface Incident {
  incidentId: string;
  [key: string]: unknown;
}

const httpClient = axios.create({
  baseURL: config.INCIDENT_SERVICE_URL,
  timeout: config.INCIDENT_SERVICE_TIMEOUT_MS,
});

export async function getIncident(incidentId: string): Promise<Incident> {
  try {
    const response = await httpClient.get<Incident>(`/incidents/${incidentId}`, {
      // one automatic retry on network-level error
      validateStatus: (status) => status < 500,
    });

    if (response.status === 404) {
      throw new UnprocessableEntityError(
        `Incident ${incidentId} does not exist or is not accessible.`,
      );
    }

    if (response.status !== 200) {
      throw new UnprocessableEntityError(
        `Unexpected response from Incident Service: HTTP ${response.status}`,
      );
    }

    return response.data;
  } catch (err) {
    if (err instanceof UnprocessableEntityError) {
      throw err;
    }

    const axiosErr = err as AxiosError;
    if (axiosErr.isAxiosError) {
      logger.warn('Incident Service request failed', {
        incidentId,
        message: axiosErr.message,
      });

      // Retry once on network error
      try {
        const retryResponse = await httpClient.get<Incident>(`/incidents/${incidentId}`);
        return retryResponse.data;
      } catch (retryErr) {
        throw new UnprocessableEntityError(
          `Unable to validate incident ${incidentId}: Incident Service unavailable.`,
        );
      }
    }

    throw err;
  }
}
