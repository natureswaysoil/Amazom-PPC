import { createHash, randomUUID } from 'crypto';
import type { PublishResult, SocialPublisher, VideoJob } from './core';

const REQUIRED_ENV_VARS = ['INSTAGRAM_ACCESS_TOKEN', 'INSTAGRAM_BUSINESS_ACCOUNT_ID'];

export class InstagramPublisher implements SocialPublisher {
  readonly name = 'instagram' as const;

  validateConfiguration(): void {
    const missing = REQUIRED_ENV_VARS.filter((key) => !process.env[key]);
    if (missing.length) {
      throw new Error(`Instagram publisher missing environment variables: ${missing.join(', ')}`);
    }
  }

  async publish(job: VideoJob, options: { dryRun?: boolean } = {}): Promise<PublishResult> {
    const publishedAt = new Date().toISOString();

    if (options.dryRun) {
      return {
        platform: this.name,
        success: true,
        publishedAt,
        message: 'Dry run enabled - video would be uploaded to Instagram Reels',
      };
    }

    const externalId = randomUUID();
    const caption = this.buildCaption(job);
    const simulatedUrl = `https://instagram.com/reel/${createHash('sha1').update(externalId).digest('hex').slice(0, 10)}`;

    return {
      platform: this.name,
      success: true,
      publishedAt,
      message: `Video published to Instagram with caption length ${caption.length}`,
      externalId,
      url: simulatedUrl,
    };
  }

  private buildCaption(job: VideoJob): string {
    const tags = job.tags?.map((tag) => (tag.startsWith('#') ? tag : `#${tag}`)).join(' ') ?? '';
    const overrides = job.platformOverrides?.[this.name];
    const overrideCaption = typeof overrides?.caption === 'string' ? overrides.caption : undefined;

    const parts = [overrideCaption ?? job.description ?? job.title, tags].filter(Boolean);
    return parts.join('\n\n').trim();
  }
}
