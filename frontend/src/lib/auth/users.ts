import "server-only";
import { promises as fs } from "fs";
import path from "path";
import { randomBytes, scryptSync, timingSafeEqual } from "crypto";

/**
 * Minimal local account store for the optional username/password sign-in.
 * Passwords are salted and hashed with scrypt; plain text is never written.
 * Stored at frontend/.data/users.json (gitignored).
 */

export interface StoredUser {
  id: string;
  username: string;
  name: string;
  salt: string;
  hash: string;
  createdAt: string;
}

const DATA_DIR = path.join(process.cwd(), ".data");
const FILE = path.join(DATA_DIR, "users.json");

async function readAll(): Promise<StoredUser[]> {
  try {
    const raw = await fs.readFile(FILE, "utf8");
    const data = JSON.parse(raw);
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

async function writeAll(users: StoredUser[]): Promise<void> {
  await fs.mkdir(DATA_DIR, { recursive: true });
  const tmp = `${FILE}.${process.pid}.tmp`;
  await fs.writeFile(tmp, JSON.stringify(users, null, 2), { encoding: "utf8", mode: 0o600 });
  await fs.rename(tmp, FILE);
}

function hashPassword(password: string, salt: string): string {
  return scryptSync(password, salt, 64).toString("hex");
}

export const USERNAME_RE = /^[a-z0-9._-]{3,32}$/;

export function validateCredentials(username: string, password: string): string | null {
  if (!USERNAME_RE.test(username)) return "Usernames are 3–32 characters: lowercase letters, numbers, dots, dashes or underscores.";
  if (password.length < 8) return "Passwords need at least 8 characters.";
  if (password.length > 128) return "Passwords can be at most 128 characters.";
  return null;
}

export async function createUser(usernameRaw: string, password: string, nameRaw: string): Promise<StoredUser> {
  const username = usernameRaw.trim().toLowerCase();
  const problem = validateCredentials(username, password);
  if (problem) throw new Error(problem);
  const users = await readAll();
  if (users.some((u) => u.username === username)) throw new Error("That username is taken. Pick another, or sign in instead.");
  const salt = randomBytes(16).toString("hex");
  const user: StoredUser = {
    id: `local_${randomBytes(8).toString("hex")}`,
    username,
    name: (nameRaw || username).trim().slice(0, 80),
    salt,
    hash: hashPassword(password, salt),
    createdAt: new Date().toISOString(),
  };
  users.push(user);
  await writeAll(users);
  return user;
}

export async function verifyUser(usernameRaw: string, password: string): Promise<StoredUser | null> {
  const username = usernameRaw.trim().toLowerCase();
  const users = await readAll();
  const user = users.find((u) => u.username === username);
  if (!user) {
    hashPassword(password, "0".repeat(32)); // equalise timing for unknown usernames
    return null;
  }
  const a = Buffer.from(hashPassword(password, user.salt), "hex");
  const b = Buffer.from(user.hash, "hex");
  return a.length === b.length && timingSafeEqual(a, b) ? user : null;
}
