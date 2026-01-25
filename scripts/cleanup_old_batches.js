import fs from "fs/promises";
import path from "path";
import pg from "pg";

const { Pool } = pg;

const STORAGE_BASE_PATH =
  process.env.STORAGE_BASE_PATH || path.join(process.cwd(), "shared");
const STORAGE_EXTRACTED_DIR = process.env.STORAGE_EXTRACTED_DIR || "extracted";
const STORAGE_UPLOADS_DIR = process.env.STORAGE_UPLOADS_DIR || "uploads";
const RETENTION_DAYS = Number(process.env.BATCH_RETENTION_DAYS || "30");

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false },
});

async function safeRemove(targetPath) {
  try {
    await fs.rm(targetPath, { recursive: true, force: true });
  } catch (error) {
    console.error(`Failed to remove ${targetPath}:`, error.message);
  }
}

async function cleanup() {
  const client = await pool.connect();
  try {
    const result = await client.query(
      `
        SELECT batch_id, zip_path
        FROM processing_jobs
        WHERE completed_at IS NOT NULL
          AND completed_at < now() - $1::interval
      `,
      [`${RETENTION_DAYS} days`]
    );

    for (const row of result.rows) {
      const zipPath = row.zip_path
        ? path.join(STORAGE_BASE_PATH, row.zip_path)
        : null;
      const extractedPath = path.join(
        STORAGE_BASE_PATH,
        STORAGE_EXTRACTED_DIR,
        row.batch_id
      );

      if (zipPath) {
        await safeRemove(zipPath);
      }
      await safeRemove(extractedPath);
    }

    console.log(`Cleanup complete. Removed ${result.rowCount} batches.`);
  } finally {
    client.release();
    await pool.end();
  }
}

cleanup().catch((error) => {
  console.error("Cleanup failed:", error.message);
  process.exit(1);
});
