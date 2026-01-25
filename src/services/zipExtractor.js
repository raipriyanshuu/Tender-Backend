import path from "path";
import fs from "fs/promises";
import crypto from "crypto";
import { query } from "../db.js";

const STORAGE_BASE_PATH =
  process.env.STORAGE_BASE_PATH || path.join(process.cwd(), "shared");
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

  const zipPath = path.join(STORAGE_BASE_PATH, job.zip_path);
  const extractPath = path.join(STORAGE_BASE_PATH, STORAGE_EXTRACTED_DIR, batchId);

  console.log(`[ZipExtractor] ZIP path: ${zipPath}`);
  console.log(`[ZipExtractor] Extract to: ${extractPath}`);

  // Create extraction directory
  await fs.mkdir(extractPath, { recursive: true });

  // Extract ZIP (top-level)
  const AdmZip = (await import("adm-zip")).default;
  const zip = new AdmZip(zipPath);
  zip.extractAllTo(extractPath, true);
  console.log(`[ZipExtractor] ZIP extracted successfully`);

  // Walk directory recursively and extract nested ZIPs
  const discoveredFiles = await walkDirectory(extractPath, 0);
  const files = discoveredFiles.map((file) => {
    const ext = path.extname(file.filename).toLowerCase();
    return {
      filename: path.basename(file.filename),
      file_path: path.join(
        STORAGE_EXTRACTED_DIR,
        batchId,
        path.relative(extractPath, file.full_path)
      ),
      file_type: ext.substring(1),
    };
  });

  console.log(`[ZipExtractor] ${files.length} supported files found`);

  if (files.length === 0) {
    await query(
      "UPDATE processing_jobs SET status = $2, error_message = $3, updated_at = now() WHERE batch_id = $1",
      [batchId, "failed", "No supported files found in ZIP"]
    );
    throw new Error("No supported files found in ZIP");
  }

  // Create file_extraction records
  const runId = job.run_id || batchId;
  console.log(`[ZipExtractor] Creating file_extractions records with run_id: ${runId}`);

  for (const file of files) {
    const docId = `${batchId}_${crypto.randomUUID()}`;

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
      [docId, runId, file.filename, file.file_path, file.file_type, "pending", "upload"]
    );
    
    if (result.rows.length > 0) {
      console.log(`[ZipExtractor]   Created: ${docId} → ${file.filename}`);
    }
  }

  // Update batch with total files
  await query(
    "UPDATE processing_jobs SET total_files = $2, run_id = $3, status = $4, updated_at = now() WHERE batch_id = $1",
    [batchId, files.length, runId, "queued"]
  );

  console.log(`[ZipExtractor] Batch updated: total_files=${files.length}, run_id=${runId}, status=queued`);

  return { batch_id: batchId, total_files: files.length };
}
