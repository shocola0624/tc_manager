import { describe, expect, it } from "vitest";
import { parseServiceAccountJson, signServiceAccountJwt } from "./googleAuth";

function base64UrlDecode(value: string): Uint8Array {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/").padEnd(value.length + ((4 - (value.length % 4)) % 4), "=");
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

async function generateTestServiceAccount() {
  const keyPair = (await crypto.subtle.generateKey(
    { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" },
    true,
    ["sign", "verify"],
  )) as CryptoKeyPair;
  const pkcs8 = (await crypto.subtle.exportKey("pkcs8", keyPair.privateKey)) as ArrayBuffer;
  const base64 = btoa(String.fromCharCode(...new Uint8Array(pkcs8)));
  const pem = `-----BEGIN PRIVATE KEY-----\n${base64.match(/.{1,64}/g)!.join("\n")}\n-----END PRIVATE KEY-----\n`;
  return { pem, publicKey: keyPair.publicKey };
}

describe("signServiceAccountJwt", () => {
  it("produces a JWT whose signature verifies against the matching public key", async () => {
    const { pem, publicKey } = await generateTestServiceAccount();
    const jwt = await signServiceAccountJwt(
      { client_email: "test@example.iam.gserviceaccount.com", private_key: pem },
      ["https://www.googleapis.com/auth/spreadsheets"],
      { now: 1_700_000_000 },
    );

    const [headerB64, claimsB64, signatureB64] = jwt.split(".");
    expect(headerB64).toBeDefined();
    expect(claimsB64).toBeDefined();
    expect(signatureB64).toBeDefined();

    const signature = base64UrlDecode(signatureB64!);
    const signedData = new TextEncoder().encode(`${headerB64}.${claimsB64}`);
    const valid = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", publicKey, signature, signedData);
    expect(valid).toBe(true);
  });

  it("encodes the expected header and claims", async () => {
    const { pem } = await generateTestServiceAccount();
    const jwt = await signServiceAccountJwt(
      { client_email: "svc@example.com", private_key: pem },
      ["scope-a", "scope-b"],
      { now: 1_700_000_000, expiresInSeconds: 1800 },
    );
    const [headerB64, claimsB64] = jwt.split(".");
    const header = JSON.parse(new TextDecoder().decode(base64UrlDecode(headerB64!)));
    const claims = JSON.parse(new TextDecoder().decode(base64UrlDecode(claimsB64!)));

    expect(header).toEqual({ alg: "RS256", typ: "JWT" });
    expect(claims.iss).toBe("svc@example.com");
    expect(claims.scope).toBe("scope-a scope-b");
    expect(claims.iat).toBe(1_700_000_000);
    expect(claims.exp).toBe(1_700_001_800);
    expect(claims.aud).toBe("https://oauth2.googleapis.com/token");
  });
});

describe("parseServiceAccountJson", () => {
  it("parses a valid service account JSON", () => {
    const parsed = parseServiceAccountJson(
      JSON.stringify({ client_email: "a@b.com", private_key: "key", other_field: "ignored" }),
    );
    expect(parsed).toEqual({ client_email: "a@b.com", private_key: "key" });
  });

  it("rejects JSON missing required fields", () => {
    expect(() => parseServiceAccountJson(JSON.stringify({ client_email: "a@b.com" }))).toThrow();
  });
});
