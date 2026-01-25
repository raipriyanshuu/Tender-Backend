/**
 * Storage factory - creates appropriate storage adapter based on configuration
 */

import path from 'path';
import { LocalStorageAdapter } from './localAdapter.js';
import { R2StorageAdapter } from './r2Adapter.js';

export function createStorageAdapter() {
    const storageBackend = process.env.STORAGE_BACKEND || 'local';

    console.log(`[StorageFactory] Creating storage adapter: ${storageBackend}`);

    if (storageBackend === 'local') {
        const basePath = process.env.STORAGE_BASE_PATH || path.join(process.cwd(), 'shared');
        console.log(`[StorageFactory] Local storage base path: ${basePath}`);
        return new LocalStorageAdapter(basePath);
    } else if (storageBackend === 'r2') {
        const accountId = process.env.R2_ACCOUNT_ID;
        const accessKeyId = process.env.R2_ACCESS_KEY_ID;
        const secretAccessKey = process.env.R2_SECRET_ACCESS_KEY;
        const bucketName = process.env.R2_BUCKET_NAME;
        const environment = process.env.STORAGE_ENVIRONMENT || 'prod';
        const region = process.env.R2_REGION || 'auto';

        console.log(`[StorageFactory] R2 Configuration:`);
        console.log(`[StorageFactory]   Account ID: ${accountId ? accountId.substring(0, 8) + '...' : 'NOT SET'}`);
        console.log(`[StorageFactory]   Access Key: ${accessKeyId ? accessKeyId.substring(0, 8) + '...' : 'NOT SET'}`);
        console.log(`[StorageFactory]   Bucket: ${bucketName || 'NOT SET'}`);
        console.log(`[StorageFactory]   Environment: ${environment}`);
        console.log(`[StorageFactory]   Region: ${region}`);

        // Construct endpoint URL if not provided
        let endpointUrl = process.env.R2_ENDPOINT_URL;
        if (!endpointUrl && accountId) {
            endpointUrl = `https://${accountId}.r2.cloudflarestorage.com`;
        }
        console.log(`[StorageFactory]   Endpoint: ${endpointUrl || 'NOT SET'}`);

        if (!accountId || !accessKeyId || !secretAccessKey || !bucketName) {
            console.error(`[StorageFactory] ❌ R2 configuration incomplete!`);
            console.error(`[StorageFactory] Missing: ${[
                !accountId && 'R2_ACCOUNT_ID',
                !accessKeyId && 'R2_ACCESS_KEY_ID',
                !secretAccessKey && 'R2_SECRET_ACCESS_KEY',
                !bucketName && 'R2_BUCKET_NAME'
            ].filter(Boolean).join(', ')}`);
            throw new Error('R2 configuration incomplete. Required: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME');
        }

        console.log(`[StorageFactory] ✅ R2 adapter created successfully`);
        return new R2StorageAdapter({
            accountId,
            accessKeyId,
            secretAccessKey,
            bucketName,
            endpointUrl,
            environment,
            region,
        });
    } else {
        console.error(`[StorageFactory] ❌ Unknown storage backend: ${storageBackend}`);
        throw new Error(`Unknown storage backend: ${storageBackend}`);
    }
}
