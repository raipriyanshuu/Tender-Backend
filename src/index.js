import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import tendersRouter from './routes/tenders.js';
import uploadRoutes from './routes/upload.js';

// Load environment variables
dotenv.config();

const app = express();
const PORT = process.env.PORT || 3001;
const CORS_ORIGIN = process.env.CORS_ORIGIN || 'http://localhost:5173';

// Middleware - Allow multiple origins for development
app.use(cors({
  origin: [
    'http://localhost:5173',
    'http://localhost:3000',
    'https://tenderfrontend-three.vercel.app'
  ],
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: true
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
app.use('/api/tenders', tendersRouter);

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

// Start server
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
