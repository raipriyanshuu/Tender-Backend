/**
 * Abstract storage adapter interface for Node.js backend
 */

export class StorageAdapter {
  /**
   * Read file contents from storage
   * @param {string} objectKey - Storage key (e.g., "extracted/batch_123/doc.pdf")
   * @returns {Promise<Buffer>} File contents as Buffer
   */
  async readFile(objectKey) {
    throw new Error('readFile() must be implemented');
  }

  /**
   * Write file contents to storage
   * @param {string} objectKey - Storage key (e.g., "uploads/batch_123.zip")
   * @param {Buffer} content - File contents as Buffer
   * @returns {Promise<void>}
   */
  async writeFile(objectKey, content) {
    throw new Error('writeFile() must be implemented');
  }

  /**
   * Check if file exists in storage
   * @param {string} objectKey - Storage key
   * @returns {Promise<boolean>} True if file exists
   */
  async fileExists(objectKey) {
    throw new Error('fileExists() must be implemented');
  }

  /**
   * Get file size in bytes
   * @param {string} objectKey - Storage key
   * @returns {Promise<number>} File size in bytes
   */
  async getFileSize(objectKey) {
    throw new Error('getFileSize() must be implemented');
  }

  /**
   * List files with given prefix
   * @param {string} prefix - Key prefix (e.g., "extracted/batch_123/")
   * @returns {Promise<string[]>} Array of object keys
   */
  async listFiles(prefix) {
    throw new Error('listFiles() must be implemented');
  }

  /**
   * Delete file from storage
   * @param {string} objectKey - Storage key
   * @returns {Promise<void>}
   */
  async deleteFile(objectKey) {
    throw new Error('deleteFile() must be implemented');
  }
}
