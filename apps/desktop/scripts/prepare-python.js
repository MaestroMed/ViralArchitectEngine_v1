#!/usr/bin/env node
/**
 * Prepare Python Environment for Production Build
 * 
 * Downloads and packages Python with all dependencies for distribution.
 * 
 * Usage:
 *   node scripts/prepare-python.js [--platform=win32|darwin|linux]
 */

const { execSync } = require('child_process');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const https = require('https');

// Configuration
const PYTHON_VERSION = '3.11.7';
const PYTHON_EMBED_URLS = {
  win32: `https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-embed-amd64.zip`,
  darwin: `https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-macos11.pkg`,
  linux: null, // Use system Python on Linux
};

const FFMPEG_URLS = {
  win32: 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip',
  darwin: 'https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip',
  linux: null, // Use system FFmpeg on Linux or apt
};

// SHA-256 expected for stable third-party downloads. python.org publishes
// checksums for each release; we pin them here. FFmpeg vendors (gyan.dev,
// evermeet.cx) ship rolling builds with no stable checksum, so we record the
// observed hash on first run and check against it on every subsequent run
// (Trust On First Use). Override any expected hash with FORGE_EXPECTED_SHA256
// or skip the check entirely with FORGE_SKIP_CHECKSUM=1 (only for local dev).
const EXPECTED_HASHES = {
  [PYTHON_EMBED_URLS.win32]: 'a09ad8be8fd05f47b7d0673cffb53d0aa11b7e3094a1f10f10da34d6a4cb09c5',
  // python-3.11.7-macos11.pkg: pin once you've verified against python.org/downloads.
  // Leave undefined to TOFU.
};
const CHECKSUMS_FILE = path.join(__dirname, '..', 'resources', '.checksums.json');

function sha256File(filePath) {
  const hash = crypto.createHash('sha256');
  hash.update(fs.readFileSync(filePath));
  return hash.digest('hex');
}

function loadKnownHashes() {
  try { return JSON.parse(fs.readFileSync(CHECKSUMS_FILE, 'utf8')); } catch { return {}; }
}

function saveKnownHashes(hashes) {
  fs.mkdirSync(path.dirname(CHECKSUMS_FILE), { recursive: true });
  fs.writeFileSync(CHECKSUMS_FILE, JSON.stringify(hashes, null, 2));
}

function verifyOrPin(url, filePath) {
  if (process.env.FORGE_SKIP_CHECKSUM === '1') {
    console.warn(`  ⚠ FORGE_SKIP_CHECKSUM=1 — skipping integrity check for ${url}`);
    return;
  }
  const actual = sha256File(filePath);
  const expected = process.env.FORGE_EXPECTED_SHA256 || EXPECTED_HASHES[url];
  if (expected) {
    if (actual.toLowerCase() !== expected.toLowerCase()) {
      throw new Error(
        `SHA-256 mismatch for ${url}\n  expected: ${expected}\n  actual:   ${actual}\n` +
        `Refusing to use the file. Verify the upstream is uncompromised; if the publisher ` +
        `rotated the artifact, update EXPECTED_HASHES.`
      );
    }
    console.log(`  ✓ integrity OK (sha256=${actual.slice(0, 12)}…)`);
    return;
  }
  // TOFU path: no pinned hash → consult / update the on-disk record.
  const known = loadKnownHashes();
  if (known[url]) {
    if (known[url] !== actual) {
      throw new Error(
        `SHA-256 changed for ${url}\n  was: ${known[url]}\n  now: ${actual}\n` +
        `If you trust this is a legitimate update, delete the entry in ${CHECKSUMS_FILE} ` +
        `and re-run. Otherwise abort — the upstream may have been tampered with.`
      );
    }
    console.log(`  ✓ matches previously-seen sha256=${actual.slice(0, 12)}…`);
  } else {
    known[url] = actual;
    saveKnownHashes(known);
    console.warn(
      `  ⚠ no pinned hash for ${url} — recording sha256=${actual.slice(0, 12)}… ` +
      `for future verification (TOFU)`,
    );
  }
}

