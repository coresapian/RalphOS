#!/usr/bin/env node
import puppeteer from 'puppeteer-core';

const url = process.argv[2];
const openNew = process.argv.includes('--new');

if (!url) {
 console.error('Usage: nav.js <url> [--new]');
 process.exit(1);
}

async function main() {
 let browser;
 try {
 browser = await puppeteer.connect({
 browserURL: 'http://localhost:9222',
 defaultViewport: null
 });

 let page;
 if (openNew) {
 page = await browser.newPage();
 } else {
 const pages = await browser.pages();
 page = pages[pages.length - 1] || await browser.newPage();
 }

 await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
 console.log(` Navigated${openNew ? ' (new tab)' : ''}: ${url}`);
 console.log(` Title: ${await page.title()}`);
 } catch (e) {
 if (e.message.includes('connect')) {
 console.error(' Chrome not running. Start with: ~/.factory/skills/browser/start.js');
 } else {
 console.error(' Navigation failed:', e.message);
 }
 process.exit(1);
 } finally {
 if (browser) browser.disconnect();
 }
}

main();
