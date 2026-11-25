import { NextResponse } from "next/server";
import { googleConfigured, microsoftConfigured } from "@/lib/auth/options";

export const dynamic = "force-dynamic";

/** Which sign-in methods are ready, so the login page can explain missing OAuth setup instead of failing. */
export async function GET() {
  return NextResponse.json({ credentials: true, google: googleConfigured, microsoft: microsoftConfigured });
}
