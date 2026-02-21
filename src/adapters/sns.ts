import { SNSClient, PublishCommand } from '@aws-sdk/client-sns';
import { v4 as uuidv4 } from 'uuid';
import { config } from '../config/env';
import { RescueRequest, RescueRequestStatus } from '../domain/models';
import { logger } from '../utils/logger';

const snsClient = new SNSClient({ region: config.AWS_REGION });

export async function publishCreated(request: RescueRequest): Promise<void> {
  const event = {
    eventId: uuidv4(),
    eventType: 'rescue.request.created.v1',
    version: '1',
    timestamp: new Date().toISOString(),
    payload: {
      requestId: request.requestId,
      incidentId: request.incidentId,
      requesterName: request.requesterName,
      status: request.status,
      createdAt: request.createdAt,
    },
  };

  await snsClient.send(
    new PublishCommand({
      TopicArn: config.SNS_TOPIC_ARN_CREATED,
      Message: JSON.stringify(event),
      MessageAttributes: {
        eventType: {
          DataType: 'String',
          StringValue: event.eventType,
        },
      },
    }),
  );

  logger.info('Published rescue.request.created.v1', { requestId: request.requestId });
}

export async function publishStatusChanged(
  requestId: string,
  previousStatus: RescueRequestStatus,
  newStatus: RescueRequestStatus,
  reason: string | undefined,
): Promise<void> {
  const event = {
    eventId: uuidv4(),
    eventType: 'rescue.request.status-changed.v1',
    version: '1',
    timestamp: new Date().toISOString(),
    payload: {
      requestId,
      previousStatus,
      newStatus,
      reason: reason ?? null,
      changedAt: new Date().toISOString(),
    },
  };

  await snsClient.send(
    new PublishCommand({
      TopicArn: config.SNS_TOPIC_ARN_STATUS_CHANGED,
      Message: JSON.stringify(event),
      MessageAttributes: {
        eventType: {
          DataType: 'String',
          StringValue: event.eventType,
        },
      },
    }),
  );

  logger.info('Published rescue.request.status-changed.v1', { requestId, newStatus });
}
