import { NextResponse } from "next/server";
import { createUser } from "@/lib/auth/users";

export const runtime = "nodejs";

export async function POST(req: Request) {
  let body: { username?: string; password?: string; name?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Send a JSON body with username, password and name." }, { status: 400 });
  }
  try {
    const user = await createUser(String(body.username || ""), String(body.password || ""), String(body.name || ""));
    return NextResponse.json({ ok: true, username: user.username, name: user.name }, { status: 201 });
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : "Couldn't create the account.";
    const status = message.includes("taken") ? 409 : 400;
    return NextResponse.json({ error: message }, { status });
  }
}
