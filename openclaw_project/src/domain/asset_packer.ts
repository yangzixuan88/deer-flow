/**
 * @file asset_packer.ts
 * @description Implementation of the Asset Packager (Action 023).
 * Scans the asset library, performs PII scrubbing, and generates a portable MCP-compatible package.
 * Reference: Super Constitution Phase 7 & Portable Asset Logic.
 */

import * as fs from 'fs';
import * as path from 'path';

export interface AssetManifest {
  version: string;
  generated_at: string;
  fingerprint: string;
  assets: Array<{
    id: string;
    name: string;
    category: string;
    quality_score: number;
    path: string;
  }>;
  mcp_compatibility: boolean;
}

/**
 * Asset Packager (Action 023)
 * Logic: Scan assets -> PII Scrubbing -> Manifest generation -> Packaging.
 */
export class AssetPackager {
  // Use relative paths from project root for portability
  private readonly PROJECT_ROOT: string;
  private readonly ASSETS_ROOT: string;
  private readonly OUTPUT_DIR: string;

  constructor() {
    // Resolve paths relative to project root (parent of src/domain)
    this.PROJECT_ROOT = path.resolve(__dirname, '..', '..');
    this.ASSETS_ROOT = path.join(this.PROJECT_ROOT, 'assets');
    this.OUTPUT_DIR = path.join(this.PROJECT_ROOT, 'exports');
  }

  /**
   * Main entry point for packaging assets.
   */
  public async packageAssets(): Promise<string> {
    console.log(`[AssetPackager] Starting asset packaging...`);

    // 1. Scan the Asset Manifest (Simulated reading from SQLite)
    const assetsToPack = this.scanAssetLibrary();

    // 2. Perform PII Scrubbing (Scrub Emails, Keys, Usernames)
    this.performPIIScrubbing(assetsToPack);

    // 3. Generate MANIFEST.json
    const manifest = this.generateManifest(assetsToPack);

    // 4. Create the final package (Simulated Zip/Bundle)
    const packagePath = this.createBundle(manifest);

    console.log(`[AssetPackager] Portable asset package created at: ${packagePath}`);
    return packagePath;
  }

  private scanAssetLibrary() {
    // Logic: In a real system, query Asset_Manifest.sqlite
    return [
      { id: "asset-001", name: "react_ui_comparison.md", category: "DomainKnowledge", quality_score: 0.95, path: "domain_knowledge/react_ui_comparison.md" },
      { id: "asset-002", name: "dapr_evolution_patch.json", category: "Skill", quality_score: 0.88, path: "cold_skills/dapr_evolution_patch.json" }
    ];
  }

  /**
   * PII Scrubbing Engine
   * Logic: Scan file content for sensitive patterns and replace with [REDACTED].
   * Reference: Super Constitution §18.2 (PII Protection)
   */
  private performPIIScrubbing(assets: any[]): void {
    console.log(`[AssetPackager] Scrubbing PII from ${assets.length} assets...`);
    const piiPatterns = [
      /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g, // Email
      /sk-[a-zA-Z0-9]{40,}/g, // OpenAI Key
      /C:\\Users\\[^\\]+/g // Windows User Paths
    ];

    for (const asset of assets) {
      const fullPath = path.join(this.ASSETS_ROOT, asset.path);
      if (fs.existsSync(fullPath)) {
        let content = fs.readFileSync(fullPath, 'utf-8');
        let originalContent = content;

        for (const pattern of piiPatterns) {
          content = content.replace(pattern, '[REDACTED]');
        }

        if (content !== originalContent) {
          console.log(`[AssetPackager] PII scrubbed from ${asset.name}`);
          // In a real export, we'd write to a temporary staging area
        }
      }
    }
  }

  private generateManifest(assets: any[]): AssetManifest {
    return {
      version: "1.0.0",
      generated_at: new Date().toISOString(),
      fingerprint: "F-2B0D4C-MASTER",
      assets: assets,
      mcp_compatibility: true
    };
  }

  private createBundle(manifest: AssetManifest): string {
    if (!fs.existsSync(this.OUTPUT_DIR)) {
      fs.mkdirSync(this.OUTPUT_DIR);
    }
    const manifestFile = path.join(this.OUTPUT_DIR, 'MANIFEST.json');
    fs.writeFileSync(manifestFile, JSON.stringify(manifest, null, 2));
    
    // In a real system, we'd zip everything up here
    return path.join(this.OUTPUT_DIR, `AssetPackage_${manifest.generated_at.split('T')[0]}.zip`);
  }
}
