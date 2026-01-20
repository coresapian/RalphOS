#!/usr/bin/env node
import puppeteer from 'puppeteer-core';

const prompt = process.argv[2] || 'Click elements to select them';

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

 console.log(`\n ${prompt}`);
 console.log(' Click to select, Cmd/Ctrl+Click for multi-select, press Enter in terminal when done.\n');

 // Inject picker overlay
 await page.evaluate((promptText) => {
 if (document.getElementById('__factory_picker__')) return;
 
 const overlay = document.createElement('div');
 overlay.id = '__factory_picker__';
 overlay.innerHTML = `
 <style>
 #__factory_picker_banner__ {
 position: fixed; top: 0; left: 0; right: 0; z-index: 999999;
 background: #1a1a2e; color: #eee; padding: 12px 20px;
 font: 14px system-ui; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.3);
 }
 .__factory_highlight__ {
 outline: 3px solid #4CAF50 !important;
 outline-offset: 2px !important;
 }
 .__factory_selected__ {
 outline: 3px solid #2196F3 !important;
 outline-offset: 2px !important;
 background: rgba(33, 150, 243, 0.1) !important;
 }
 </style>
 <div id="__factory_picker_banner__">
 ${promptText} | Click to select | Cmd/Ctrl+Click for multi-select | Press Enter in terminal when done
 </div>
 `;
 document.body.appendChild(overlay);

 window.__factorySelected__ = [];
 let lastHighlight = null;

 document.addEventListener('mouseover', (e) => {
 if (e.target.closest('#__factory_picker__')) return;
 if (lastHighlight) lastHighlight.classList.remove('__factory_highlight__');
 e.target.classList.add('__factory_highlight__');
 lastHighlight = e.target;
 }, true);

 document.addEventListener('click', (e) => {
 if (e.target.closest('#__factory_picker__')) return;
 e.preventDefault();
 e.stopPropagation();
 
 const el = e.target;
 if (!e.metaKey && !e.ctrlKey) {
 document.querySelectorAll('.__factory_selected__').forEach(s => s.classList.remove('__factory_selected__'));
 window.__factorySelected__ = [];
 }
 
 el.classList.add('__factory_selected__');
 window.__factorySelected__.push({
 tag: el.tagName.toLowerCase(),
 id: el.id || null,
 classes: [...el.classList].filter(c => !c.startsWith('__factory_')),
 text: el.innerText?.slice(0, 100)?.trim() || null,
 href: el.href || null,
 selector: getSelector(el)
 });
 }, true);

 function getSelector(el) {
 if (el.id) return `#${el.id}`;
 let path = [];
 while (el && el.nodeType === 1) {
 let selector = el.tagName.toLowerCase();
 if (el.id) { path.unshift(`#${el.id}`); break; }
 if (el.className) {
 const classes = [...el.classList].filter(c => !c.startsWith('__factory_')).join('.');
 if (classes) selector += `.${classes}`;
 }
 path.unshift(selector);
 el = el.parentElement;
 }
 return path.join(' > ');
 }
 }, prompt);

 // Wait for user to press Enter
 process.stdin.setRawMode(true);
 process.stdin.resume();
 
 await new Promise(resolve => {
 process.stdin.on('data', (key) => {
 if (key[0] === 13 || key[0] === 3) resolve(); // Enter or Ctrl+C
 });
 });

 // Get selected elements
 const selected = await page.evaluate(() => {
 const results = window.__factorySelected__ || [];
 document.getElementById('__factory_picker__')?.remove();
 document.querySelectorAll('.__factory_highlight__, .__factory_selected__').forEach(el => {
 el.classList.remove('__factory_highlight__', '__factory_selected__');
 });
 return results;
 });

 console.log('\n Selected elements:\n');
 console.log(JSON.stringify(selected, null, 2));

 } catch (e) {
 if (e.message.includes('connect')) {
 console.error(' Chrome not running. Start with: ~/.factory/skills/browser/start.js');
 } else {
 console.error(' Picker failed:', e.message);
 }
 process.exit(1);
 } finally {
 process.stdin.setRawMode(false);
 if (browser) browser.disconnect();
 process.exit(0);
 }
}

main();
