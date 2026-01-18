import express from "express";
import multer from "multer";
import axios from "axios";
import FormData from "form-data";

const router = express.Router();
const upload = multer(); // memory storage

router.post("/upload-tender", upload.single("file"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: "No file uploaded" });
    }

    const form = new FormData();
    form.append("file", req.file.buffer, req.file.originalname);

    await axios.post(
      "https://pipemachine.app.n8n.cloud/webhook/tender-upload",
      form,
      { headers: form.getHeaders() }
    );

    res.json({ success: true });
  } catch (err) {
    console.error("Upload error:", err.message);
    res.status(500).json({ error: "Upload failed" });
  }
});

export default router;
