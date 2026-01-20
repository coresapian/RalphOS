#!/usr/bin/env node

import puppeteer from "puppeteer-core";

const domain = process.argv[2];

if (process.argv[2] === "--help" || process.argv[2] === "-h") {
	console.log("Usage: cookies.js [domain]");
	console.log("\nExamples:");
	console.log(" cookies.js # Get all cookies for current page");
	console.log(" cookies.js example.com # Get cookies for specific domain");
	process.exit(0);
}

const b = await puppeteer.connect({
	browserURL: "http://localhost:9222",
	defaultViewport: null,
});

const p = (await b.pages()).at(-1);

if (!p) {
	console.error(" No active tab found");
	process.exit(1);
}

const client = await p.target().createCDPSession();
const { cookies } = await client.send("Network.getAllCookies");

const filtered = domain
	? cookies.filter((c) => c.domain.includes(domain))
	: cookies;

for (const cookie of filtered) {
	console.log(`${cookie.name}: ${cookie.value}`);
	console.log(` domain: ${cookie.domain}`);
	console.log(` path: ${cookie.path}`);
	console.log(` httpOnly: ${cookie.httpOnly}`);
	console.log(` secure: ${cookie.secure}`);
	console.log("");
}

await b.disconnect();
