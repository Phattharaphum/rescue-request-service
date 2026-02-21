import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import {
  DynamoDBDocumentClient,
  PutCommand,
  GetCommand,
  QueryCommand,
  UpdateCommand,
} from '@aws-sdk/lib-dynamodb';
import { config } from '../config/env';
import { RescueRequest, RescueRequestStatus } from '../domain/models';
import { OptimisticLockError } from '../domain/errors';

const dynamoClient = new DynamoDBClient({ region: config.AWS_REGION });
const docClient = DynamoDBDocumentClient.from(dynamoClient);

export async function createRequest(request: RescueRequest): Promise<RescueRequest> {
  await docClient.send(
    new PutCommand({
      TableName: config.DYNAMODB_TABLE_NAME,
      Item: request,
      ConditionExpression: 'attribute_not_exists(requestId)',
    }),
  );
  return request;
}

export async function getRequest(requestId: string): Promise<RescueRequest | null> {
  const result = await docClient.send(
    new GetCommand({
      TableName: config.DYNAMODB_TABLE_NAME,
      Key: { requestId },
    }),
  );
  return (result.Item as RescueRequest) ?? null;
}

export async function getRequestByIdempotencyKey(
  idempotencyKey: string,
  incidentId: string,
): Promise<RescueRequest | null> {
  const result = await docClient.send(
    new QueryCommand({
      TableName: config.DYNAMODB_TABLE_NAME,
      IndexName: 'incidentId-index',
      KeyConditionExpression: 'incidentId = :incidentId',
      FilterExpression: 'idempotencyKey = :idempotencyKey',
      ExpressionAttributeValues: {
        ':incidentId': incidentId,
        ':idempotencyKey': idempotencyKey,
      },
      Limit: 1,
    }),
  );
  const items = result.Items as RescueRequest[] | undefined;
  return items?.[0] ?? null;
}

export async function searchByIncidentId(incidentId: string): Promise<RescueRequest[]> {
  const result = await docClient.send(
    new QueryCommand({
      TableName: config.DYNAMODB_TABLE_NAME,
      IndexName: 'incidentId-index',
      KeyConditionExpression: 'incidentId = :incidentId',
      ExpressionAttributeValues: {
        ':incidentId': incidentId,
      },
    }),
  );
  return (result.Items as RescueRequest[]) ?? [];
}

export async function updateRequestStatus(
  requestId: string,
  newStatus: RescueRequestStatus,
  expectedVersion: number,
  updatedAt: string,
): Promise<RescueRequest> {
  try {
    const result = await docClient.send(
      new UpdateCommand({
        TableName: config.DYNAMODB_TABLE_NAME,
        Key: { requestId },
        UpdateExpression:
          'SET #status = :newStatus, #version = :newVersion, updatedAt = :updatedAt',
        ConditionExpression: '#version = :expectedVersion',
        ExpressionAttributeNames: {
          '#status': 'status',
          '#version': 'version',
        },
        ExpressionAttributeValues: {
          ':newStatus': newStatus,
          ':newVersion': expectedVersion + 1,
          ':expectedVersion': expectedVersion,
          ':updatedAt': updatedAt,
        },
        ReturnValues: 'ALL_NEW',
      }),
    );
    return result.Attributes as RescueRequest;
  } catch (err: unknown) {
    if (
      err instanceof Error &&
      err.name === 'ConditionalCheckFailedException'
    ) {
      throw new OptimisticLockError(
        `Version conflict updating request ${requestId}. The record was modified concurrently.`,
      );
    }
    throw err;
  }
}
