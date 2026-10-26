#!/usr/bin/env node
/**
 * generate_index.mjs
 * 
 * Generates index.json and copies scholarship JSON files from canonical
 * research source to frontend public runtime directory.
 * 
 * This script must be run from anywhere in the project.
 * 
 * Usage: node research/premium_card/generate_index.mjs
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const EXPECTED_FILE_COUNT = 70;
const SCHOLARSHIP_FILE_PATTERN = /^scholarship_\d{3}_.*\.json$/;

function findProjectRoot() {
    // Get the directory of this script
    const __filename = fileURLToPath(import.meta.url);
    const __dirname = path.dirname(__filename);
    
    console.log(`[generate_index] Script dir: ${__dirname}`);
    
    // Walk up from script directory to find the TOPMOST project root
    // (the highest directory containing research/premium_card/output)
    let currentDir = path.dirname(__filename);
    let lastMatch = null;
    
    console.log(`[generate_index] Starting search from: ${currentDir}`);
    
    // Walk up until filesystem root, tracking the LAST match found
    while (currentDir !== path.parse(currentDir).root) {
        const candidate = path.join(currentDir, 'research', 'premium_card', 'output');
        const exists = fs.existsSync(candidate);
        console.log(`[generate_index] Checking: ${candidate} -> ${exists ? 'EXISTS' : 'not found'}`);
        
        if (exists) {
            lastMatch = currentDir;
            console.log(`[generate_index] Match found at: ${currentDir}`);
        }
        currentDir = path.dirname(currentDir);
    }
    
    if (lastMatch) {
        console.log(`[generate_index] Topmost match (project root): ${lastMatch}`);
        return lastMatch;
    }
    
    // Fallback: if we're in frontend/, go up one level
    const scriptDir = path.dirname(fileURLToPath(import.meta.url));
    if (path.basename(path.dirname(scriptDir)) === 'frontend') {
        return path.dirname(path.dirname(scriptDir));
    }
    
    throw new Error('Could not find project root (research/premium_card/output not found)');
}

async function main() {
    console.log('[generate_index] Starting Premium Card index generation...');
    
    const PROJECT_ROOT = findProjectRoot();
    const SOURCE_DIR = path.join(PROJECT_ROOT, 'research', 'premium_card', 'output');
    const DEST_DIR = path.join(PROJECT_ROOT, 'frontend', 'public', 'research', 'premium_card', 'output');
    const INDEX_PATH = path.join(DEST_DIR, 'index.json');

    console.log(`[generate_index] Project root: ${PROJECT_ROOT}`);
    console.log(`[generate_index] Source dir: ${SOURCE_DIR}`);
    console.log(`[generate_index] Dest dir: ${DEST_DIR}`);

    // 1. Validate source directory exists
    if (!fs.existsSync(SOURCE_DIR)) {
        console.error(`[generate_index] ERROR: Source directory not found: ${SOURCE_DIR}`);
        process.exit(1);
    }

    // 2. Read all scholarship JSON files
    const allFiles = fs.readdirSync(SOURCE_DIR);
    const scholarshipFiles = allFiles
        .filter(f => SCHOLARSHIP_FILE_PATTERN.test(f))
        .sort();

    console.log(`[generate_index] Found ${scholarshipFiles.length} scholarship JSON files`);

    // 3. Validate exactly 70 files
    if (scholarshipFiles.length !== EXPECTED_FILE_COUNT) {
        console.error(`[generate_index] ERROR: Expected ${EXPECTED_FILE_COUNT} scholarship files, found ${scholarshipFiles.length}`);
        process.exit(1);
    }

    // 4. Read and validate each file
    const indexEntries = [];
    const requiredFields = ['source_title', 'source_provider', 'source_file', 'researched_at', 'data'];

    for (const filename of scholarshipFiles) {
        const filePath = path.join(SOURCE_DIR, filename);
        
        let content;
        try {
            content = fs.readFileSync(filePath, 'utf-8');
        } catch (err) {
            console.error(`[generate_index] ERROR: Failed to read ${filename}: ${err.message}`);
            process.exit(1);
        }

        let parsed;
        try {
            parsed = JSON.parse(content);
        } catch (err) {
            console.error(`[generate_index] ERROR: Invalid JSON in ${filename}: ${err.message}`);
            process.exit(1);
        }

        // Validate required fields
        for (const field of requiredFields) {
            if (!(field in parsed)) {
                console.error(`[generate_index] ERROR: Missing required field '${field}' in ${filename}`);
                process.exit(1);
            }
        }

        // Validate data.id exists
        if (!parsed.data || !parsed.data.id) {
            console.error(`[generate_index] ERROR: Missing data.id in ${filename}`);
            process.exit(1);
        }

        indexEntries.push(parsed);
    }

    // 5. Check for duplicate IDs
    const ids = indexEntries.map(e => e.data.id);
    const uniqueIds = new Set(ids);
    if (ids.length !== uniqueIds.size) {
        const duplicates = ids.filter((id, i) => ids.indexOf(id) !== i);
        console.error(`[generate_index] ERROR: Duplicate data.id values found: ${duplicates.join(', ')}`);
        process.exit(1);
    }

    console.log(`[generate_index] Validated ${indexEntries.length} entries with unique IDs`);

    // 6. Ensure destination directory exists
    fs.mkdirSync(DEST_DIR, { recursive: true });

    // 7. Remove stale destination scholarship JSON files
    if (fs.existsSync(DEST_DIR)) {
        const destFiles = fs.readdirSync(DEST_DIR);
        const destScholarshipFiles = destFiles.filter(f => SCHOLARSHIP_FILE_PATTERN.test(f));
        for (const staleFile of destScholarshipFiles) {
            fs.unlinkSync(path.join(DEST_DIR, staleFile));
        }
        console.log(`[generate_index] Removed ${destScholarshipFiles.length} stale destination files`);
    }

    // 8. Copy 70 scholarship JSON files to destination
    let copied = 0;
    for (const filename of scholarshipFiles) {
        const srcPath = path.join(SOURCE_DIR, filename);
        const destPath = path.join(DEST_DIR, filename);
        fs.copyFileSync(srcPath, destPath);
        copied++;
    }
    console.log(`[generate_index] Copied ${copied} scholarship JSON files to destination`);

    // 9. Generate index.json deterministically
    // Sort by data.id for deterministic ordering
    indexEntries.sort((a, b) => a.data.id.localeCompare(b.data.id));

    const indexJson = JSON.stringify(indexEntries, null, 2);
    fs.writeFileSync(INDEX_PATH, indexJson, 'utf-8');
    console.log(`[generate_index] Generated index.json with ${indexEntries.length} entries`);

    // 10. Verify output
    const verifyIndex = JSON.parse(fs.readFileSync(INDEX_PATH, 'utf-8'));
    const destFilesAfter = fs.readdirSync(DEST_DIR).filter(f => SCHOLARSHIP_FILE_PATTERN.test(f));
    
    if (verifyIndex.length !== EXPECTED_FILE_COUNT) {
        console.error(`[generate_index] ERROR: Index has ${verifyIndex.length} entries, expected ${EXPECTED_FILE_COUNT}`);
        process.exit(1);
    }
    if (destFilesAfter.length !== EXPECTED_FILE_COUNT) {
        console.error(`[generate_index] ERROR: Destination has ${destFilesAfter.length} files, expected ${EXPECTED_FILE_COUNT}`);
        process.exit(1);
    }

    console.log('[generate_index] ✓ All validations passed');
    console.log('[generate_index] Premium Card runtime data generated successfully');
}

main().catch(err => {
    console.error('[generate_index] FATAL ERROR:', err);
    process.exit(1);
});