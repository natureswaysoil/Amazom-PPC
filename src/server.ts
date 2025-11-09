import http from 'http';
import { createDefaultProcessor, PlatformName, PublishOptions, VideoJob } from './core';

export interface ServerConfig {
  port?: number;
}

function parseUrl(url: string | undefined): string {
  if (!url) {
    return '/';
  }

  try {
    const parsed = new URL(url, 'http://localhost');
    return parsed.pathname;
  } catch {
    return url;
  }
}

async function readJsonBody<T>(req: http.IncomingMessage): Promise<T> {
  const chunks: Buffer[] = [];

  for await (const chunk of req) {
    chunks.push(typeof chunk === 'string' ? Buffer.from(chunk) : chunk);
  }

  const payload = Buffer.concat(chunks).toString('utf8');
  if (!payload) {
    throw new Error('Request body is empty');
  }

  try {
    return JSON.parse(payload) as T;
  } catch (error) {
    throw new Error(`Unable to parse JSON body: ${(error as Error).message}`);
  }
}

export function createServer(config: ServerConfig = {}): http.Server {
  const processor = createDefaultProcessor();
  const server = http.createServer(async (req, res) => {
    const method = req.method ?? 'GET';
    const pathname = parseUrl(req.url);

    res.setHeader('Content-Type', 'application/json');

    if (method === 'GET' && pathname === '/health') {
      res.statusCode = 200;
      res.end(JSON.stringify({ status: 'ok', platforms: processor.getRegisteredPlatforms() }));
      return;
    }

    if (method === 'POST' && pathname === '/publish') {
      try {
        const body = await readJsonBody<{ job: VideoJob; options?: PublishOptions & { platforms?: PlatformName[] } }>(req);
        const report = await processor.publish(body.job, body.options);
        res.statusCode = 200;
        res.end(JSON.stringify(report));
      } catch (error) {
        res.statusCode = 400;
        res.end(JSON.stringify({ message: error instanceof Error ? error.message : String(error) }));
      }
      return;
    }

    res.statusCode = 404;
    res.end(JSON.stringify({ message: 'Not Found' }));
  });

  const port = config.port ?? Number(process.env.PORT ?? '8080');
  server.listen(port, () => {
    console.log(`Video processor listening on port ${port}`);
  });

  return server;
}

if (require.main === module) {
  createServer();
}
