#!/usr/bin/env node
import puppeteer from 'puppeteer-core';
import { tmpdir } from 'os';
import { join } from 'path';

async function main() {
 let browser;
 try {
 browser = await puppeteer.connect({
 browserURL: 'http://localhost:9222',
 defaultViewport: null
 });

 const pages = await browser.pages();
 const page = pages[pages.length - 1];
 
 if (!page) {
 console.error(' No active page found');
 process.exit(1);
 }

 const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
 const filepath = join(tmpdir(), `screenshot-${timestamp}.png`);
 
 await page.screenshot({ path: filepath });
 console.log(` Screenshot saved: ${filepath}`);
 } catch (e) {
 if (e.message.includes('connect')) {
 console.error(' Chrome not running. Start with: ~/.factory/skills/browser/start.js');
 } else {
 console.error(' Screenshot failed:', e.message);
 }
 process.exit(1);
 } finally {
 if (browser) browser.disconnect();
 }
}

main();
