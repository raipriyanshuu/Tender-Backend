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

// Load environment variables
dotenv.config();

const app = express();
const PORT = process.env.PORT || 3001;
const CORS_ORIGIN = process.env.CORS_ORIGIN || 'http://localhost:5173';

// Middleware - Allow multiple origins for development
const allowedOrigins = new Set([
  'http://localhost:5173',
  'http://localhost:3000',
  'https://tenderautomation1.vercel.app',
  'http://127.0.0.1:5500',
  'http://localhost:5500',
]);

app.use(cors({
  origin: (origin, cb) => {
    // allow server-to-server / curl / postman (no Origin header)
    if (!origin) return cb(null, true);

    if (allowedOrigins.has(origin)) return cb(null, true);

    return cb(new Error(`CORS blocked for origin: ${origin}`), false);
  },
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
}));

app.options('*', cors());

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Request logging middleware
app.use((req, res, next) => {
  console.log(`${new Date().toISOString()} - ${req.method} ${req.path}`);
  next();
});




// Routes
app.use(uploadRoutes);
app.use(batchRoutes);
app.use('/api/tenders', tendersRouter);
app.use(healthRoutes);
app.use(monitoringRoutes);
app.use(queueRoutes);


app.get('/ping', (req, res) => {
  res.send('pong');
});

// Root endpoint
app.get('/', (req, res) => {
  res.json({
    name: 'Tender Backend API',
    version: '1.0.0',
    status: 'running',
    endpoints: {
      health: 'GET /api/tenders/health',
      tenders: 'GET /api/tenders',
      tenderDetails: 'GET /api/tenders/:tenderId',
      runs: 'GET /api/tenders/runs/list',
      runFiles: 'GET /api/tenders/runs/:runId/files'
    }
  });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({
    success: false,
    error: 'Endpoint not found',
    path: req.path
  });
});

// Global error handler
app.use((err, req, res, next) => {
  console.error('Global error handler:', err);
  res.status(err.status || 500).json({
    success: false,
    error: err.message || 'Internal server error',
    ...(process.env.NODE_ENV === 'development' && { stack: err.stack })
  });
});

const startServer = async () => {
  try {
    await pool.query('SELECT 1');
    console.log('✅ Database connectivity verified on startup');
  } catch (error) {
    console.error('❌ Database connection failed on startup:', error.message);
    process.exit(1);
  }

  app.listen(PORT, () => {
    console.log(`
╔═══════════════════════════════════════════════════════╗
║                                                       ║
║   🚀 Tender Backend API Server                       ║
║                                                       ║
║   Server running on: http://localhost:${PORT}         ║
║   Environment: ${process.env.NODE_ENV || 'development'}                            ║
║   CORS Origin: ${CORS_ORIGIN}                        ║
║                                                       ║
║   API Documentation: http://localhost:${PORT}/         ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝
  `);
  });
};

// Start server
startServer();

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM signal received: closing HTTP server');
  app.close(() => {
    console.log('HTTP server closed');
    process.exit(0);
  });
});

process.on('SIGINT', () => {
  console.log('\nSIGINT signal received: closing HTTP server');
  process.exit(0);
});

export default app;
