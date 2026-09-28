#!/usr/bin/env node

/* eslint-disable no-undef */
/**
 * Generate sitemap.xml for ScholarZone
 * Run this after database updates to regenerate the sitemap
 */

const fs = require('fs');
const path = require('path');

const BASE_URL = 'https://gopal735.github.io/ScholarZone';

// Static pages that are always included
const STATIC_PAGES = [
  { url: '/ScholarZone/', changefreq: 'daily', priority: 1.0 },
  { url: '/ScholarZone/scholarships', changefreq: 'daily', priority: 0.9 },
  { url: '/ScholarZone/countries', changefreq: 'weekly', priority: 0.8 },
];

async function generateSitemap() {
  const apiBase = process.env.VITE_API_BASE_URL || 'http://localhost:8000/api';
  
  try {
    // Fetch all valid scholarships from the API
    const response = await fetch(`${apiBase}/scholarships?limit=500&verified=true`);
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    const data = await response.json();
    
    const scholarships = data.items || [];
    console.log(`Fetched ${scholarships.length} scholarships`);
    
    const urls = [...STATIC_PAGES];
    
    // Add scholarship detail pages
    for (const s of scholarships) {
      if (s.id) {
        urls.push({
          url: `/ScholarZone/scholarships/${s.id}`,
          lastmod: s.last_verified_at || s.updated_at || new Date().toISOString().split('T')[0],
          changefreq: 'weekly',
          priority: 0.7
        });
      }
    }
    
    // Generate XML
    const xml = [
      '<?xml version="1.0" encoding="UTF-8"?>',
      '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
      ...urls.map(page => {
        const lastmod = page.lastmod ? `<lastmod>${page.lastmod}</lastmod>` : '';
        return `  <url>
    <loc>${BASE_URL}${page.url}</loc>
    ${lastmod}
    <changefreq>${page.changefreq}</changefreq>
    <priority>${page.priority}</priority>
  </url>`;
      }),
      '</urlset>'
    ].join('\n');
    
    const outputPath = path.join(__dirname, '..', 'public', 'sitemap.xml');
    fs.writeFileSync(outputPath, xml);
    console.log(`Sitemap written to ${outputPath} with ${urls.length} URLs`);
    
  } catch (error) {
    console.error('Failed to generate sitemap:', error.message);
    process.exit(1);
  }
}

generateSitemap();