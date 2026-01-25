import rateLimit from "express-rate-limit";

const defaultHandler = (req, res) => {
  res.status(429).json({
    success: false,
    error: "Too many requests",
    message: "Please retry after some time.",
  });
};

export const uploadRateLimiter = rateLimit({
  windowMs: 60 * 60 * 1000,
  max: Number(process.env.UPLOAD_RATE_LIMIT_PER_HOUR || "10"),
  standardHeaders: true,
  legacyHeaders: false,
  handler: defaultHandler,
});

export const processRateLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: Number(process.env.PROCESS_RATE_LIMIT_PER_MINUTE || "5"),
  standardHeaders: true,
  legacyHeaders: false,
  handler: defaultHandler,
});
