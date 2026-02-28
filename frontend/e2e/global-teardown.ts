/**
 * Global teardown for E2E tests.
 *
 * Runs after all tests to clean up resources.
 */

import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export default async function globalTeardown(_config: FullConfig): Promise<void> {
  console.log('\n🧹 E2E Test Teardown');
  console.log('━'.repeat(50));

  // Clean up temp files
  const tempDir = '/tmp';
  const testFilePatterns = [
    /^.*_filled\.(aasx|json)$/,
    /^aas-conformance-.*$/,
    /^e2e-test-.*$/,
  ];

  let cleanedCount = 0;

  try {
    const files = fs.readdirSync(tempDir);

    for (const file of files) {
      const shouldClean = testFilePatterns.some((pattern) => pattern.test(file));

      if (shouldClean) {
        const filePath = path.join(tempDir, file);

        try {
          const stat = fs.statSync(filePath);

          // Only clean files older than 1 hour to avoid cleaning files from running tests
          const oneHourAgo = Date.now() - 60 * 60 * 1000;

          if (stat.mtimeMs < oneHourAgo) {
            if (stat.isDirectory()) {
              fs.rmSync(filePath, { recursive: true, force: true });
            } else {
              fs.unlinkSync(filePath);
            }
            cleanedCount++;
          }
        } catch {
          // Ignore errors when cleaning up
        }
      }
    }

    if (cleanedCount > 0) {
      console.log(`   Cleaned ${cleanedCount} temporary file(s)`);
    }
  } catch {
    // Ignore errors reading temp directory
  }

  // Log test summary if available
  const testResultsPath = path.join(process.cwd(), 'test-results', 'e2e-summary.json');

  if (fs.existsSync(testResultsPath)) {
    try {
      const summary = JSON.parse(fs.readFileSync(testResultsPath, 'utf-8'));

      console.log('\n📊 Test Summary');
      console.log('━'.repeat(50));
      console.log(`   Total: ${summary.total ?? 'N/A'}`);
      console.log(`   Passed: ${summary.passed ?? 'N/A'}`);
      console.log(`   Failed: ${summary.failed ?? 'N/A'}`);
      console.log(`   Skipped: ${summary.skipped ?? 'N/A'}`);
      console.log(`   Duration: ${summary.duration ?? 'N/A'}`);
    } catch {
      // Ignore errors reading summary
    }
  }

  console.log('\n✅ Teardown complete\n');
}
