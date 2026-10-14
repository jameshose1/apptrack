/** @type {import('next').NextConfig} */
const path = require("path");
const nextConfig = {
  // better-sqlite3 is a native module; keep it external to the server bundle
  serverExternalPackages: ["better-sqlite3"],
  // pin the workspace root (a stray ~/package-lock.json confuses inference)
  outputFileTracingRoot: __dirname,
};
module.exports = nextConfig;
