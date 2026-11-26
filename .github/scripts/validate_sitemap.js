#!/usr/bin/env node
/* Validate sitemap after PR #107 purge */

const fs = require('fs');
const xml = fs.readFileSync('public/sitemap.xml', 'utf8');

if (!xml.includes('<?xml version="1.0" encoding="UTF-8"?>')) throw new Error('Missing XML declaration');
if (!xml.includes('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')) throw new Error('Missing urlset');

const urlCount = (xml.match(/<url>/g) || []).length;
console.log('Sitemap URLs:', urlCount);

const snapshot = JSON.parse(fs.readFileSync('public/scholarships-snapshot.json', 'utf8'));
const expectedMin = 2 + snapshot.scholarships.length;
if (urlCount < expectedMin) {
  throw new Error('Sitemap has ' + urlCount + ' URLs, expected at least ' + expectedMin);
}

const excluded = ['/admin', '/dashboard', '/applications', '/login', '/register', '/saved', '/compare', '/api/'];
for (const prefix of excluded) {
  if (xml.includes(prefix)) throw new Error('Sitemap contains excluded prefix: ' + prefix);
}

console.log('Sitemap validation passed');