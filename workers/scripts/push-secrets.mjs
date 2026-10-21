// .prod.vars(.dev.vars と同じ KEY=VALUE 形式)の値を `wrangler secret bulk` で
// Cloudflare に一括登録する。値は画面に表示しない。
//
// 使い方: npm run secrets:push            (.prod.vars を本番環境へ)
//         npm run secrets:push -- .dev.vars  (別ファイルを指定する場合)
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const REQUIRED = [
  "SPREADSHEET_ID",
  "GOOGLE_SERVICE_ACCOUNT_JSON",
  "DISCORD_BOT_TOKEN",
  "DISCORD_TASK_CHANNEL_ADMIN_ID",
  "DISCORD_TASK_CHANNEL_OFFICER_ID",
  "DISCORD_TASK_CHANNEL_MEMBER_ID",
];
const OPTIONAL = ["GOOGLE_CALENDAR_ID"];

const file = process.argv[2] ?? ".prod.vars";
const values = {};
for (const line of readFileSync(file, "utf8").split(/\r?\n/)) {
  const match = /^([A-Z0-9_]+)=(.*)$/.exec(line.trim());
  if (!match) continue;
  let value = match[2].trim();
  if (/^(['"]).*\1$/.test(value)) value = value.slice(1, -1);
  if (value) values[match[1]] = value;
}

const missing = REQUIRED.filter((key) => !values[key]);
if (missing.length > 0) {
  console.error(`${file} に未入力の必須項目があります: ${missing.join(", ")}`);
  process.exit(1);
}
try {
  JSON.parse(values.GOOGLE_SERVICE_ACCOUNT_JSON);
} catch {
  console.error("GOOGLE_SERVICE_ACCOUNT_JSON が正しいJSONではありません(1行のJSONで記入してください)");
  process.exit(1);
}

const secrets = Object.fromEntries([...REQUIRED, ...OPTIONAL].filter((k) => values[k]).map((k) => [k, values[k]]));
const dir = mkdtempSync(join(tmpdir(), "tc-secrets-"));
const jsonPath = join(dir, "secrets.json");
try {
  writeFileSync(jsonPath, JSON.stringify(secrets), { mode: 0o600 });
  console.log(`登録するキー: ${Object.keys(secrets).join(", ")}`);
  if (!secrets.GOOGLE_CALENDAR_ID) console.log("(GOOGLE_CALENDAR_ID は未入力のため、カレンダー同期はスキップされます)");
  const result = spawnSync("npx", ["wrangler", "secret", "bulk", jsonPath], { stdio: "inherit" });
  process.exitCode = result.status ?? 1;
} finally {
  rmSync(dir, { recursive: true, force: true });
}
