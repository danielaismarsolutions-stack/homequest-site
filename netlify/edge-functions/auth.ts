import type { Context } from "https://edge.netlify.com";

const REALM = 'Basic realm="HomeQuest Preview", charset="UTF-8"';

function unauthorized(): Response {
  return new Response("401 Unauthorized", {
    status: 401,
    headers: {
      "WWW-Authenticate": REALM,
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}

async function sha256(input: string): Promise<Uint8Array> {
  const data = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return new Uint8Array(digest);
}

function timingSafeEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

async function constantTimeStringEqual(a: string, b: string): Promise<boolean> {
  const [ha, hb] = await Promise.all([sha256(a), sha256(b)]);
  return timingSafeEqual(ha, hb);
}

export default async function handler(request: Request, context: Context) {
  const url = new URL(request.url);

  if (url.pathname === "/favicon.ico") {
    return context.next();
  }

  const expectedUser = Deno.env.get("AUTH_USERNAME");
  const expectedPass = Deno.env.get("AUTH_PASSWORD");

  if (!expectedUser || !expectedPass) {
    return new Response(
      "Service unavailable: authentication is not configured.",
      {
        status: 503,
        headers: {
          "Content-Type": "text/plain; charset=utf-8",
          "Cache-Control": "no-store",
        },
      },
    );
  }

  const header = request.headers.get("authorization");
  if (!header || !header.toLowerCase().startsWith("basic ")) {
    return unauthorized();
  }

  let decoded: string;
  try {
    decoded = atob(header.slice(6).trim());
  } catch {
    return unauthorized();
  }

  const sep = decoded.indexOf(":");
  if (sep < 0) return unauthorized();

  const user = decoded.slice(0, sep);
  const pass = decoded.slice(sep + 1);

  const [userOk, passOk] = await Promise.all([
    constantTimeStringEqual(user, expectedUser),
    constantTimeStringEqual(pass, expectedPass),
  ]);

  if (!userOk || !passOk) return unauthorized();

  return context.next();
}

export const config = {
  path: "/*",
};
