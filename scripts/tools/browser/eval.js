#!/usr/bin/env node
import puppeteer from 'puppeteer-core';

const code = process.argv[2];

if (!code) {
 console.error('Usage: eval.js <javascript-expression>');
 console.error('Example: eval.js "document.title"');
 console.error('Example: eval.js "document.querySelectorAll(\'a\').length"');
 process.exit(1);
}

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

 const result = await page.evaluate(async (expr) => {
 return await eval(`(async () => ${expr})()`);
 }, code);

 if (typeof result === 'object') {
 console.log(JSON.stringify(result, null, 2));
 } else {
 console.log(result);
 }
 } catch (e) {
 if (e.message.includes('connect')) {
 console.error(' Chrome not running. Start with: ~/.factory/skills/browser/start.js');
 } else {
 console.error(' Evaluation failed:', e.message);
 }
 process.exit(1);
 } finally {
 if (browser) browser.disconnect();
 }
}

main();
