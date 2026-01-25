import path from "path";
import fs from "fs/promises";
import os from "os";
import crypto from "crypto";
import { query } from "../db.js";
import { createStorageAdapter } from "../storage/index.js";

const STORAGE_EXTRACTED_DIR = process.env.STORAGE_EXTRACTED_DIR || "extracted";
const MAX_ZIP_DEPTH = Number(process.env.MAX_ZIP_DEPTH || "3");
const SUPPORTED_EXTENSIONS = [
  ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt",
  // GAEB formats
  ".x83", ".x84", ".x85", ".x86", ".x89",
  ".d83", ".d84", ".d85", ".d86", ".d89",
  ".p83", ".p84", ".p85", ".p86", ".p89",
  ".gaeb"
];

async function walkDirectory(dirPath, depth = 0) {
  if (depth > MAX_ZIP_DEPTH) {
    console.warn(`[ZipExtractor] Max ZIP depth reached at ${dirPath}`);
    return [];
  }

  const entries = await fs.readdir(dirPath, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await walkDirectory(fullPath, depth)));
      continue;
    }
    if (!entry.isFile()) {
      continue;
    }

    const ext = path.extname(entry.name).toLowerCase();
    if (ext === ".zip") {
      const nestedDir = path.join(
        path.dirname(fullPath),
        `${path.basename(entry.name, ".zip")}_zip`
      );
      await fs.mkdir(nestedDir, { recursive: true });
      const AdmZip = (await import("adm-zip")).default;
      const zip = new AdmZip(fullPath);
      zip.extractAllTo(nestedDir, true);
      console.log(`[ZipExtractor] Nested ZIP extracted: ${fullPath} → ${nestedDir}`);
      files.push(...(await walkDirectory(nestedDir, depth + 1)));
      continue;
    }

    if (SUPPORTED_EXTENSIONS.includes(ext)) {
      files.push({
        filename: entry.name,
        full_path: fullPath,
      });
    }
  }

  return files;
}

/**
 * Extract ZIP file and create file_extraction records
 */
export async function extractBatch(batchId) {
  console.log(`[ZipExtractor] Starting extraction for batch ${batchId}`);

  // Get batch job
  const jobResult = await query(
    "SELECT * FROM processing_jobs WHERE batch_id = $1",
    [batchId]
  );
  const job = jobResult.rows[0];
  if (!job) {
    throw new Error(`Batch not found: ${batchId}`);
  }

  console.log(`[ZipExtractor] Batch found, zip_path: ${job.zip_path}`);

  // Update status to extracting
  await query(
    "UPDATE processing_jobs SET status = $2, updated_at = now() WHERE batch_id = $1",
    [batchId, "extracting"]
  );

  // Create storage adapter
  const storage = createStorageAdapter();

  // Create temporary directory for extraction
  const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), `tender-extract-${batchId}-`));

  try {
    // Download ZIP from storage to temp file
    console.log(`[ZipExtractor] Downloading ZIP from storage: ${job.zip_path}`);
    const zipBuffer = await storage.readFile(job.zip_path);
    const tempZipPath = path.join(tempDir, `${batchId}.zip`);
    await fs.writeFile(tempZipPath, zipBuffer);
    console.log(`[ZipExtractor] ZIP downloaded to: ${tempZipPath}`);

    // Extract ZIP to temp directory
    const extractPath = path.join(tempDir, "extracted");
    await fs.mkdir(extractPath, { recursive: true });

    const AdmZip = (await import("adm-zip")).default;
    const zip = new AdmZip(tempZipPath);
    zip.extractAllTo(extractPath, true);
    console.log(`[ZipExtractor] ZIP extracted to: ${extractPath}`);

    // Walk directory recursively and extract nested ZIPs
    const discoveredFiles = await walkDirectory(extractPath, 0);
    console.log(`[ZipExtractor] ${discoveredFiles.length} supported files found`);

    if (discoveredFiles.length === 0) {
      await query(
        "UPDATE processing_jobs SET status = $2, error_message = $3, updated_at = now() WHERE batch_id = $1",
        [batchId, "failed", "No supported files found in ZIP"]
      );
      throw new Error("No supported files found in ZIP");
    }

    // Upload files to storage and create DB records
    const runId = job.run_id || batchId;
    console.log(`[ZipExtractor] Uploading ${discoveredFiles.length} files to storage...`);

    for (const file of discoveredFiles) {
      const docId = `${batchId}_${crypto.randomUUID()}`;

      // Calculate relative path within extracted directory
      const relativePath = path.relative(extractPath, file.full_path);

      // Construct storage key
      const storageKey = path.join(STORAGE_EXTRACTED_DIR, batchId, relativePath).replace(/\\/g, '/');

      // Read file and upload to storage
      const fileBuffer = await fs.readFile(file.full_path);
      await storage.writeFile(storageKey, fileBuffer);

      const ext = path.extname(file.filename).toLowerCase();
      const fileType = ext.substring(1); // Remove leading dot

      // Create DB record
      const result = await query(
        `
        INSERT INTO file_extractions (
          doc_id,
          run_id,
          filename,
          file_path,
          file_type,
          status,
          source
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (doc_id) DO NOTHING
        RETURNING id
        `,
        [docId, runId, file.filename, storageKey, fileType, "pending", "upload"]
      );

      if (result.rows.length > 0) {
        console.log(`[ZipExtractor]   Created: ${docId} → ${file.filename} (${storageKey})`);
      }
    }

    // Update batch with total files
    await query(
      "UPDATE processing_jobs SET total_files = $2, run_id = $3, status = $4, updated_at = now() WHERE batch_id = $1",
      [batchId, discoveredFiles.length, runId, "queued"]
    );

    console.log(`[ZipExtractor] Batch updated: total_files=${discoveredFiles.length}, run_id=${runId}, status=queued`);

    return { batch_id: batchId, total_files: discoveredFiles.length };

  } finally {
    // Clean up temp directory
    try {
      await fs.rm(tempDir, { recursive: true, force: true });
      console.log(`[ZipExtractor] Cleaned up temp directory: ${tempDir}`);
    } catch (cleanupError) {
      console.warn(`[ZipExtractor] Failed to clean up temp directory: ${cleanupError.message}`);
    }
  }
}
