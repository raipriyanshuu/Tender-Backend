/**
 * Local filesystem storage adapter for Node.js
 */

import fs from 'fs/promises';
import path from 'path';
import { StorageAdapter } from './adapter.js';

export class LocalStorageAdapter extends StorageAdapter {
    constructor(basePath) {
        super();
        this.basePath = basePath;
    }

    _resolvePath(objectKey) {
        // Remove leading slashes
        const cleanKey = objectKey.replace(/^[/\\]+/, '');
        return path.join(this.basePath, cleanKey);
    }

    async readFile(objectKey) {
        const filePath = this._resolvePath(objectKey);
        try {
            return await fs.readFile(filePath);
        } catch (error) {
            if (error.code === 'ENOENT') {
                throw new Error(`File not found: ${objectKey}`);
            }
            throw new Error(`Failed to read file: ${objectKey} - ${error.message}`);
        }
    }

    async writeFile(objectKey, content) {
        const filePath = this._resolvePath(objectKey);
        console.log(`[LocalAdapter] Writing file to local filesystem`);
        console.log(`[LocalAdapter]   Object key: ${objectKey}`);
        console.log(`[LocalAdapter]   Full path: ${filePath}`);
        console.log(`[LocalAdapter]   Size: ${Math.round(content.length / 1024)}KB`);

        try {
            // Create parent directories
            await fs.mkdir(path.dirname(filePath), { recursive: true });
            await fs.writeFile(filePath, content);
            console.log(`[LocalAdapter] ✅ File written successfully: ${filePath}`);
        } catch (error) {
            console.error(`[LocalAdapter] ❌ Failed to write file: ${objectKey}`);
            console.error(`[LocalAdapter] Error:`, error.message);
            throw new Error(`Failed to write file: ${objectKey} - ${error.message}`);
        }
    }

    async fileExists(objectKey) {
        const filePath = this._resolvePath(objectKey);
        try {
            const stats = await fs.stat(filePath);
            return stats.isFile();
        } catch (error) {
            return false;
        }
    }

    async getFileSize(objectKey) {
        const filePath = this._resolvePath(objectKey);
        try {
            const stats = await fs.stat(filePath);
            return stats.size;
        } catch (error) {
            if (error.code === 'ENOENT') {
                throw new Error(`File not found: ${objectKey}`);
            }
            throw new Error(`Failed to get file size: ${objectKey} - ${error.message}`);
        }
    }

    async listFiles(prefix) {
        const prefixPath = this._resolvePath(prefix);
        const files = [];

        try {
            const stats = await fs.stat(prefixPath);

            if (stats.isFile()) {
                files.push(prefix);
            } else if (stats.isDirectory()) {
                // Recursively list all files
                const walk = async (dir, baseDir) => {
                    const entries = await fs.readdir(dir, { withFileTypes: true });
                    for (const entry of entries) {
                        const fullPath = path.join(dir, entry.name);
                        if (entry.isFile()) {
                            const relativePath = path.relative(baseDir, fullPath);
                            files.push(relativePath.replace(/\\/g, '/'));
                        } else if (entry.isDirectory()) {
                            await walk(fullPath, baseDir);
                        }
                    }
                };
                await walk(prefixPath, this.basePath);
            }
        } catch (error) {
            // Return empty array if path doesn't exist
            return [];
        }

        return files;
    }

    async deleteFile(objectKey) {
        const filePath = this._resolvePath(objectKey);
        try {
            await fs.unlink(filePath);
        } catch (error) {
            if (error.code !== 'ENOENT') {
                throw new Error(`Failed to delete file: ${objectKey} - ${error.message}`);
            }
        }
    }
}
