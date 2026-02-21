import { logger } from './logger';

export async function wrapWithTracing<T>(
  segmentName: string,
  fn: () => Promise<T>,
): Promise<T> {
  // Attempt to use AWS X-Ray if available; silently skip otherwise.
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const AWSXRay = require('aws-xray-sdk-core') as {
      getSegment: () => { addNewSubsegment: (name: string) => { close: () => void } };
    };
    const segment = AWSXRay.getSegment().addNewSubsegment(segmentName);
    try {
      const result = await fn();
      segment.close();
      return result;
    } catch (err) {
      segment.close();
      throw err;
    }
  } catch (requireErr) {
    // X-Ray SDK not available — execute without tracing
    logger.debug(`X-Ray tracing unavailable for segment "${segmentName}", skipping.`);
    return fn();
  }
}
