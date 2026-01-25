import express from "express";
import { getQueueMetrics } from "../services/queueClient.js";

const router = express.Router();

router.get("/api/queue/metrics", async (req, res) => {
  try {
    const metrics = await getQueueMetrics();
    res.json({ success: true, metrics });
  } catch (error) {
    console.error("[QueueMetrics] Failed to fetch metrics:", error.message);
    res.status(500).json({ success: false, error: error.message });
  }
});

export default router;
