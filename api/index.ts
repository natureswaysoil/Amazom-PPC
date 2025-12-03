import { NestFactory } from '@nestjs/core';
import { AppModule } from '../src/app.module';
import serverless from 'serverless-http';
import * as express from 'express';
import { ExpressAdapter } from '@nestjs/platform-express';

let server: any;

async function bootstrap() {
  const expressApp = express();
  const adapter = new ExpressAdapter(expressApp);
  const app = await NestFactory.create(AppModule, adapter, { logger: false });
  // If you use a global prefix, adjust or remove this line:
  // app.setGlobalPrefix('api');
  await app.init();
  return serverless(expressApp);
}

export default async function handler(req: any, res: any) {
  if (!server) {
    server = await bootstrap();
  }
  return server(req, res);
}
