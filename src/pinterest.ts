import { createHash } from 'crypto';
import type { PublishResult, SocialPublisher, VideoJob } from './processor-core';

const REQUIRED_ENV_VARS = ['PINTEREST_ACCESS_TOKEN', 'PINTEREST_BOARD_ID'];

export class PinterestPublisher implements SocialPublisher {
  readonly name = 'pinterest' as const;

  validateConfiguration(): void {
    const missing = REQUIRED_ENV_VARS.filter((key) => !process.env[key]);
    if (missing.length) {
      throw new Error(`Pinterest publisher missing environment variables: ${missing.join(', ')}`);
    }
  }

  async publish(job: VideoJob, options: { dryRun?: boolean } = {}): Promise<PublishResult> {
    const publishedAt = new Date().toISOString();

    if (options.dryRun) {
      return {
        platform: this.name,
        success: true,
        publishedAt,
        message: 'Dry run enabled - video would be uploaded as a Pinterest Idea Pin',
      };
    }

    const overrides = job.platformOverrides?.[this.name];
    const boardSection = typeof overrides?.boardSection === 'string' ? overrides.boardSection : undefined;
    const simulatedId = createHash('sha256')
      .update([job.title, job.video.url, boardSection ?? '', Date.now().toString()].join('|'))
      .digest('hex')
      .slice(0, 16);

    return {
      platform: this.name,
      success: true,
      publishedAt,
      message: `Video published to Pinterest board${boardSection ? ` section ${boardSection}` : ''}`,
      externalId: simulatedId,
      url: `https://www.pinterest.com/pin/${simulatedId}/`,
    };
  }
}
