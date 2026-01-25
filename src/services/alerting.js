import { query } from "../db.js";

const ALERT_COOLDOWN_MINUTES = Number(process.env.ALERT_COOLDOWN_MINUTES || "15");

export const AlertSeverity = {
  CRITICAL: "CRITICAL",
  WARNING: "WARNING",
  INFO: "INFO",
};

export async function createAlert(alertType, severity, message, context = {}) {
  const cooldownQuery = `
    SELECT created_at
    FROM system_alerts
    WHERE alert_type = $1 AND resolved_at IS NULL
    ORDER BY created_at DESC
    LIMIT 1
  `;
  const recent = await query(cooldownQuery, [alertType]);
  if (recent.rows[0]) {
    const createdAt = new Date(recent.rows[0].created_at);
    const elapsedMinutes = (Date.now() - createdAt.getTime()) / 60000;
    if (elapsedMinutes < ALERT_COOLDOWN_MINUTES) {
      return { created: false, reason: "cooldown" };
    }
  }

  await query(
    `
      INSERT INTO system_alerts (alert_type, severity, message, context)
      VALUES ($1, $2, $3, $4)
    `,
    [alertType, severity, message, context]
  );
  return { created: true };
}