const RESOURCES_DIR = path.join(__dirname, '..', 'resources');

// Parse arguments
const args = process.argv.slice(2);
const platformArg = args.find(a => a.startsWith('--platform='));
const platform = platformArg ? platformArg.split('=')[1] : process.platform;

console.log(`🐍 Preparing Python environment for ${platform}...`);

// Create directories
const pythonDir = path.join(RESOURCES_DIR, `python-${platform}`);
const ffmpegDir = path.join(RESOURCES_DIR, `ffmpeg-${platform}`);

if (!fs.existsSync(RESOURCES_DIR)) {
  fs.mkdirSync(RESOURCES_DIR, { recursive: true });
}

// Helper function to download file
function downloadFile(url, dest) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);
    https.get(url, (response) => {
      // Handle redirects
      if (response.statusCode === 302 || response.statusCode === 301) {
        return downloadFile(response.headers.location, dest)
          .then(resolve)
          .catch(reject);
      }
      
      response.pipe(file);
      file.on('finish', () => {
        file.close();
        resolve();
      });
    }).on('error', (err) => {
      fs.unlink(dest, () => {});
      reject(err);
    });
  });
}

// Helper to extract zip
function extractZip(zipPath, destDir) {
  if (platform === 'win32') {
    execSync(`powershell -command "Expand-Archive -Path '${zipPath}' -DestinationPath '${destDir}' -Force"`, { stdio: 'inherit' });
  } else {
    execSync(`unzip -o "${zipPath}" -d "${destDir}"`, { stdio: 'inherit' });
  }
}

async function preparePython() {
  console.log('\n📦 Preparing Python...');
  
  if (platform === 'linux') {
    console.log('  ℹ️  Linux: Using system Python. Ensure python3 is installed.');
    
    // Create a shell script to use system Python
    if (!fs.existsSync(pythonDir)) {
      fs.mkdirSync(pythonDir, { recursive: true });
    }
    
    fs.writeFileSync(
      path.join(pythonDir, 'python'),
      '#!/bin/bash\nexec python3 "$@"\n',
      { mode: 0o755 }
    );
    
    return;
  }
  
  const url = PYTHON_EMBED_URLS[platform];
  if (!url) {
    console.log('  ⚠️  No embedded Python URL for this platform');
    return;
  }
  
  const zipPath = path.join(RESOURCES_DIR, `python-${PYTHON_VERSION}.zip`);
  
  // Download if not exists
  if (!fs.existsSync(zipPath)) {
    console.log(`  ⬇️  Downloading Python ${PYTHON_VERSION}...`);
    await downloadFile(url, zipPath);
    console.log('  ✅ Download complete');
  } else {
    console.log('  ✅ Python archive already exists');
  }
  verifyOrPin(url, zipPath);

  // Extract
  if (!fs.existsSync(pythonDir)) {
    fs.mkdirSync(pythonDir, { recursive: true });
  }
  
  console.log('  📂 Extracting...');
  extractZip(zipPath, pythonDir);
  console.log('  ✅ Python extracted');
  
  // Enable pip for embedded Python (Windows)
  if (platform === 'win32') {
    const pthFile = fs.readdirSync(pythonDir).find(f => f.endsWith('._pth'));
    if (pthFile) {
      const pthPath = path.join(pythonDir, pthFile);
      let content = fs.readFileSync(pthPath, 'utf8');
      // Uncomment import site
      content = content.replace('#import site', 'import site');
      fs.writeFileSync(pthPath, content);
      console.log('  ✅ Enabled pip support');
    }
    
    // Install pip
    console.log('  📥 Installing pip...');
    const getPipUrl = 'https://bootstrap.pypa.io/get-pip.py';
    const getPipPath = path.join(pythonDir, 'get-pip.py');
    await downloadFile(getPipUrl, getPipPath);
    verifyOrPin(getPipUrl, getPipPath);
    execSync(`"${path.join(pythonDir, 'python.exe')}" "${getPipPath}"`, { stdio: 'inherit' });
    fs.unlinkSync(getPipPath);
  }
}

