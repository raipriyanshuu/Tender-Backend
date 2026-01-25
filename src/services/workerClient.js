import axios from "axios";

const WORKER_API_URL = process.env.WORKER_API_URL || "http://localhost:8000";
const WORKER_TIMEOUT_MS = Number(process.env.WORKER_TIMEOUT_MS || "30000");

const axiosInstance = axios.create({
  baseURL: WORKER_API_URL,
  timeout: WORKER_TIMEOUT_MS,
  headers: {
    "Content-Type": "application/json",
  },
});

export const workerClient = {
  async healthCheck() {
    try {
      const response = await axiosInstance.get("/health", { timeout: 5000 });
      return response.data;
    } catch (error) {
      console.error(`[WorkerClient] Health check failed:`, error.message);
      if (error.code === 'ECONNREFUSED') {
        console.error(`[WorkerClient] Cannot connect to worker at ${WORKER_API_URL}`);
      }
      throw error;
    }
  },

  async processFile(docId) {
    try {
      const response = await axiosInstance.post("/process-file", {
        doc_id: docId,
      });
      return response.data;
    } catch (error) {
      console.error(`[WorkerClient] processFile failed for ${docId}:`);
      console.error(`  Message: ${error.message}`);
      if (error.response) {
        console.error(`  Status: ${error.response.status}`);
        console.error(`  Data: ${JSON.stringify(error.response.data).substring(0, 200)}`);
      } else if (error.code) {
        console.error(`  Code: ${error.code} (${error.code === 'ECONNREFUSED' ? 'Worker not reachable' : 'Network error'})`);
      }
      throw error;
    }
  },

  async aggregateBatch(batchId) {
    try {
      const response = await axiosInstance.post("/aggregate-batch", {
        batch_id: batchId,
      });
      return response.data;
    } catch (error) {
      console.error(`[WorkerClient] aggregateBatch failed for ${batchId}:`, error.message);
      if (error.response) {
        console.error(`  Status: ${error.response.status}`);
        console.error(`  Data: ${JSON.stringify(error.response.data).substring(0, 200)}`);
      }
      throw error;
    }
  },
};
