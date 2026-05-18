// Netlify Edge Function: HTTP Basic Authentication gate.
// Runs on every request (config.path = "/*") and returns 401 BEFORE any
// HTML is served unless the request carries valid Basic credentials.

declare const Netlify: { env: { get(key: string): string | undefined } };

export default async (request: Request): Promise<Response | undefined> => {
  const username = Netlify.env.get("AUTH_USERNAME");
  const password = Netlify.env.get("AUTH_PASSWORD");

  if (!username || !password) {
    return new Response(
      "Server misconfiguration: AUTH_USERNAME and/or AUTH_PASSWORD environment variables are not set on this Netlify deploy.",
      {
        status: 500,
        headers: { "Content-Type": "text/plain; charset=utf-8" },
      },
    );
  }

  const expected = "Basic " + btoa(`${username}:${password}`);
  const provided = request.headers.get("authorization");

  if (provided === expected) {
    return;
  }

  return new Response("Authentication required", {
    status: 401,
    headers: {
      "WWW-Authenticate": 'Basic realm="HomeQuest Preview", charset="UTF-8"',
      "Content-Type": "text/plain; charset=utf-8",
    },
  });
};

export const config = {
  path: "/*",
};