async function prepareFFmpeg() {
  console.log('\n🎬 Preparing FFmpeg...');
  
  if (platform === 'linux') {
    console.log('  ℹ️  Linux: Using system FFmpeg. Ensure ffmpeg is installed.');
    
    // Create symlink script
    if (!fs.existsSync(ffmpegDir)) {
      fs.mkdirSync(ffmpegDir, { recursive: true });
    }
    
    fs.writeFileSync(
      path.join(ffmpegDir, 'ffmpeg'),
      '#!/bin/bash\nexec /usr/bin/ffmpeg "$@"\n',
      { mode: 0o755 }
    );
    fs.writeFileSync(
      path.join(ffmpegDir, 'ffprobe'),
      '#!/bin/bash\nexec /usr/bin/ffprobe "$@"\n',
      { mode: 0o755 }
    );
    
    return;
  }
  
  const url = FFMPEG_URLS[platform];
  if (!url) {
    console.log('  ⚠️  No FFmpeg URL for this platform');
    return;
  }
  
  const zipPath = path.join(RESOURCES_DIR, 'ffmpeg.zip');
  
  // Download if not exists
  if (!fs.existsSync(zipPath)) {
    console.log('  ⬇️  Downloading FFmpeg...');
    await downloadFile(url, zipPath);
    console.log('  ✅ Download complete');
  } else {
    console.log('  ✅ FFmpeg archive already exists');
  }
  verifyOrPin(url, zipPath);
  
  // Extract
  if (!fs.existsSync(ffmpegDir)) {
    fs.mkdirSync(ffmpegDir, { recursive: true });
  }
  
  console.log('  📂 Extracting...');
  extractZip(zipPath, ffmpegDir);
  
  // Find and move binaries to root of ffmpegDir
  const extractedDirs = fs.readdirSync(ffmpegDir);
  for (const dir of extractedDirs) {
    const binDir = path.join(ffmpegDir, dir, 'bin');
    if (fs.existsSync(binDir)) {
      const files = fs.readdirSync(binDir);
      for (const file of files) {
        fs.copyFileSync(
          path.join(binDir, file),
          path.join(ffmpegDir, file)
        );
      }
    }
  }
  
  console.log('  ✅ FFmpeg extracted');
}

async function installDependencies() {
  console.log('\n📚 Installing Python dependencies...');
  
  const requirementsPath = path.join(__dirname, '..', '..', 'forge-engine', 'requirements.txt');
  
  if (!fs.existsSync(requirementsPath)) {
    console.log('  ⚠️  requirements.txt not found');
    return;
  }
  
  let pythonExe;
  if (platform === 'win32') {
    pythonExe = path.join(pythonDir, 'python.exe');
  } else if (platform === 'darwin') {
    pythonExe = path.join(pythonDir, 'bin', 'python3');
  } else {
    pythonExe = 'python3';
  }
  
  if (!fs.existsSync(pythonExe) && platform !== 'linux') {
    console.log('  ⚠️  Python executable not found');
    return;
  }
  
  try {
    console.log('  📥 Installing packages...');
    execSync(`"${pythonExe}" -m pip install -r "${requirementsPath}" --target "${path.join(pythonDir, 'Lib', 'site-packages')}"`, {
      stdio: 'inherit',
    });
    console.log('  ✅ Dependencies installed');
  } catch (err) {
    console.error('  ❌ Failed to install dependencies:', err.message);
  }
}

async function main() {
  try {
    await preparePython();
    await prepareFFmpeg();
    await installDependencies();
    
    console.log('\n✅ Build resources prepared successfully!');
    console.log(`   Python: ${pythonDir}`);
    console.log(`   FFmpeg: ${ffmpegDir}`);
    
  } catch (err) {
    console.error('❌ Error:', err);
    process.exit(1);
  }
}

main();
