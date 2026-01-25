/**
 * Cloudflare R2 storage adapter for Node.js using AWS SDK v3
 */

import { S3Client, GetObjectCommand, PutObjectCommand, HeadObjectCommand, ListObjectsV2Command, DeleteObjectCommand } from '@aws-sdk/client-s3';
import { StorageAdapter } from './adapter.js';

export class R2StorageAdapter extends StorageAdapter {
    constructor(config) {
        super();
        this.bucketName = config.bucketName;
        this.environment = config.environment || 'prod';

        // Initialize S3 client with R2 endpoint
        this.s3Client = new S3Client({
            region: config.region || 'auto',
            endpoint: config.endpointUrl,
            credentials: {
                accessKeyId: config.accessKeyId,
                secretAccessKey: config.secretAccessKey,
            },
        });
    }

    _addEnvironmentPrefix(objectKey) {
        // Remove leading slashes
        const cleanKey = objectKey.replace(/^[/\\]+/, '');
        return `${this.environment}/${cleanKey}`;
    }

    _removeEnvironmentPrefix(fullKey) {
        const prefix = `${this.environment}/`;
        if (fullKey.startsWith(prefix)) {
            return fullKey.substring(prefix.length);
        }
        return fullKey;
    }

    async readFile(objectKey) {
        const fullKey = this._addEnvironmentPrefix(objectKey);
        try {
            const command = new GetObjectCommand({
                Bucket: this.bucketName,
                Key: fullKey,
            });
            const response = await this.s3Client.send(command);

            // Convert stream to buffer
            const chunks = [];
            for await (const chunk of response.Body) {
                chunks.push(chunk);
            }
            return Buffer.concat(chunks);
        } catch (error) {
            if (error.name === 'NoSuchKey') {
                throw new Error(`File not found in R2: ${objectKey}`);
            }
            throw new Error(`Failed to read from R2: ${objectKey} - ${error.message}`);
        }
    }

    async writeFile(objectKey, content) {
        const fullKey = this._addEnvironmentPrefix(objectKey);
        console.log(`[R2Adapter] Writing file to R2`);
        console.log(`[R2Adapter]   Object key: ${objectKey}`);
        console.log(`[R2Adapter]   Full key (with env): ${fullKey}`);
        console.log(`[R2Adapter]   Bucket: ${this.bucketName}`);
        console.log(`[R2Adapter]   Environment: ${this.environment}`);
        console.log(`[R2Adapter]   Size: ${Math.round(content.length / 1024)}KB`);

        try {
            const command = new PutObjectCommand({
                Bucket: this.bucketName,
                Key: fullKey,
                Body: content,
            });
            await this.s3Client.send(command);
            console.log(`[R2Adapter] ✅ File uploaded successfully to R2: ${fullKey}`);
        } catch (error) {
            console.error(`[R2Adapter] ❌ Failed to write to R2: ${objectKey}`);
            console.error(`[R2Adapter] Error details:`, error.message);
            console.error(`[R2Adapter] Error code:`, error.name);
            throw new Error(`Failed to write to R2: ${objectKey} - ${error.message}`);
        }
    }

    async fileExists(objectKey) {
        const fullKey = this._addEnvironmentPrefix(objectKey);
        try {
            const command = new HeadObjectCommand({
                Bucket: this.bucketName,
                Key: fullKey,
            });
            await this.s3Client.send(command);
            return true;
        } catch (error) {
            if (error.name === 'NotFound' || error.$metadata?.httpStatusCode === 404) {
                return false;
            }
            return false;
        }
    }

    async getFileSize(objectKey) {
        const fullKey = this._addEnvironmentPrefix(objectKey);
        try {
            const command = new HeadObjectCommand({
                Bucket: this.bucketName,
                Key: fullKey,
            });
            const response = await this.s3Client.send(command);
            return response.ContentLength;
        } catch (error) {
            if (error.name === 'NotFound' || error.$metadata?.httpStatusCode === 404) {
                throw new Error(`File not found in R2: ${objectKey}`);
            }
            throw new Error(`Failed to get file size from R2: ${objectKey} - ${error.message}`);
        }
    }

    async listFiles(prefix) {
        const fullPrefix = this._addEnvironmentPrefix(prefix);
        const files = [];

        try {
            let continuationToken = undefined;

            do {
                const command = new ListObjectsV2Command({
                    Bucket: this.bucketName,
                    Prefix: fullPrefix,
                    ContinuationToken: continuationToken,
                });

                const response = await this.s3Client.send(command);

                if (response.Contents) {
                    for (const obj of response.Contents) {
                        // Remove environment prefix from returned keys
                        const key = this._removeEnvironmentPrefix(obj.Key);
                        files.push(key);
                    }
                }

                continuationToken = response.NextContinuationToken;
            } while (continuationToken);

        } catch (error) {
            throw new Error(`Failed to list files in R2: ${prefix} - ${error.message}`);
        }

        return files;
    }

    async deleteFile(objectKey) {
        const fullKey = this._addEnvironmentPrefix(objectKey);
        try {
            const command = new DeleteObjectCommand({
                Bucket: this.bucketName,
                Key: fullKey,
            });
            await this.s3Client.send(command);
        } catch (error) {
            throw new Error(`Failed to delete file from R2: ${objectKey} - ${error.message}`);
        }
    }
}
