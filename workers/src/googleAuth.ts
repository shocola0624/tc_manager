// Cloudflare Workers には Node の `crypto` モジュールが無いため、サービスアカウントの
// JWT(RS256)署名は Web Crypto API(SubtleCrypto)で自前実装する(技術的な落とし穴として
// 事前に把握していた点)。

export interface ServiceAccount {
  client_email: string;
  private_key: string;
}

function base64UrlEncode(bytes: ArrayBuffer | Uint8Array): string {
  const array = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let binary = "";
  for (const byte of array) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function base64UrlEncodeString(value: string): string {
  return base64UrlEncode(new TextEncoder().encode(value));
}

/** "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n" (PKCS8/PEM) を
 * SubtleCrypto.importKey に渡せる ArrayBuffer(DER)に変換する。 */
function pemToDer(pem: string): ArrayBuffer {
  const base64 = pem
    .replace(/-----BEGIN PRIVATE KEY-----/, "")
    .replace(/-----END PRIVATE KEY-----/, "")
    .replace(/\s+/g, "");
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

async function importSigningKey(privateKeyPem: string): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "pkcs8",
    pemToDer(privateKeyPem),
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["sign"],
  );
}

/** サービスアカウントの秘密鍵で RS256 署名した JWT(アサーション)を作る。 */
export async function signServiceAccountJwt(
  serviceAccount: ServiceAccount,
  scopes: string[],
  options: { now?: number; expiresInSeconds?: number; audience?: string } = {},
): Promise<string> {
  const now = options.now ?? Math.floor(Date.now() / 1000);
  const expiresIn = options.expiresInSeconds ?? 3600;
  const audience = options.audience ?? "https://oauth2.googleapis.com/token";

  const header = { alg: "RS256", typ: "JWT" };
  const claims = {
    iss: serviceAccount.client_email,
    scope: scopes.join(" "),
    aud: audience,
    iat: now,
    exp: now + expiresIn,
  };

  const unsigned = `${base64UrlEncodeString(JSON.stringify(header))}.${base64UrlEncodeString(JSON.stringify(claims))}`;
  const key = await importSigningKey(serviceAccount.private_key);
  const signature = await crypto.subtle.sign(
    "RSASSA-PKCS1-v1_5",
    key,
    new TextEncoder().encode(unsigned),
  );
  return `${unsigned}.${base64UrlEncode(signature)}`;
}

interface TokenResponse {
  access_token: string;
  expires_in: number;
  token_type: string;
}

/** JWT Bearer フローでアクセストークンを取得する(1回の Cron 実行につき1回だけ呼ぶ想定。
 * Workers は常駐しないため、呼び出しをまたいだトークンキャッシュは持たない)。 */
export async function getAccessToken(serviceAccount: ServiceAccount, scopes: string[]): Promise<string> {
  const assertion = await signServiceAccountJwt(serviceAccount, scopes);
  const response = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
      assertion,
    }),
  });
  if (!response.ok) {
    throw new Error(`google token exchange failed: ${response.status} ${await response.text()}`);
  }
  const body = (await response.json()) as TokenResponse;
  return body.access_token;
}

export function parseServiceAccountJson(raw: string): ServiceAccount {
  const parsed = JSON.parse(raw) as Partial<ServiceAccount>;
  if (!parsed.client_email || !parsed.private_key) {
    throw new Error("service account JSON is missing client_email/private_key");
  }
  return { client_email: parsed.client_email, private_key: parsed.private_key };
}
