import { z } from 'zod';

const envSchema = z.object({
  AWS_REGION: z.string().default('us-east-1'),
  DYNAMODB_TABLE_NAME: z.string().min(1),
  SNS_TOPIC_ARN_CREATED: z.string().min(1),
  SNS_TOPIC_ARN_STATUS_CHANGED: z.string().min(1),
  INCIDENT_SERVICE_URL: z.string().url(),
  INCIDENT_SERVICE_TIMEOUT_MS: z
    .string()
    .optional()
    .transform((v) => (v ? parseInt(v, 10) : 3000)),
  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error']).default('info'),
});

function loadConfig() {
  const result = envSchema.safeParse(process.env);
  if (!result.success) {
    throw new Error(`Invalid environment configuration: ${result.error.message}`);
  }
  return result.data;
}

export type Config = z.infer<typeof envSchema>;
export const config: Config = loadConfig();
