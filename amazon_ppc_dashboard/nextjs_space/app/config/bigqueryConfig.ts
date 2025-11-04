import fs from 'fs';
import path from 'path';

export interface BigQueryConfig {
  projectId?: string;
  datasetId?: string;
  location?: string;
}

let cachedConfig: BigQueryConfig | null = null;
let attemptedLoad = false;

function normalizeBigQueryConfig(rawConfig: any): BigQueryConfig {
  if (!rawConfig || typeof rawConfig !== 'object') {
    return {};
  }

  return {
    projectId: rawConfig.projectId || rawConfig.project_id || undefined,
    datasetId: rawConfig.datasetId || rawConfig.dataset_id || undefined,
    location: rawConfig.location || undefined,
  };
}

export function loadBigQueryConfigFromFile(): BigQueryConfig {
  if (cachedConfig) {
    return cachedConfig;
  }

  if (attemptedLoad) {
    return {};
  }

  attemptedLoad = true;

  try {
    const configPath = path.join(process.cwd(), '..', '..', 'config.json');
    const fileContents = fs.readFileSync(configPath, 'utf-8');
    const parsedConfig = JSON.parse(fileContents);
    cachedConfig = normalizeBigQueryConfig(parsedConfig?.bigquery);
    return cachedConfig ?? {};
  } catch (error) {
    console.warn('Unable to load config.json for BigQuery defaults:', error);
    cachedConfig = {};
    return cachedConfig;
  }
}
