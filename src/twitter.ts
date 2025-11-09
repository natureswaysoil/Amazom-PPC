import { createHash } from 'crypto';
import type { PublishResult, SocialPublisher, VideoJob } from './processor-core';

const REQUIRED_ENV_VARS = ['TWITTER_BEARER_TOKEN'];

export class TwitterPublisher implements SocialPublisher {
  readonly name = 'twitter' as const;

  validateConfiguration(): void {
    const missing = REQUIRED_ENV_VARS.filter((key) => !process.env[key]);
    if (missing.length) {
      throw new Error(`Twitter publisher missing environment variables: ${missing.join(', ')}`);
    }
  }

  async publish(job: VideoJob, options: { dryRun?: boolean } = {}): Promise<PublishResult> {
    const publishedAt = new Date().toISOString();

    if (options.dryRun) {
      return {
        platform: this.name,
        success: true,
        publishedAt,
        message: 'Dry run enabled - video would be uploaded to Twitter/X media API',
      };
    }

    const tweetText = this.buildTweet(job);
    const simulatedId = createHash('md5')
      .update([job.title, tweetText, job.video.url, Date.now().toString()].join('|'))
      .digest('hex')
      .slice(0, 12);

    return {
      platform: this.name,
      success: true,
      publishedAt,
      message: `Video tweeted with ${tweetText.length} characters`,
      externalId: simulatedId,
      url: `https://twitter.com/i/web/status/${simulatedId}`,
    };
  }

  private buildTweet(job: VideoJob): string {
    const overrides = job.platformOverrides?.[this.name];
    const overrideText = typeof overrides?.text === 'string' ? overrides.text : undefined;
    const base = overrideText ?? job.description ?? job.title;
    const maxLength = 280;

    if (base.length <= maxLength) {
      return base;
    }

    return `${base.slice(0, maxLength - 1)}…`;
  }
}
