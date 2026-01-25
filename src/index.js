import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';

import tendersRouter from './routes/tenders.js';
import uploadRoutes from './routes/upload.js';
import batchRoutes from './routes/batches.js';
import healthRoutes from './routes/health.js';
import monitoringRoutes from './routes/monitoring.js';
import queueRoutes from './routes/queue.js';

import pool from './db.js';

// Load env
dotenv.config();

const app = express();
const PORT = process.env.PORT || 3001;

/* ======================================================
   CORS CONFIG (FIXED FOR RENDER + VERCEL)
====================================================== */

const allowedOrigins = new Set([
  'http://localhost:5173',
  'http://localhost:3000',
  'http://localhost:5500',
  'http://127.0.0.1:5500',

  // stable production frontend (if you use it)
  'https://tenderautomation1.vercel.app',
]);

function isAllowedOrigin(origin) {
  // allow server-to-server, curl, postman
  if (!origin) return true;

  // exact match
  if (allowedOrigins.has(origin)) return true;

  // allow ONLY your Vercel preview deployments
  // example:
  // https://tenderautomation1-xxxxx-priyanshu-rais-projects-914bd8c2.vercel.app
  try {
    const { hostname } = new URL(origin);
    return hostname.endsWith('-priyanshu-rais-projects-914bd8c2.vercel.app');
  } catch {
    return false;
  }
}

app.use(
  cors({
    origin: (origin, cb) => {
      if (isAllowedOrigin(origin)) return cb(null, true);
      return cb(new Error(`CORS blocked for origin: ${origin}`));
    },
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization'],
  })
);

// preflight
app.options('*', cors());

/* ======================================================
   BODY PARSERS
====================================================== */

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

/* ======================================================
   REQUEST LOGGING
====================================================== */

app.use((req, res, next) => {
  console.log(`${new Date().toISOString()} - ${req.method} ${req.path}`);
  next();
});

/* ======================================================
   ROUTES
====================================================== */

app.use(uploadRoutes);
app.use(batchRoutes);
app.use('/api/tenders', tendersRouter);
app.use(healthRoutes);
app.use(monitoringRoutes);
app.use(queueRoutes);

app.get('/ping', (req, res) => {
  res.send('pong');
});

app.get('/', (req, res) => {
  res.json({
    name: 'Tender Backend API',
    version: '1.0.0',
    status: 'running',
    endpoints: {
      health: 'GET /health',
      tenders: 'GET /api/tenders',
      tenderDetails: 'GET /api/tenders/:tenderId',
      runs: 'GET /api/tenders/runs/list',
      runFiles: 'GET /api/tenders/runs/:runId/files',
    },
  });
});

/* ======================================================
   404 HANDLER
====================================================== */

app.use((req, res) => {
  res.status(404).json({
    success: false,
    error: 'Endpoint not found',
    path: req.path,
  });
});

/* ======================================================
   GLOBAL ERROR HANDLER
====================================================== */

app.use((err, req, res, next) => {
  console.error('Global error handler:', err.message);

  res.status(err.status || 500).json({
    success: false,
    error: err.message || 'Internal server error',
    ...(process.env.NODE_ENV === 'development' && { stack: err.stack }),
  });
});

/* ======================================================
   SERVER START + DB CHECK
====================================================== */

let server;

const startServer = async () => {
  try {
    await pool.query('SELECT 1');
    console.log('✅ Database connectivity verified on startup');
  } catch (error) {
    console.error('❌ Database connection failed on startup:', error.message);
    process.exit(1);
  }

  server = app.listen(PORT, () => {
    console.log(`
╔═══════════════════════════════════════════════════════╗
║                                                       ║
║   🚀 Tender Backend API                               ║
║                                                       ║
║   Port: ${PORT}                                       ║
║   Environment: ${process.env.NODE_ENV || 'development'}                          
║                                                       ║
╚═══════════════════════════════════════════════════════╝
`);
  });
};

startServer();

/* ======================================================
   GRACEFUL SHUTDOWN (FIXED)
====================================================== */

process.on('SIGTERM', () => {
  console.log('SIGTERM received: shutting down server...');
  if (server) {
    server.close(() => {
      console.log('HTTP server closed');
      process.exit(0);
    });
  } else {
    process.exit(0);
  }
});

process.on('SIGINT', () => {
  console.log('\nSIGINT received: exiting...');
  process.exit(0);
});

export default app;
