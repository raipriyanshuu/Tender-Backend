const fs = require("fs");
const { Client } = require("pg");

const env = fs.readFileSync(".env", "utf8");
const match = env.match(/DATABASE_URL=(.+)/);
if (!match) {
  console.error("DATABASE_URL not found");
  process.exit(1);
}
const dbUrl = match[1].trim();

const ids = [
  "batch_e91a5c71-b338-49b5-9572-552d6bd0c08e_881b3dc4-57b8-4001-8e35-cdb78bcf28bb",
  "batch_e91a5c71-b338-49b5-9572-552d6bd0c08e_06a739a0-fea9-47c6-b5fd-410da82cdf6c",
  "batch_e91a5c71-b338-49b5-9572-552d6bd0c08e_8ed1be4a-8c69-41f6-9bab-3fd05055e0ea",
  "batch_e91a5c71-b338-49b5-9572-552d6bd0c08e_62a4e9e7-a2eb-4c76-a164-3ddbbd81cf70",
  "batch_e91a5c71-b338-49b5-9572-552d6bd0c08e_5a089814-11ca-4fa5-9f63-6e0c300e8b30",
  "batch_e91a5c71-b338-49b5-9572-552d6bd0c08e_cb747e94-c216-4c43-bc00-c572b6bebffc",
  "batch_e91a5c71-b338-49b5-9572-552d6bd0c08e_a3434437-131c-4b67-9e36-97858792dd75",
  "batch_e91a5c71-b338-49b5-9572-552d6bd0c08e_82ce1143-99b4-4371-a73e-772617010a7c",
  "batch_e91a5c71-b338-49b5-9572-552d6bd0c08e_b805e875-8558-41da-8dd8-a40c55d041a0",
  "batch_e91a5c71-b338-49b5-9572-552d6bd0c08e_f8721284-b208-4c1b-8593-21012aa01476",
  "batch_e91a5c71-b338-49b5-9572-552d6bd0c08e_e766d242-5d18-4b65-a6c6-655baa91694b",
  "batch_e91a5c71-b338-49b5-9572-552d6bd0c08e_11eb2dd5-d3cf-4935-94e0-58b393b97c31",
  "batch_e91a5c71-b338-49b5-9572-552d6bd0c08e_0a8910b2-6699-4dfe-9342-5ea060d5bd65",
  "batch_e91a5c71-b338-49b5-9572-552d6bd0c08e_a0b54f93-054a-4e4c-83c7-db33bc2d1325",
  "batch_e91a5c71-b338-49b5-9572-552d6bd0c08e_66247002-e03f-4df5-a523-94e809dd5d80",
  "batch_e91a5c71-b338-49b5-9572-552d6bd0c08e_656676b6-6542-4cc5-abbd-0d3ca4913aed",
];

(async () => {
  const client = new Client({ connectionString: dbUrl });
  await client.connect();
  const res = await client.query(
    "SELECT doc_id, status, run_id, filename FROM file_extractions WHERE doc_id = ANY($1)",
    [ids]
  );
  console.log("Found rows:", res.rowCount);
  console.log(res.rows);

  const pending = await client.query(
    "SELECT status, count(1) AS count FROM file_extractions WHERE run_id = $1 GROUP BY status",
    ["batch_e91a5c71-b338-49b5-9572-552d6bd0c08e"]
  );
  console.log("Status counts for run_id:", pending.rows);
  await client.end();
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
