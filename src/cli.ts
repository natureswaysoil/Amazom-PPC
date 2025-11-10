#!/usr/bin/env node
import { createDefaultProcessor, loadJobFromFile, PlatformName } from './core';

interface CliOptions {
  jobFile: string;
  dryRun: boolean;
  platforms?: PlatformName[];
}

function parseArguments(argv: string[]): CliOptions {
  const options: CliOptions = {
    jobFile: '',
    dryRun: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === '--job' || value === '-j') {
      options.jobFile = argv[++index] ?? '';
    } else if (value === '--dry-run') {
      options.dryRun = true;
    } else if (value === '--platforms' || value === '-p') {
      const next = argv[++index];
      if (!next) {
        throw new Error('Missing value for --platforms argument');
      }
      options.platforms = next.split(',').map((platform) => platform.trim().toLowerCase() as PlatformName);
    } else if (value === '--help' || value === '-h') {
      printUsage();
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${value}`);
    }
  }

  if (!options.jobFile) {
    throw new Error('A job definition JSON file must be provided with --job <path>');
  }

  return options;
}

function printUsage(): void {
  const usage = `Video Processor CLI\n\n` +
    `Usage:\n  video-processor --job <file> [--platforms instagram,twitter] [--dry-run]\n\n` +
    `Options:\n` +
    `  --job, -j         Path to a JSON file describing the video job\n` +
    `  --platforms, -p   Comma separated list of platforms to publish to\n` +
    `  --dry-run         Validate inputs without performing network calls\n` +
    `  --help, -h        Display this help message\n`;
  console.log(usage);
}

async function main(): Promise<void> {
  try {
    const options = parseArguments(process.argv.slice(2));
    const job = await loadJobFromFile(options.jobFile);
    const processor = createDefaultProcessor();

    const report = await processor.publish(job, {
      dryRun: options.dryRun,
      platforms: options.platforms,
    });

    console.log(JSON.stringify(report, null, 2));
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}

void main();
