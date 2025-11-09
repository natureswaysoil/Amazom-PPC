import { readFile } from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';
import { InstagramPublisher } from './instagram';
import { PinterestPublisher } from './pinterest';
import { TwitterPublisher } from './twitter';

export type PlatformName = 'instagram' | 'twitter' | 'pinterest';

export interface VideoJobAsset {
  url: string;
  mimeType?: string;
}

export interface VideoJob {
  id?: string;
  title: string;
  description?: string;
  video: VideoJobAsset;
  thumbnail?: VideoJobAsset;
  callToActionUrl?: string;
  tags?: string[];
  scheduledFor?: string;
  platformOverrides?: Partial<Record<PlatformName, Record<string, unknown>>>;
}

export interface PublishOptions {
  platforms?: PlatformName[];
  dryRun?: boolean;
}

export interface PublishResult {
  platform: PlatformName;
  success: boolean;
  publishedAt: string;
  message: string;
  externalId?: string;
  url?: string;
  error?: string;
}

export interface SocialPublisher {
  readonly name: PlatformName;
  publish(job: VideoJob, options: { dryRun?: boolean }): Promise<PublishResult>;
  validateConfiguration(): void;
}

export interface ProcessReport {
  job: VideoJob;
  startedAt: string;
  completedAt: string;
  results: PublishResult[];
  summary: {
    success: number;
    failure: number;
  };
}

export class VideoProcessor {
  private readonly publishers: Map<PlatformName, SocialPublisher>;

  constructor(publishers: SocialPublisher[]) {
    if (!publishers.length) {
      throw new Error('VideoProcessor requires at least one publisher instance');
    }

    this.publishers = new Map(publishers.map((publisher) => [publisher.name, publisher]));
  }

  getRegisteredPlatforms(): PlatformName[] {
    return Array.from(this.publishers.keys());
  }

  async publish(job: VideoJob, options: PublishOptions = {}): Promise<ProcessReport> {
    validateJob(job);

    const startedAt = new Date().toISOString();
    const platforms = options.platforms?.length
      ? options.platforms
      : this.getRegisteredPlatforms();

    const results: PublishResult[] = [];

    for (const platform of platforms) {
      const publisher = this.publishers.get(platform);
      if (!publisher) {
        results.push({
          platform,
          success: false,
          publishedAt: new Date().toISOString(),
          message: 'Platform not registered with processor',
          error: `Unknown platform: ${platform}`,
        });
        continue;
      }

      try {
        publisher.validateConfiguration();
        const result = await publisher.publish(job, { dryRun: options.dryRun });
        results.push(result);
      } catch (error) {
        results.push({
          platform,
          success: false,
          publishedAt: new Date().toISOString(),
          message: 'Failed to publish video',
          error: error instanceof Error ? error.message : String(error),
        });
      }
    }

    const completedAt = new Date().toISOString();
    const summary = results.reduce(
      (acc, result) => {
        if (result.success) {
          acc.success += 1;
        } else {
          acc.failure += 1;
        }
        return acc;
      },
      { success: 0, failure: 0 },
    );

    return {
      job,
      startedAt,
      completedAt,
      results,
      summary,
    };
  }
}

export function createDefaultProcessor(): VideoProcessor {
  return new VideoProcessor([
    new InstagramPublisher(),
    new PinterestPublisher(),
    new TwitterPublisher(),
  ]);
}

export async function loadJobFromFile(filePath: string): Promise<VideoJob> {
  if (!filePath) {
    throw new Error('A JSON job file path must be provided');
  }

  const resolvedPath = resolveFilePath(filePath);
  const raw = await readFile(resolvedPath, 'utf8');

  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch (error) {
    throw new Error(`Unable to parse job definition JSON: ${(error as Error).message}`);
  }

  if (!isVideoJob(data)) {
    throw new Error('Job definition JSON is missing required fields: title and video.url');
  }

  return normaliseJob(data);
}

function normaliseJob(job: VideoJob): VideoJob {
  return {
    ...job,
    id: job.id || `job_${Date.now()}`,
    title: job.title.trim(),
    description: job.description?.trim(),
    tags: job.tags?.map((tag) => tag.trim()).filter(Boolean),
  };
}

function resolveFilePath(filePath: string): string {
  if (path.isAbsolute(filePath)) {
    return filePath;
  }

  const cwdUrl = pathToFileUrl(process.cwd()).href;
  const resolved = new URL(filePath, cwdUrl);
  return fileURLToPath(resolved);
}

function pathToFileUrl(p: string): URL {
  let resolved = path.resolve(p);
  if (!resolved.startsWith('/')) {
    resolved = `/${resolved}`;
  }
  return new URL(`file://${resolved}`);
}

function isVideoJob(value: unknown): value is VideoJob {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const job = value as VideoJob;
  return Boolean(job.title && job.video && typeof job.video.url === 'string');
}

function validateJob(job: VideoJob): void {
  if (!job.title?.trim()) {
    throw new Error('Video job must include a title');
  }

  if (!job.video?.url?.trim()) {
    throw new Error('Video job must include a video.url property');
  }

  if (job.scheduledFor) {
    const timestamp = Date.parse(job.scheduledFor);
    if (Number.isNaN(timestamp)) {
      throw new Error(`Invalid scheduledFor timestamp: ${job.scheduledFor}`);
    }
  }
}
