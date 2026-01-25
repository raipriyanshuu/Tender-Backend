import express from "express";
import multer from "multer";
import crypto from "crypto";
import path from "path";
import fs from "fs/promises";
import { query } from "../db.js";
import { uploadRateLimiter } from "../middleware/rateLimiter.js";

const router = express.Router();

const MAX_FILE_SIZE_MB = Number(process.env.MAX_FILE_SIZE_MB || "100");
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

const upload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: MAX_FILE_SIZE_BYTES,
  },
}); 

const STORAGE_BASE_PATH =
  process.env.STORAGE_BASE_PATH || path.join(process.cwd(), "shared");
const STORAGE_UPLOADS_DIR = process.env.STORAGE_UPLOADS_DIR || "uploads";

router.post("/upload-tender", uploadRateLimiter, upload.single("file"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: "No file uploaded" });
    }

    if (!req.file.originalname.toLowerCase().endsWith(".zip")) {
      return res.status(400).json({ error: "Only .zip files are supported" });
    }

    if (req.file.size > MAX_FILE_SIZE_BYTES) {
      return res.status(400).json({ 
        error: `File size exceeds maximum limit of ${MAX_FILE_SIZE_MB}MB`,
        max_size_mb: MAX_FILE_SIZE_MB,
        file_size_mb: Math.round(req.file.size / (1024 * 1024)),
      });
    }

    const batchId = `batch_${crypto.randomUUID()}`;
    const uploadsPath = path.join(STORAGE_BASE_PATH, STORAGE_UPLOADS_DIR);
    await fs.mkdir(uploadsPath, { recursive: true });

    const fileName = `${batchId}.zip`;
    const fullPath = path.join(uploadsPath, fileName);
    await fs.writeFile(fullPath, req.file.buffer);

    const relativeZipPath = path.join(STORAGE_UPLOADS_DIR, fileName);

    await query(
      `
      INSERT INTO processing_jobs (batch_id, zip_path, status, uploaded_by)
      VALUES ($1, $2, $3, $4)
      `,
      [batchId, relativeZipPath, "queued", req.body?.uploaded_by || null]
    );

    res.json({ success: true, batch_id: batchId });
  } catch (err) {
    console.error("Upload error:", err.message);
    if (err.code === "LIMIT_FILE_SIZE") {
      return res.status(400).json({ 
        error: `File size exceeds maximum limit of ${MAX_FILE_SIZE_MB}MB`,
        max_size_mb: MAX_FILE_SIZE_MB,
      });
    }
    res.status(500).json({ error: "Upload failed", details: err.message });
  }
});

export default router;
