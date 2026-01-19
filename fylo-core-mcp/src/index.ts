#!/usr/bin/env node
/**
 * Fylo-Core-MCP: Knowledge Graph MCP Server for RalphOS
 *
 * Provides knowledge graph capabilities for tracking the Ralph scraping pipeline:
 * - URL Discovery → HTML Scraping → Build Extraction → Mod Extraction
 *
 * Features:
 * - Entity tracking (sources, URLs, builds, modifications)
 * - Relationship mapping between pipeline stages
 * - DuckDB integration for persistence and visualization
 * - Real-time pipeline progress monitoring
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import * as fs from "fs";
import * as path from "path";

// Types for the knowledge graph
interface Entity {
  id: string;
  type: "source" | "url" | "build" | "modification" | "category" | "pattern";
  name: string;
  observations: string[];
  properties: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

interface Relation {
  id: string;
  from: string;
  to: string;
  type: string;
  properties: Record<string, unknown>;
  createdAt: string;
}

interface KnowledgeGraph {
  entities: Map<string, Entity>;
  relations: Relation[];
  metadata: {
    lastUpdated: string;
    version: string;
  };
}

// Initialize knowledge graph
const graph: KnowledgeGraph = {
  entities: new Map(),
  relations: [],
  metadata: {
    lastUpdated: new Date().toISOString(),
    version: "1.0.0"
  }
};

// Data directory for persistence
const DATA_DIR = process.env.FYLO_DATA_DIR || path.join(process.cwd(), "data", "fylo-graph");
const GRAPH_FILE = path.join(DATA_DIR, "knowledge-graph.json");
const RALPH_DIR = process.env.RALPH_DIR || process.cwd();

// Auto-sync configuration
const AUTO_SYNC_ENABLED = process.env.FYLO_AUTO_SYNC !== "false";
const SYNC_DEBOUNCE_MS = parseInt(process.env.FYLO_SYNC_DEBOUNCE || "2000", 10);
const PERIODIC_SYNC_INTERVAL_MS = parseInt(process.env.FYLO_PERIODIC_SYNC || "0", 10); // 0 = disabled

// File watcher state
let syncDebounceTimer: ReturnType<typeof setTimeout> | null = null;
let periodicSyncTimer: ReturnType<typeof setInterval> | null = null;
const activeWatchers: fs.FSWatcher[] = [];

// Ensure data directory exists
function ensureDataDir(): void {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }
}

// Load graph from disk
function loadGraph(): void {
  ensureDataDir();
  if (fs.existsSync(GRAPH_FILE)) {
    try {
      const data = JSON.parse(fs.readFileSync(GRAPH_FILE, "utf-8"));
      graph.entities = new Map(Object.entries(data.entities || {}));
      graph.relations = data.relations || [];
      graph.metadata = data.metadata || graph.metadata;
    } catch (error) {
      console.error("Error loading graph:", error);
    }
  }
}

// Save graph to disk
function saveGraph(): void {
  ensureDataDir();
  const data = {
    entities: Object.fromEntries(graph.entities),
    relations: graph.relations,
    metadata: {
      ...graph.metadata,
      lastUpdated: new Date().toISOString()
    }
  };
  fs.writeFileSync(GRAPH_FILE, JSON.stringify(data, null, 2));
}

// ============== AUTO-SYNC FILE WATCHING ==============

/**
 * Debounced sync function to prevent rapid re-syncing
 */
function debouncedSync(syncFn: () => void): void {
  if (syncDebounceTimer) {
    clearTimeout(syncDebounceTimer);
  }
  syncDebounceTimer = setTimeout(() => {
    try {
      syncFn();
      saveGraph();
      console.error(`[Auto-Sync] Knowledge graph updated at ${new Date().toISOString()}`);
    } catch (error) {
      console.error("[Auto-Sync] Error during sync:", error);
    }
  }, SYNC_DEBOUNCE_MS);
}

/**
 * Sync sources from sources.json into the knowledge graph
 */
function syncSourcesFromFile(): void {
  const sourcesPath = path.join(RALPH_DIR, "scripts", "ralph", "sources.json");
  if (!fs.existsSync(sourcesPath)) {
    return;
  }

  try {
    const sourcesData = JSON.parse(fs.readFileSync(sourcesPath, "utf-8"));
    const sources = sourcesData.sources || [];

    for (const source of sources) {
      const entityId = `source_${source.id.replace(/[^a-zA-Z0-9]/g, "_")}`;

      if (!graph.entities.has(entityId)) {
        // Create new source entity
        graph.entities.set(entityId, {
          id: entityId,
          type: "source",
          name: source.name || source.id,
          observations: [`Auto-synced from sources.json`],
          properties: {
            sourceId: source.id,
            url: source.url,
            status: source.status || "pending",
            outputDir: source.outputDir,
            pipeline: {
              urlsFound: 0,
              htmlScraped: 0,
              buildsExtracted: 0,
              modsExtracted: 0
            }
          },
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString()
        });
      } else {
        // Update existing source
        const existing = graph.entities.get(entityId)!;
        existing.properties.status = source.status || existing.properties.status;
        existing.properties.url = source.url || existing.properties.url;
        existing.updatedAt = new Date().toISOString();
        graph.entities.set(entityId, existing);
      }
    }

    graph.metadata.lastUpdated = new Date().toISOString();
  } catch (error) {
    console.error("[Auto-Sync] Error parsing sources.json:", error);
  }
}

/**
 * Scan data directories for pipeline progress and update entities
 */
function scanDataDirectories(): void {
  const dataDir = path.join(RALPH_DIR, "data");
  if (!fs.existsSync(dataDir)) {
    return;
  }

  try {
    const dirs = fs.readdirSync(dataDir, { withFileTypes: true })
      .filter(d => d.isDirectory() && !d.name.startsWith(".") && d.name !== "fylo-graph");

    for (const dir of dirs) {
      const sourceDir = path.join(dataDir, dir.name);
      const entityId = `source_${dir.name.replace(/[^a-zA-Z0-9]/g, "_")}`;

      // Find or create source entity
      let entity = graph.entities.get(entityId);
      if (!entity) {
        entity = {
          id: entityId,
          type: "source",
          name: dir.name,
          observations: [`Auto-discovered from data directory`],
          properties: {
            sourceId: dir.name,
            outputDir: `data/${dir.name}`,
            pipeline: {
              urlsFound: 0,
              htmlScraped: 0,
              buildsExtracted: 0,
              modsExtracted: 0
            }
          },
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString()
        };
      }

      // Update pipeline stats from files
      const pipeline = entity.properties.pipeline as Record<string, number>;

      // Check urls.json
      const urlsFile = path.join(sourceDir, "urls.json");
      if (fs.existsSync(urlsFile)) {
        try {
          const urlsData = JSON.parse(fs.readFileSync(urlsFile, "utf-8"));
          pipeline.urlsFound = Array.isArray(urlsData.urls) ? urlsData.urls.length : 0;
        } catch { /* ignore parse errors */ }
      }

      // Check html directory
      const htmlDir = path.join(sourceDir, "html");
      if (fs.existsSync(htmlDir)) {
        try {
          const htmlFiles = fs.readdirSync(htmlDir).filter(f => f.endsWith(".html"));
          pipeline.htmlScraped = htmlFiles.length;
        } catch { /* ignore errors */ }
      }

      // Check builds.json
      const buildsFile = path.join(sourceDir, "builds.json");
      if (fs.existsSync(buildsFile)) {
        try {
          const buildsData = JSON.parse(fs.readFileSync(buildsFile, "utf-8"));
          pipeline.buildsExtracted = Array.isArray(buildsData.builds) ? buildsData.builds.length :
                                     Array.isArray(buildsData) ? buildsData.length : 0;
        } catch { /* ignore parse errors */ }
      }

      // Check mods.json
      const modsFile = path.join(sourceDir, "mods.json");
      if (fs.existsSync(modsFile)) {
        try {
          const modsData = JSON.parse(fs.readFileSync(modsFile, "utf-8"));
          pipeline.modsExtracted = Array.isArray(modsData.modifications) ? modsData.modifications.length :
                                   Array.isArray(modsData) ? modsData.length : 0;
        } catch { /* ignore parse errors */ }
      }

      entity.properties.pipeline = pipeline;
      entity.updatedAt = new Date().toISOString();
      graph.entities.set(entityId, entity);
    }

    graph.metadata.lastUpdated = new Date().toISOString();
  } catch (error) {
    console.error("[Auto-Sync] Error scanning data directories:", error);
  }
}

/**
 * Start file watchers for auto-sync
 */
function startFileWatchers(): void {
  if (!AUTO_SYNC_ENABLED) {
    console.error("[Auto-Sync] Disabled via FYLO_AUTO_SYNC=false");
    return;
  }

  // Watch sources.json
  const sourcesPath = path.join(RALPH_DIR, "scripts", "ralph", "sources.json");
  if (fs.existsSync(sourcesPath)) {
    try {
      const watcher = fs.watch(sourcesPath, (eventType) => {
        if (eventType === "change") {
          console.error("[Auto-Sync] sources.json changed, syncing...");
          debouncedSync(syncSourcesFromFile);
        }
      });
      activeWatchers.push(watcher);
      console.error(`[Auto-Sync] Watching: ${sourcesPath}`);
    } catch (error) {
      console.error("[Auto-Sync] Failed to watch sources.json:", error);
    }
  }

  // Watch data directory for new source directories
  const dataDir = path.join(RALPH_DIR, "data");
  if (fs.existsSync(dataDir)) {
    try {
      const watcher = fs.watch(dataDir, { recursive: false }, (eventType, filename) => {
        if (filename && !filename.startsWith(".") && filename !== "fylo-graph") {
          console.error(`[Auto-Sync] Data directory change detected: ${filename}`);
          debouncedSync(scanDataDirectories);
        }
      });
      activeWatchers.push(watcher);
      console.error(`[Auto-Sync] Watching: ${dataDir}`);
    } catch (error) {
      console.error("[Auto-Sync] Failed to watch data directory:", error);
    }
  }

  // Start periodic sync if configured
  if (PERIODIC_SYNC_INTERVAL_MS > 0) {
    periodicSyncTimer = setInterval(() => {
      console.error("[Auto-Sync] Running periodic sync...");
      syncSourcesFromFile();
      scanDataDirectories();
      saveGraph();
    }, PERIODIC_SYNC_INTERVAL_MS);
    console.error(`[Auto-Sync] Periodic sync enabled every ${PERIODIC_SYNC_INTERVAL_MS / 1000}s`);
  }

  // Initial sync on startup
  console.error("[Auto-Sync] Running initial sync...");
  syncSourcesFromFile();
  scanDataDirectories();
  saveGraph();
}

/**
 * Stop all file watchers and timers
 */
function stopFileWatchers(): void {
  for (const watcher of activeWatchers) {
    watcher.close();
  }
  activeWatchers.length = 0;

  if (syncDebounceTimer) {
    clearTimeout(syncDebounceTimer);
    syncDebounceTimer = null;
  }

  if (periodicSyncTimer) {
    clearInterval(periodicSyncTimer);
    periodicSyncTimer = null;
  }

  console.error("[Auto-Sync] File watchers stopped");
}

// Generate unique ID
function generateId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// Create MCP server
const server = new McpServer({
  name: "fylo-core-mcp",
  version: "1.0.0",
});

// ============== TOOLS ==============

// Create Entity
server.tool(
  "create_entity",
  "Create a new entity in the knowledge graph (source, url, build, modification, category, or pattern)",
  {
    type: z.enum(["source", "url", "build", "modification", "category", "pattern"])
      .describe("Type of entity to create"),
    name: z.string().describe("Name/identifier for the entity"),
    properties: z.record(z.unknown()).optional()
      .describe("Additional properties for the entity"),
    observations: z.array(z.string()).optional()
      .describe("Initial observations about this entity")
  },
  async ({ type, name, properties, observations }) => {
    const id = generateId(type);
    const entity: Entity = {
      id,
      type,
      name,
      observations: observations || [],
      properties: properties || {},
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };

    graph.entities.set(id, entity);
    saveGraph();

    return {
      content: [{
        type: "text",
        text: `Created ${type} entity: ${name} (ID: ${id})`
      }]
    };
  }
);

// Add Observation
server.tool(
  "add_observation",
  "Add an observation to an existing entity",
  {
    entityId: z.string().describe("ID of the entity to add observation to"),
    observation: z.string().describe("The observation text to add")
  },
  async ({ entityId, observation }) => {
    const entity = graph.entities.get(entityId);
    if (!entity) {
      return {
        content: [{
          type: "text",
          text: `Entity not found: ${entityId}`
        }]
      };
    }

    entity.observations.push(observation);
    entity.updatedAt = new Date().toISOString();
    saveGraph();

    return {
      content: [{
        type: "text",
        text: `Added observation to ${entity.name}: "${observation}"`
      }]
    };
  }
);

// Create Relation
server.tool(
  "create_relation",
  "Create a relationship between two entities",
  {
    fromId: z.string().describe("ID of the source entity"),
    toId: z.string().describe("ID of the target entity"),
    relationType: z.string().describe("Type of relationship (e.g., 'has_url', 'contains_build', 'uses_mod', 'belongs_to')"),
    properties: z.record(z.unknown()).optional()
      .describe("Additional properties for the relationship")
  },
  async ({ fromId, toId, relationType, properties }) => {
    const fromEntity = graph.entities.get(fromId);
    const toEntity = graph.entities.get(toId);

    if (!fromEntity || !toEntity) {
      return {
        content: [{
          type: "text",
          text: `Entity not found: ${!fromEntity ? fromId : toId}`
        }]
      };
    }

    const relation: Relation = {
      id: generateId("rel"),
      from: fromId,
      to: toId,
      type: relationType,
      properties: properties || {},
      createdAt: new Date().toISOString()
    };

    graph.relations.push(relation);
    saveGraph();

    return {
      content: [{
        type: "text",
        text: `Created relation: ${fromEntity.name} --[${relationType}]--> ${toEntity.name}`
      }]
    };
  }
);

// Query Graph
server.tool(
  "query_graph",
  "Query the knowledge graph for entities and relationships",
  {
    entityType: z.enum(["source", "url", "build", "modification", "category", "pattern", "all"]).optional()
      .describe("Filter by entity type"),
    searchTerm: z.string().optional()
      .describe("Search term to filter entity names"),
    includeRelations: z.boolean().optional()
      .describe("Include relationships in the response")
  },
  async ({ entityType, searchTerm, includeRelations }) => {
    let entities = Array.from(graph.entities.values());

    if (entityType && entityType !== "all") {
      entities = entities.filter(e => e.type === entityType);
    }

    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      entities = entities.filter(e =>
        e.name.toLowerCase().includes(term) ||
        e.observations.some(o => o.toLowerCase().includes(term))
      );
    }

    let result = `Found ${entities.length} entities:\n\n`;

    for (const entity of entities) {
      result += `[${entity.type.toUpperCase()}] ${entity.name} (${entity.id})\n`;
      if (entity.observations.length > 0) {
        result += `  Observations: ${entity.observations.slice(0, 3).join("; ")}${entity.observations.length > 3 ? "..." : ""}\n`;
      }
      result += `  Properties: ${JSON.stringify(entity.properties)}\n\n`;
    }

    if (includeRelations) {
      const relevantRelations = graph.relations.filter(r =>
        entities.some(e => e.id === r.from || e.id === r.to)
      );

      result += `\nRelationships (${relevantRelations.length}):\n`;
      for (const rel of relevantRelations) {
        const from = graph.entities.get(rel.from);
        const to = graph.entities.get(rel.to);
        result += `  ${from?.name || rel.from} --[${rel.type}]--> ${to?.name || rel.to}\n`;
      }
    }

    return {
      content: [{
        type: "text",
        text: result
      }]
    };
  }
);

// Sync Ralph Sources
server.tool(
  "sync_ralph_sources",
  "Sync sources from RalphOS sources.json into the knowledge graph",
  {
    sourcesPath: z.string().optional()
      .describe("Path to sources.json (defaults to scripts/ralph/sources.json)")
  },
  async ({ sourcesPath }) => {
    const filePath = sourcesPath || path.join(RALPH_DIR, "scripts", "ralph", "sources.json");

    if (!fs.existsSync(filePath)) {
      return {
        content: [{
          type: "text",
          text: `Sources file not found: ${filePath}`
        }]
      };
    }

    try {
      const sourcesData = JSON.parse(fs.readFileSync(filePath, "utf-8"));
      const sources = sourcesData.sources || [];
      let created = 0;
      let updated = 0;

      for (const source of sources) {
        // Check if source already exists
        const existing = Array.from(graph.entities.values())
          .find(e => e.type === "source" && e.properties.sourceId === source.id);

        if (existing) {
          // Update existing entity
          existing.properties = {
            ...existing.properties,
            status: source.status,
            pipeline: source.pipeline,
            url: source.url,
            outputDir: source.outputDir
          };
          existing.updatedAt = new Date().toISOString();
          updated++;
        } else {
          // Create new entity
          const id = generateId("source");
          const entity: Entity = {
            id,
            type: "source",
            name: source.name || source.id,
            observations: [`Status: ${source.status}`],
            properties: {
              sourceId: source.id,
              url: source.url,
              outputDir: source.outputDir,
              status: source.status,
              pipeline: source.pipeline || {}
            },
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
          };

          if (source.pipeline) {
            entity.observations.push(
              `URLs found: ${source.pipeline.urlsFound || 0}`,
              `HTML scraped: ${source.pipeline.htmlScraped || 0}`,
              `Builds extracted: ${source.pipeline.builds || 0}`,
              `Mods extracted: ${source.pipeline.mods || 0}`
            );
          }

          graph.entities.set(id, entity);
          created++;
        }
      }

      saveGraph();

      return {
        content: [{
          type: "text",
          text: `Synced ${sources.length} sources from RalphOS:\n- Created: ${created}\n- Updated: ${updated}`
        }]
      };
    } catch (error) {
      return {
        content: [{
          type: "text",
          text: `Error syncing sources: ${error}`
        }]
      };
    }
  }
);

// Get Pipeline Status
server.tool(
  "get_pipeline_status",
  "Get the current status of the Ralph scraping pipeline",
  {},
  async () => {
    const sources = Array.from(graph.entities.values())
      .filter(e => e.type === "source");

    if (sources.length === 0) {
      return {
        content: [{
          type: "text",
          text: "No sources in knowledge graph. Run sync_ralph_sources first."
        }]
      };
    }

    let result = "## Ralph Pipeline Status\n\n";

    // Summary statistics
    const statusCounts = { pending: 0, in_progress: 0, completed: 0, blocked: 0, skip: 0 };
    let totalUrls = 0;
    let totalBuilds = 0;
    let totalMods = 0;

    for (const source of sources) {
      const status = (source.properties.status as string) || "unknown";
      statusCounts[status as keyof typeof statusCounts] =
        (statusCounts[status as keyof typeof statusCounts] || 0) + 1;

      const pipeline = source.properties.pipeline as Record<string, number> || {};
      totalUrls += pipeline.urlsFound || 0;
      totalBuilds += pipeline.builds || 0;
      totalMods += pipeline.mods || 0;
    }

    result += `### Summary\n`;
    result += `- Total Sources: ${sources.length}\n`;
    result += `- Pending: ${statusCounts.pending}\n`;
    result += `- In Progress: ${statusCounts.in_progress}\n`;
    result += `- Completed: ${statusCounts.completed}\n`;
    result += `- Blocked: ${statusCounts.blocked}\n`;
    result += `- Skipped: ${statusCounts.skip}\n`;
    result += `\n### Totals\n`;
    result += `- URLs Discovered: ${totalUrls}\n`;
    result += `- Builds Extracted: ${totalBuilds}\n`;
    result += `- Modifications: ${totalMods}\n`;

    result += `\n### Source Details\n\n`;

    for (const source of sources) {
      const pipeline = source.properties.pipeline as Record<string, number> || {};
      result += `**${source.name}** (${source.properties.status})\n`;
      result += `  URLs: ${pipeline.urlsFound || 0}`;
      result += ` | HTML: ${pipeline.htmlScraped || 0}`;
      result += ` | Builds: ${pipeline.builds || 0}`;
      result += ` | Mods: ${pipeline.mods || 0}\n\n`;
    }

    return {
      content: [{
        type: "text",
        text: result
      }]
    };
  }
);

// Export to DuckDB
server.tool(
  "export_to_duckdb",
  "Export the knowledge graph to DuckDB format for analysis and visualization",
  {
    outputPath: z.string().optional()
      .describe("Path for the DuckDB SQL output file")
  },
  async ({ outputPath }) => {
    const outFile = outputPath || path.join(DATA_DIR, "knowledge-graph.sql");

    let sql = `-- Fylo-Core Knowledge Graph Export\n`;
    sql += `-- Generated: ${new Date().toISOString()}\n\n`;

    // Create tables
    sql += `-- Create entities table\n`;
    sql += `CREATE TABLE IF NOT EXISTS entities (\n`;
    sql += `  id VARCHAR PRIMARY KEY,\n`;
    sql += `  type VARCHAR,\n`;
    sql += `  name VARCHAR,\n`;
    sql += `  observations VARCHAR[],\n`;
    sql += `  properties JSON,\n`;
    sql += `  created_at TIMESTAMP,\n`;
    sql += `  updated_at TIMESTAMP\n`;
    sql += `);\n\n`;

    sql += `-- Create relations table\n`;
    sql += `CREATE TABLE IF NOT EXISTS relations (\n`;
    sql += `  id VARCHAR PRIMARY KEY,\n`;
    sql += `  from_id VARCHAR REFERENCES entities(id),\n`;
    sql += `  to_id VARCHAR REFERENCES entities(id),\n`;
    sql += `  relation_type VARCHAR,\n`;
    sql += `  properties JSON,\n`;
    sql += `  created_at TIMESTAMP\n`;
    sql += `);\n\n`;

    // Insert entities
    sql += `-- Insert entities\n`;
    for (const entity of graph.entities.values()) {
      const obs = entity.observations.map(o => `'${o.replace(/'/g, "''")}'`).join(", ");
      const props = JSON.stringify(entity.properties).replace(/'/g, "''");
      sql += `INSERT INTO entities VALUES (\n`;
      sql += `  '${entity.id}',\n`;
      sql += `  '${entity.type}',\n`;
      sql += `  '${entity.name.replace(/'/g, "''")}',\n`;
      sql += `  [${obs}],\n`;
      sql += `  '${props}',\n`;
      sql += `  '${entity.createdAt}',\n`;
      sql += `  '${entity.updatedAt}'\n`;
      sql += `);\n`;
    }

    sql += `\n-- Insert relations\n`;
    for (const rel of graph.relations) {
      const props = JSON.stringify(rel.properties).replace(/'/g, "''");
      sql += `INSERT INTO relations VALUES (\n`;
      sql += `  '${rel.id}',\n`;
      sql += `  '${rel.from}',\n`;
      sql += `  '${rel.to}',\n`;
      sql += `  '${rel.type}',\n`;
      sql += `  '${props}',\n`;
      sql += `  '${rel.createdAt}'\n`;
      sql += `);\n`;
    }

    // Add useful views
    sql += `\n-- Useful views for analysis\n`;
    sql += `CREATE VIEW source_summary AS\n`;
    sql += `SELECT \n`;
    sql += `  name,\n`;
    sql += `  json_extract_string(properties, '$.status') as status,\n`;
    sql += `  CAST(json_extract(properties, '$.pipeline.urlsFound') AS INTEGER) as urls_found,\n`;
    sql += `  CAST(json_extract(properties, '$.pipeline.htmlScraped') AS INTEGER) as html_scraped,\n`;
    sql += `  CAST(json_extract(properties, '$.pipeline.builds') AS INTEGER) as builds,\n`;
    sql += `  CAST(json_extract(properties, '$.pipeline.mods') AS INTEGER) as mods\n`;
    sql += `FROM entities\n`;
    sql += `WHERE type = 'source';\n\n`;

    sql += `CREATE VIEW entity_relationships AS\n`;
    sql += `SELECT \n`;
    sql += `  e1.name as from_entity,\n`;
    sql += `  e1.type as from_type,\n`;
    sql += `  r.relation_type,\n`;
    sql += `  e2.name as to_entity,\n`;
    sql += `  e2.type as to_type\n`;
    sql += `FROM relations r\n`;
    sql += `JOIN entities e1 ON r.from_id = e1.id\n`;
    sql += `JOIN entities e2 ON r.to_id = e2.id;\n`;

    ensureDataDir();
    fs.writeFileSync(outFile, sql);

    return {
      content: [{
        type: "text",
        text: `Exported knowledge graph to DuckDB SQL:\n- File: ${outFile}\n- Entities: ${graph.entities.size}\n- Relations: ${graph.relations.length}\n\nLoad in DuckDB with:\n  .read ${outFile}`
      }]
    };
  }
);

// Visualize Graph
server.tool(
  "visualize_graph",
  "Generate a Mermaid diagram of the knowledge graph for visualization",
  {
    entityType: z.enum(["source", "url", "build", "modification", "category", "pattern", "all"]).optional()
      .describe("Focus on specific entity type"),
    maxNodes: z.number().optional()
      .describe("Maximum number of nodes to include (default: 50)")
  },
  async ({ entityType, maxNodes }) => {
    const limit = maxNodes || 50;
    let entities = Array.from(graph.entities.values());

    if (entityType && entityType !== "all") {
      entities = entities.filter(e => e.type === entityType);
    }

    entities = entities.slice(0, limit);
    const entityIds = new Set(entities.map(e => e.id));

    let mermaid = "```mermaid\ngraph TD\n";

    // Add subgraphs for each type
    const typeGroups: Record<string, Entity[]> = {};
    for (const entity of entities) {
      if (!typeGroups[entity.type]) {
        typeGroups[entity.type] = [];
      }
      typeGroups[entity.type].push(entity);
    }

    // Define node styles
    mermaid += "  %% Node styles\n";
    mermaid += "  classDef source fill:#e1f5fe,stroke:#01579b\n";
    mermaid += "  classDef url fill:#fff3e0,stroke:#e65100\n";
    mermaid += "  classDef build fill:#e8f5e9,stroke:#1b5e20\n";
    mermaid += "  classDef modification fill:#fce4ec,stroke:#880e4f\n";
    mermaid += "  classDef category fill:#f3e5f5,stroke:#4a148c\n";
    mermaid += "  classDef pattern fill:#e0f2f1,stroke:#004d40\n\n";

    // Add nodes by type
    for (const [type, typeEntities] of Object.entries(typeGroups)) {
      mermaid += `  subgraph ${type.toUpperCase()}\n`;
      for (const entity of typeEntities) {
        const shortId = entity.id.split("_").slice(-1)[0];
        const label = entity.name.replace(/["\[\]]/g, "").slice(0, 30);
        mermaid += `    ${shortId}["${label}"]\n`;
      }
      mermaid += "  end\n";
    }

    // Add relationships
    const relevantRelations = graph.relations.filter(r =>
      entityIds.has(r.from) && entityIds.has(r.to)
    );

    mermaid += "\n  %% Relationships\n";
    for (const rel of relevantRelations) {
      const fromId = rel.from.split("_").slice(-1)[0];
      const toId = rel.to.split("_").slice(-1)[0];
      mermaid += `  ${fromId} -->|${rel.type}| ${toId}\n`;
    }

    // Apply styles
    mermaid += "\n  %% Apply styles\n";
    for (const entity of entities) {
      const shortId = entity.id.split("_").slice(-1)[0];
      mermaid += `  class ${shortId} ${entity.type}\n`;
    }

    mermaid += "```\n";

    return {
      content: [{
        type: "text",
        text: `# Knowledge Graph Visualization\n\n${mermaid}\n\n**Legend:**\n- Blue: Sources\n- Orange: URLs\n- Green: Builds\n- Pink: Modifications\n- Purple: Categories\n- Teal: Patterns\n\nShowing ${entities.length} entities and ${relevantRelations.length} relationships.`
      }]
    };
  }
);

// Ingest Build Data
server.tool(
  "ingest_builds",
  "Ingest build data from a builds.json file into the knowledge graph",
  {
    sourceId: z.string().describe("ID of the source entity"),
    buildsPath: z.string().describe("Path to the builds.json file")
  },
  async ({ sourceId, buildsPath }) => {
    const source = graph.entities.get(sourceId);
    if (!source) {
      return {
        content: [{
          type: "text",
          text: `Source entity not found: ${sourceId}`
        }]
      };
    }

    if (!fs.existsSync(buildsPath)) {
      return {
        content: [{
          type: "text",
          text: `Builds file not found: ${buildsPath}`
        }]
      };
    }

    try {
      const builds = JSON.parse(fs.readFileSync(buildsPath, "utf-8"));
      const buildList = Array.isArray(builds) ? builds : builds.builds || [];
      let created = 0;

      for (const build of buildList) {
        const buildId = generateId("build");
        const entity: Entity = {
          id: buildId,
          type: "build",
          name: build.build_title || `${build.year || ""} ${build.make || ""} ${build.model || ""}`.trim() || "Unknown Build",
          observations: [],
          properties: {
            buildId: build.build_id,
            year: build.year,
            make: build.make,
            model: build.model,
            trim: build.trim,
            generation: build.generation,
            engine: build.engine,
            transmission: build.transmission,
            drivetrain: build.drivetrain,
            buildType: build.build_type,
            modificationLevel: build.modification_level,
            confidence: build.extraction_confidence,
            sourceUrl: build.source_url
          },
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString()
        };

        // Add observations
        if (build.build_type) {
          entity.observations.push(`Build type: ${build.build_type}`);
        }
        if (build.modification_level) {
          entity.observations.push(`Mod level: ${build.modification_level}`);
        }
        if (build.engine) {
          entity.observations.push(`Engine: ${build.engine}`);
        }

        graph.entities.set(buildId, entity);

        // Create relationship to source
        const relation: Relation = {
          id: generateId("rel"),
          from: sourceId,
          to: buildId,
          type: "contains_build",
          properties: {},
          createdAt: new Date().toISOString()
        };
        graph.relations.push(relation);

        // Process modifications if present
        if (build.modifications && Array.isArray(build.modifications)) {
          for (const mod of build.modifications) {
            const modId = generateId("modification");
            const modEntity: Entity = {
              id: modId,
              type: "modification",
              name: mod.name || "Unknown Modification",
              observations: [],
              properties: {
                category: mod.category,
                brand: mod.brand,
                partNumber: mod.part_number,
                details: mod.details
              },
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString()
            };

            if (mod.brand) {
              modEntity.observations.push(`Brand: ${mod.brand}`);
            }
            if (mod.category) {
              modEntity.observations.push(`Category: ${mod.category}`);
            }

            graph.entities.set(modId, modEntity);

            // Create relationship to build
            const modRelation: Relation = {
              id: generateId("rel"),
              from: buildId,
              to: modId,
              type: "has_modification",
              properties: {},
              createdAt: new Date().toISOString()
            };
            graph.relations.push(modRelation);
          }
        }

        created++;
      }

      saveGraph();

      return {
        content: [{
          type: "text",
          text: `Ingested ${created} builds from ${buildsPath} into knowledge graph`
        }]
      };
    } catch (error) {
      return {
        content: [{
          type: "text",
          text: `Error ingesting builds: ${error}`
        }]
      };
    }
  }
);

// Get Graph Statistics
server.tool(
  "get_graph_stats",
  "Get statistics about the current knowledge graph",
  {},
  async () => {
    const stats: Record<string, number> = {};

    for (const entity of graph.entities.values()) {
      stats[entity.type] = (stats[entity.type] || 0) + 1;
    }

    const relationTypes: Record<string, number> = {};
    for (const rel of graph.relations) {
      relationTypes[rel.type] = (relationTypes[rel.type] || 0) + 1;
    }

    let result = `## Knowledge Graph Statistics\n\n`;
    result += `**Last Updated:** ${graph.metadata.lastUpdated}\n`;
    result += `**Version:** ${graph.metadata.version}\n\n`;
    result += `### Entities (${graph.entities.size} total)\n`;

    for (const [type, count] of Object.entries(stats).sort((a, b) => b[1] - a[1])) {
      result += `- ${type}: ${count}\n`;
    }

    result += `\n### Relationships (${graph.relations.length} total)\n`;
    for (const [type, count] of Object.entries(relationTypes).sort((a, b) => b[1] - a[1])) {
      result += `- ${type}: ${count}\n`;
    }

    // Total observations
    let totalObs = 0;
    for (const entity of graph.entities.values()) {
      totalObs += entity.observations.length;
    }
    result += `\n### Observations\n`;
    result += `- Total: ${totalObs}\n`;
    result += `- Avg per entity: ${(totalObs / graph.entities.size).toFixed(1)}\n`;

    return {
      content: [{
        type: "text",
        text: result
      }]
    };
  }
);

// ============== VALIDATION SUITE ==============

// Validation result interface
interface ValidationResult {
  passed: boolean;
  stage: string;
  checks: Array<{
    name: string;
    passed: boolean;
    message: string;
    details?: unknown;
  }>;
  score: number;
  timestamp: string;
}

// Validate Pipeline Stage
server.tool(
  "validate_pipeline_stage",
  "Validate that a pipeline stage completed successfully with proper outputs",
  {
    sourceDir: z.string().describe("Path to the source data directory (e.g., data/lomar_refined)"),
    stage: z.enum(["url_discovery", "html_scrape", "build_extraction", "mod_extraction", "all"])
      .describe("Pipeline stage to validate")
  },
  async ({ sourceDir, stage }) => {
    const results: ValidationResult[] = [];
    const baseDir = path.isAbsolute(sourceDir) ? sourceDir : path.join(RALPH_DIR, sourceDir);

    // URL Discovery validation
    if (stage === "url_discovery" || stage === "all") {
      const urlsFile = path.join(baseDir, "urls.json");
      const checks: ValidationResult["checks"] = [];

      // Check file exists
      const fileExists = fs.existsSync(urlsFile);
      checks.push({
        name: "urls.json exists",
        passed: fileExists,
        message: fileExists ? "File found" : "urls.json not found"
      });

      if (fileExists) {
        try {
          const data = JSON.parse(fs.readFileSync(urlsFile, "utf-8"));
          const urls = data.urls || [];

          // Check has URLs
          checks.push({
            name: "Has URLs",
            passed: urls.length > 0,
            message: `Found ${urls.length} URLs`,
            details: { count: urls.length }
          });

          // Check URL validity
          const validUrls = urls.filter((u: string) => {
            try { new URL(u); return true; } catch { return false; }
          });
          const validityRate = urls.length > 0 ? validUrls.length / urls.length : 0;
          checks.push({
            name: "URL validity",
            passed: validityRate >= 0.95,
            message: `${(validityRate * 100).toFixed(1)}% valid URLs`,
            details: { valid: validUrls.length, total: urls.length }
          });

          // Check for duplicates
          const uniqueUrls = new Set(urls);
          const hasDuplicates = uniqueUrls.size < urls.length;
          checks.push({
            name: "No duplicates",
            passed: !hasDuplicates,
            message: hasDuplicates ? `${urls.length - uniqueUrls.size} duplicates found` : "No duplicates",
            details: { unique: uniqueUrls.size, total: urls.length }
          });

          // Check metadata
          checks.push({
            name: "Has metadata",
            passed: !!data.lastUpdated,
            message: data.lastUpdated ? `Last updated: ${data.lastUpdated}` : "Missing lastUpdated field"
          });
        } catch (error) {
          checks.push({
            name: "Valid JSON",
            passed: false,
            message: `Parse error: ${error}`
          });
        }
      }

      const passed = checks.filter(c => c.passed).length;
      results.push({
        passed: passed === checks.length,
        stage: "url_discovery",
        checks,
        score: checks.length > 0 ? (passed / checks.length) * 100 : 0,
        timestamp: new Date().toISOString()
      });
    }

    // HTML Scrape validation
    if (stage === "html_scrape" || stage === "all") {
      const htmlDir = path.join(baseDir, "html");
      const progressFile = path.join(baseDir, "scrape_progress.json");
      const urlsFile = path.join(baseDir, "urls.json");
      const checks: ValidationResult["checks"] = [];

      // Check html directory exists
      const dirExists = fs.existsSync(htmlDir);
      checks.push({
        name: "html/ directory exists",
        passed: dirExists,
        message: dirExists ? "Directory found" : "html/ directory not found"
      });

      if (dirExists) {
        const htmlFiles = fs.readdirSync(htmlDir).filter(f => f.endsWith(".html"));

        // Check has HTML files
        checks.push({
          name: "Has HTML files",
          passed: htmlFiles.length > 0,
          message: `Found ${htmlFiles.length} HTML files`,
          details: { count: htmlFiles.length }
        });

        // Check file sizes (not empty)
        const nonEmptyFiles = htmlFiles.filter(f => {
          const stat = fs.statSync(path.join(htmlDir, f));
          return stat.size > 100; // Minimum reasonable HTML size
        });
        const nonEmptyRate = htmlFiles.length > 0 ? nonEmptyFiles.length / htmlFiles.length : 0;
        checks.push({
          name: "Files not empty",
          passed: nonEmptyRate >= 0.9,
          message: `${nonEmptyFiles.length}/${htmlFiles.length} files have content`,
          details: { nonEmpty: nonEmptyFiles.length, total: htmlFiles.length }
        });

        // Compare to URL count if available
        if (fs.existsSync(urlsFile)) {
          try {
            const urlData = JSON.parse(fs.readFileSync(urlsFile, "utf-8"));
            const urlCount = (urlData.urls || []).length;
            const completionRate = urlCount > 0 ? htmlFiles.length / urlCount : 0;
            checks.push({
              name: "Scrape completion",
              passed: completionRate >= 0.9,
              message: `${(completionRate * 100).toFixed(1)}% of URLs scraped`,
              details: { scraped: htmlFiles.length, total: urlCount }
            });
          } catch { /* ignore */ }
        }
      }

      // Check progress file
      if (fs.existsSync(progressFile)) {
        try {
          const progress = JSON.parse(fs.readFileSync(progressFile, "utf-8"));
          checks.push({
            name: "Progress tracking",
            passed: true,
            message: `Progress: ${progress.completed || 0}/${progress.total || 0}`,
            details: progress
          });
        } catch { /* ignore */ }
      }

      const passed = checks.filter(c => c.passed).length;
      results.push({
        passed: passed === checks.length,
        stage: "html_scrape",
        checks,
        score: checks.length > 0 ? (passed / checks.length) * 100 : 0,
        timestamp: new Date().toISOString()
      });
    }

    // Build Extraction validation
    if (stage === "build_extraction" || stage === "all") {
      const buildsFile = path.join(baseDir, "builds.json");
      const checks: ValidationResult["checks"] = [];

      const fileExists = fs.existsSync(buildsFile);
      checks.push({
        name: "builds.json exists",
        passed: fileExists,
        message: fileExists ? "File found" : "builds.json not found"
      });

      if (fileExists) {
        try {
          const data = JSON.parse(fs.readFileSync(buildsFile, "utf-8"));
          const builds = Array.isArray(data) ? data : data.builds || [];

          checks.push({
            name: "Has builds",
            passed: builds.length > 0,
            message: `Found ${builds.length} builds`,
            details: { count: builds.length }
          });

          // Check required fields
          const requiredFields = ["build_id", "year", "make", "model"];
          const completeBuilds = builds.filter((b: Record<string, unknown>) =>
            requiredFields.every(f => b[f] !== undefined && b[f] !== null && b[f] !== "")
          );
          const completionRate = builds.length > 0 ? completeBuilds.length / builds.length : 0;
          checks.push({
            name: "Required fields present",
            passed: completionRate >= 0.8,
            message: `${(completionRate * 100).toFixed(1)}% have required fields`,
            details: { complete: completeBuilds.length, total: builds.length, requiredFields }
          });

          // Check for build_id uniqueness
          const buildIds = builds.map((b: Record<string, unknown>) => b.build_id).filter(Boolean);
          const uniqueIds = new Set(buildIds);
          checks.push({
            name: "Unique build IDs",
            passed: uniqueIds.size === buildIds.length,
            message: uniqueIds.size === buildIds.length ? "All IDs unique" : `${buildIds.length - uniqueIds.size} duplicate IDs`,
            details: { unique: uniqueIds.size, total: buildIds.length }
          });

          // Check confidence scores if present
          const withConfidence = builds.filter((b: Record<string, unknown>) =>
            typeof b.extraction_confidence === "number"
          );
          if (withConfidence.length > 0) {
            const avgConfidence = withConfidence.reduce((sum: number, b: Record<string, unknown>) =>
              sum + (b.extraction_confidence as number), 0) / withConfidence.length;
            checks.push({
              name: "Extraction confidence",
              passed: avgConfidence >= 0.7,
              message: `Average confidence: ${(avgConfidence * 100).toFixed(1)}%`,
              details: { average: avgConfidence, count: withConfidence.length }
            });
          }
        } catch (error) {
          checks.push({
            name: "Valid JSON",
            passed: false,
            message: `Parse error: ${error}`
          });
        }
      }

      const passed = checks.filter(c => c.passed).length;
      results.push({
        passed: passed === checks.length,
        stage: "build_extraction",
        checks,
        score: checks.length > 0 ? (passed / checks.length) * 100 : 0,
        timestamp: new Date().toISOString()
      });
    }

    // Mod Extraction validation
    if (stage === "mod_extraction" || stage === "all") {
      const modsFile = path.join(baseDir, "mods.json");
      const checks: ValidationResult["checks"] = [];

      const fileExists = fs.existsSync(modsFile);
      checks.push({
        name: "mods.json exists",
        passed: fileExists,
        message: fileExists ? "File found" : "mods.json not found (may be embedded in builds)"
      });

      if (fileExists) {
        try {
          const data = JSON.parse(fs.readFileSync(modsFile, "utf-8"));
          const mods = Array.isArray(data) ? data : data.mods || data.modifications || [];

          checks.push({
            name: "Has modifications",
            passed: mods.length > 0,
            message: `Found ${mods.length} modifications`,
            details: { count: mods.length }
          });

          // Check categorization
          const categorized = mods.filter((m: Record<string, unknown>) => m.category);
          const catRate = mods.length > 0 ? categorized.length / mods.length : 0;
          checks.push({
            name: "Categorization",
            passed: catRate >= 0.7,
            message: `${(catRate * 100).toFixed(1)}% have categories`,
            details: { categorized: categorized.length, total: mods.length }
          });
        } catch (error) {
          checks.push({
            name: "Valid JSON",
            passed: false,
            message: `Parse error: ${error}`
          });
        }
      }

      const passed = checks.filter(c => c.passed).length;
      results.push({
        passed: passed === checks.length,
        stage: "mod_extraction",
        checks,
        score: checks.length > 0 ? (passed / checks.length) * 100 : 0,
        timestamp: new Date().toISOString()
      });
    }

    // Format output
    let output = `## Pipeline Validation Report\n`;
    output += `**Source:** ${sourceDir}\n`;
    output += `**Validated:** ${new Date().toISOString()}\n\n`;

    for (const result of results) {
      const icon = result.passed ? "✅" : "❌";
      output += `### ${icon} ${result.stage} (Score: ${result.score.toFixed(0)}%)\n\n`;

      for (const check of result.checks) {
        const checkIcon = check.passed ? "✓" : "✗";
        output += `- ${checkIcon} **${check.name}**: ${check.message}\n`;
      }
      output += "\n";
    }

    const overallScore = results.length > 0
      ? results.reduce((sum, r) => sum + r.score, 0) / results.length
      : 0;
    const allPassed = results.every(r => r.passed);

    output += `---\n**Overall Score:** ${overallScore.toFixed(0)}%\n`;
    output += `**Status:** ${allPassed ? "✅ ALL STAGES PASSED" : "❌ SOME STAGES FAILED"}\n`;

    // Record validation in knowledge graph
    const validationEntity: Entity = {
      id: generateId("validation"),
      type: "pattern",
      name: `Validation: ${sourceDir} - ${stage}`,
      observations: results.map(r => `${r.stage}: ${r.passed ? "PASSED" : "FAILED"} (${r.score.toFixed(0)}%)`),
      properties: {
        sourceDir,
        stage,
        results,
        overallScore,
        allPassed
      },
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };
    graph.entities.set(validationEntity.id, validationEntity);
    saveGraph();

    return {
      content: [{
        type: "text",
        text: output
      }]
    };
  }
);

// ============== ASSERTION FRAMEWORK ==============

// Assert Condition
server.tool(
  "assert_condition",
  "Assert a condition and return pass/fail result for task verification",
  {
    condition: z.enum([
      "file_exists",
      "file_not_empty",
      "json_valid",
      "count_gte",
      "count_lte",
      "count_eq",
      "contains_text",
      "matches_pattern"
    ]).describe("Type of assertion to check"),
    target: z.string().describe("File path or value to check"),
    value: z.union([z.string(), z.number()]).optional()
      .describe("Expected value for comparison assertions"),
    jsonPath: z.string().optional()
      .describe("JSON path for extracting count (e.g., 'urls' or 'builds.length')"),
    message: z.string().optional()
      .describe("Custom message for assertion result")
  },
  async ({ condition, target, value, jsonPath, message }) => {
    let passed = false;
    let actualValue: unknown;
    let details = "";

    const targetPath = path.isAbsolute(target) ? target : path.join(RALPH_DIR, target);

    try {
      switch (condition) {
        case "file_exists":
          passed = fs.existsSync(targetPath);
          details = passed ? `File exists: ${target}` : `File not found: ${target}`;
          break;

        case "file_not_empty":
          if (fs.existsSync(targetPath)) {
            const stat = fs.statSync(targetPath);
            passed = stat.size > 0;
            actualValue = stat.size;
            details = `File size: ${stat.size} bytes`;
          } else {
            details = `File not found: ${target}`;
          }
          break;

        case "json_valid":
          if (fs.existsSync(targetPath)) {
            try {
              JSON.parse(fs.readFileSync(targetPath, "utf-8"));
              passed = true;
              details = "Valid JSON";
            } catch (e) {
              details = `Invalid JSON: ${e}`;
            }
          } else {
            details = `File not found: ${target}`;
          }
          break;

        case "count_gte":
        case "count_lte":
        case "count_eq":
          if (fs.existsSync(targetPath)) {
            try {
              const data = JSON.parse(fs.readFileSync(targetPath, "utf-8"));
              // Extract count from JSON path
              let countValue = data;
              if (jsonPath) {
                for (const key of jsonPath.split(".")) {
                  if (key === "length" && Array.isArray(countValue)) {
                    countValue = countValue.length;
                  } else {
                    countValue = countValue?.[key];
                  }
                }
              }
              if (Array.isArray(countValue)) {
                countValue = countValue.length;
              }
              actualValue = countValue;
              const expected = Number(value);

              if (condition === "count_gte") {
                passed = countValue >= expected;
                details = `Count ${countValue} >= ${expected}: ${passed ? "PASS" : "FAIL"}`;
              } else if (condition === "count_lte") {
                passed = countValue <= expected;
                details = `Count ${countValue} <= ${expected}: ${passed ? "PASS" : "FAIL"}`;
              } else {
                passed = countValue === expected;
                details = `Count ${countValue} === ${expected}: ${passed ? "PASS" : "FAIL"}`;
              }
            } catch (e) {
              details = `Error reading JSON: ${e}`;
            }
          } else {
            details = `File not found: ${target}`;
          }
          break;

        case "contains_text":
          if (fs.existsSync(targetPath)) {
            const content = fs.readFileSync(targetPath, "utf-8");
            passed = content.includes(String(value));
            details = passed ? `Contains "${value}"` : `Does not contain "${value}"`;
          } else {
            details = `File not found: ${target}`;
          }
          break;

        case "matches_pattern":
          if (fs.existsSync(targetPath)) {
            const content = fs.readFileSync(targetPath, "utf-8");
            const regex = new RegExp(String(value));
            passed = regex.test(content);
            details = passed ? `Matches pattern: ${value}` : `Does not match pattern: ${value}`;
          } else {
            details = `File not found: ${target}`;
          }
          break;
      }
    } catch (error) {
      details = `Error: ${error}`;
    }

    const icon = passed ? "✅ PASS" : "❌ FAIL";
    const customMsg = message ? `\n**Message:** ${message}` : "";

    return {
      content: [{
        type: "text",
        text: `## Assertion Result: ${icon}\n\n**Condition:** ${condition}\n**Target:** ${target}\n**Expected:** ${value ?? "N/A"}\n**Actual:** ${actualValue ?? "N/A"}\n**Details:** ${details}${customMsg}`
      }]
    };
  }
);

// Batch Assert
server.tool(
  "assert_batch",
  "Run multiple assertions at once for comprehensive validation",
  {
    assertions: z.array(z.object({
      condition: z.string(),
      target: z.string(),
      value: z.union([z.string(), z.number()]).optional(),
      jsonPath: z.string().optional(),
      message: z.string().optional()
    })).describe("Array of assertions to check")
  },
  async ({ assertions }) => {
    const results: Array<{ passed: boolean; condition: string; target: string; message: string }> = [];

    for (const assertion of assertions) {
      let passed = false;
      let message = "";
      const targetPath = path.isAbsolute(assertion.target)
        ? assertion.target
        : path.join(RALPH_DIR, assertion.target);

      try {
        switch (assertion.condition) {
          case "file_exists":
            passed = fs.existsSync(targetPath);
            message = passed ? "File exists" : "File not found";
            break;

          case "file_not_empty":
            if (fs.existsSync(targetPath)) {
              passed = fs.statSync(targetPath).size > 0;
              message = passed ? "File has content" : "File is empty";
            } else {
              message = "File not found";
            }
            break;

          case "count_gte":
            if (fs.existsSync(targetPath)) {
              const data = JSON.parse(fs.readFileSync(targetPath, "utf-8"));
              let count = data;
              if (assertion.jsonPath) {
                for (const key of assertion.jsonPath.split(".")) {
                  count = key === "length" && Array.isArray(count) ? count.length : count?.[key];
                }
              }
              if (Array.isArray(count)) count = count.length;
              passed = count >= Number(assertion.value);
              message = `Count: ${count} (expected >= ${assertion.value})`;
            }
            break;

          default:
            message = `Unknown condition: ${assertion.condition}`;
        }
      } catch (error) {
        message = `Error: ${error}`;
      }

      results.push({
        passed,
        condition: assertion.condition,
        target: assertion.target,
        message: assertion.message || message
      });
    }

    const passedCount = results.filter(r => r.passed).length;
    const allPassed = passedCount === results.length;

    let output = `## Batch Assertion Results\n\n`;
    output += `**Total:** ${results.length} | **Passed:** ${passedCount} | **Failed:** ${results.length - passedCount}\n\n`;

    for (const result of results) {
      const icon = result.passed ? "✓" : "✗";
      output += `- ${icon} **${result.condition}** on \`${result.target}\`: ${result.message}\n`;
    }

    output += `\n---\n**Overall:** ${allPassed ? "✅ ALL PASSED" : "❌ SOME FAILED"}`;

    return {
      content: [{
        type: "text",
        text: output
      }]
    };
  }
);

// ============== QUALITY SCORING ==============

// Get Quality Report
server.tool(
  "get_quality_report",
  "Generate a comprehensive quality report for a source with numeric scores",
  {
    sourceDir: z.string().describe("Path to source data directory")
  },
  async ({ sourceDir }) => {
    const baseDir = path.isAbsolute(sourceDir) ? sourceDir : path.join(RALPH_DIR, sourceDir);
    const scores: Record<string, number> = {};
    const details: Record<string, string[]> = {};

    // URL Quality
    const urlsFile = path.join(baseDir, "urls.json");
    if (fs.existsSync(urlsFile)) {
      try {
        const data = JSON.parse(fs.readFileSync(urlsFile, "utf-8"));
        const urls = data.urls || [];

        const validUrls = urls.filter((u: string) => {
          try { new URL(u); return true; } catch { return false; }
        });
        const uniqueUrls = new Set(urls);

        scores.url_validity = urls.length > 0 ? (validUrls.length / urls.length) * 100 : 0;
        scores.url_uniqueness = urls.length > 0 ? (uniqueUrls.size / urls.length) * 100 : 0;
        scores.url_count = Math.min(urls.length / 10, 100); // Scale: 1000+ URLs = 100%

        details.urls = [
          `Total: ${urls.length}`,
          `Valid: ${validUrls.length}`,
          `Unique: ${uniqueUrls.size}`
        ];
      } catch { scores.url_validity = 0; }
    }

    // HTML Quality
    const htmlDir = path.join(baseDir, "html");
    if (fs.existsSync(htmlDir)) {
      const htmlFiles = fs.readdirSync(htmlDir).filter(f => f.endsWith(".html"));
      const nonEmpty = htmlFiles.filter(f => fs.statSync(path.join(htmlDir, f)).size > 100);

      scores.html_coverage = fs.existsSync(urlsFile)
        ? (() => {
            try {
              const urls = JSON.parse(fs.readFileSync(urlsFile, "utf-8")).urls || [];
              return urls.length > 0 ? (htmlFiles.length / urls.length) * 100 : 0;
            } catch { return 0; }
          })()
        : 0;
      scores.html_quality = htmlFiles.length > 0 ? (nonEmpty.length / htmlFiles.length) * 100 : 0;

      details.html = [
        `Files: ${htmlFiles.length}`,
        `Non-empty: ${nonEmpty.length}`,
        `Coverage: ${scores.html_coverage.toFixed(1)}%`
      ];
    }

    // Build Quality
    const buildsFile = path.join(baseDir, "builds.json");
    if (fs.existsSync(buildsFile)) {
      try {
        const data = JSON.parse(fs.readFileSync(buildsFile, "utf-8"));
        const builds = Array.isArray(data) ? data : data.builds || [];

        const requiredFields = ["build_id", "year", "make", "model"];
        const complete = builds.filter((b: Record<string, unknown>) =>
          requiredFields.every(f => b[f])
        );

        const withConfidence = builds.filter((b: Record<string, unknown>) =>
          typeof b.extraction_confidence === "number"
        );
        const avgConfidence = withConfidence.length > 0
          ? withConfidence.reduce((s: number, b: Record<string, unknown>) =>
              s + (b.extraction_confidence as number), 0) / withConfidence.length
          : 0;

        scores.build_completeness = builds.length > 0 ? (complete.length / builds.length) * 100 : 0;
        scores.build_confidence = avgConfidence * 100;
        scores.build_count = Math.min(builds.length, 100); // Scale: 100+ builds = 100

        details.builds = [
          `Total: ${builds.length}`,
          `Complete: ${complete.length}`,
          `Avg confidence: ${(avgConfidence * 100).toFixed(1)}%`
        ];
      } catch { scores.build_completeness = 0; }
    }

    // Calculate overall score (weighted average)
    const weights: Record<string, number> = {
      url_validity: 0.15,
      url_uniqueness: 0.1,
      url_count: 0.1,
      html_coverage: 0.2,
      html_quality: 0.15,
      build_completeness: 0.15,
      build_confidence: 0.1,
      build_count: 0.05
    };

    let overallScore = 0;
    let totalWeight = 0;
    for (const [key, weight] of Object.entries(weights)) {
      if (scores[key] !== undefined) {
        overallScore += scores[key] * weight;
        totalWeight += weight;
      }
    }
    overallScore = totalWeight > 0 ? overallScore / totalWeight : 0;

    // Format output
    let output = `## Quality Report: ${sourceDir}\n\n`;
    output += `### Overall Score: ${overallScore.toFixed(1)}/100\n\n`;

    // Score bar visualization
    const barLength = 20;
    const filledBars = Math.round((overallScore / 100) * barLength);
    const bar = "█".repeat(filledBars) + "░".repeat(barLength - filledBars);
    output += `\`[${bar}]\`\n\n`;

    output += `### Detailed Scores\n\n`;
    output += `| Metric | Score | Status |\n`;
    output += `|--------|-------|--------|\n`;

    for (const [key, score] of Object.entries(scores)) {
      const status = score >= 80 ? "✅" : score >= 50 ? "⚠️" : "❌";
      output += `| ${key.replace(/_/g, " ")} | ${score.toFixed(1)} | ${status} |\n`;
    }

    output += `\n### Details\n\n`;
    for (const [section, items] of Object.entries(details)) {
      output += `**${section}:** ${items.join(" | ")}\n`;
    }

    // Grade
    const grade = overallScore >= 90 ? "A" :
                  overallScore >= 80 ? "B" :
                  overallScore >= 70 ? "C" :
                  overallScore >= 60 ? "D" : "F";
    output += `\n---\n**Grade:** ${grade}\n`;

    return {
      content: [{
        type: "text",
        text: output
      }]
    };
  }
);

// ============== COMPLETION PROOFS ==============

// Verify Story Complete
server.tool(
  "verify_story_complete",
  "Verify that a user story's acceptance criteria have been met",
  {
    storyId: z.string().describe("User story ID (e.g., US-001)"),
    criteria: z.array(z.object({
      type: z.enum(["file_exists", "count_gte", "directory_has_files", "json_has_field"]),
      target: z.string(),
      value: z.union([z.string(), z.number()]).optional(),
      field: z.string().optional()
    })).describe("Acceptance criteria to verify")
  },
  async ({ storyId, criteria }) => {
    const results: Array<{ criterion: string; passed: boolean; evidence: string }> = [];

    for (const c of criteria) {
      let passed = false;
      let evidence = "";
      const targetPath = path.isAbsolute(c.target) ? c.target : path.join(RALPH_DIR, c.target);

      try {
        switch (c.type) {
          case "file_exists":
            passed = fs.existsSync(targetPath);
            evidence = passed
              ? `File exists: ${c.target} (${fs.statSync(targetPath).size} bytes)`
              : `File not found: ${c.target}`;
            break;

          case "count_gte":
            if (fs.existsSync(targetPath)) {
              const data = JSON.parse(fs.readFileSync(targetPath, "utf-8"));
              const items = Array.isArray(data) ? data : data[c.field || "items"] || [];
              passed = items.length >= Number(c.value);
              evidence = `Count: ${items.length} (required: >= ${c.value})`;
            } else {
              evidence = "File not found";
            }
            break;

          case "directory_has_files":
            if (fs.existsSync(targetPath) && fs.statSync(targetPath).isDirectory()) {
              const files = fs.readdirSync(targetPath);
              passed = files.length >= Number(c.value || 1);
              evidence = `Directory has ${files.length} files (required: >= ${c.value || 1})`;
            } else {
              evidence = "Directory not found";
            }
            break;

          case "json_has_field":
            if (fs.existsSync(targetPath)) {
              const data = JSON.parse(fs.readFileSync(targetPath, "utf-8"));
              const fieldName = c.field || "";
              passed = fieldName ? data[fieldName] !== undefined : false;
              evidence = passed
                ? `Field "${fieldName}" present with value: ${JSON.stringify(data[fieldName]).slice(0, 50)}`
                : `Field "${fieldName}" not found`;
            } else {
              evidence = "File not found";
            }
            break;
        }
      } catch (error) {
        evidence = `Error: ${error}`;
      }

      results.push({
        criterion: `${c.type}: ${c.target}${c.value ? ` (${c.value})` : ""}`,
        passed,
        evidence
      });
    }

    const allPassed = results.every(r => r.passed);
    const passedCount = results.filter(r => r.passed).length;

    let output = `## Story Verification: ${storyId}\n\n`;
    output += `**Status:** ${allPassed ? "✅ COMPLETE" : "❌ INCOMPLETE"}\n`;
    output += `**Criteria Met:** ${passedCount}/${results.length}\n\n`;

    output += `### Acceptance Criteria\n\n`;
    for (const result of results) {
      const icon = result.passed ? "✅" : "❌";
      output += `${icon} **${result.criterion}**\n`;
      output += `   Evidence: ${result.evidence}\n\n`;
    }

    // Record completion proof
    const proofEntity: Entity = {
      id: generateId("pattern"),
      type: "pattern",
      name: `Completion Proof: ${storyId}`,
      observations: [
        `Verified: ${new Date().toISOString()}`,
        `Status: ${allPassed ? "COMPLETE" : "INCOMPLETE"}`,
        `Criteria: ${passedCount}/${results.length} passed`
      ],
      properties: {
        storyId,
        results,
        allPassed,
        verifiedAt: new Date().toISOString()
      },
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };
    graph.entities.set(proofEntity.id, proofEntity);
    saveGraph();

    return {
      content: [{
        type: "text",
        text: output
      }]
    };
  }
);

// Get Completion Proof
server.tool(
  "get_completion_proof",
  "Generate a comprehensive completion proof with evidence for a source",
  {
    sourceDir: z.string().describe("Path to source data directory"),
    storyId: z.string().optional().describe("Optional story ID for context")
  },
  async ({ sourceDir, storyId }) => {
    const baseDir = path.isAbsolute(sourceDir) ? sourceDir : path.join(RALPH_DIR, sourceDir);
    const evidence: Array<{ item: string; status: string; value: string }> = [];

    // Collect evidence
    const files = [
      { path: "urls.json", key: "urls" },
      { path: "builds.json", key: "builds" },
      { path: "mods.json", key: "mods" },
      { path: "scrape_progress.json", key: null }
    ];

    for (const file of files) {
      const filePath = path.join(baseDir, file.path);
      if (fs.existsSync(filePath)) {
        try {
          const data = JSON.parse(fs.readFileSync(filePath, "utf-8"));
          const count = file.key
            ? (Array.isArray(data) ? data.length : (data[file.key] || []).length)
            : "N/A";
          const size = fs.statSync(filePath).size;
          evidence.push({
            item: file.path,
            status: "✅ EXISTS",
            value: `${count} items, ${(size / 1024).toFixed(1)}KB`
          });
        } catch {
          evidence.push({
            item: file.path,
            status: "⚠️ INVALID",
            value: "Parse error"
          });
        }
      } else {
        evidence.push({
          item: file.path,
          status: "❌ MISSING",
          value: "-"
        });
      }
    }

    // Check HTML directory
    const htmlDir = path.join(baseDir, "html");
    if (fs.existsSync(htmlDir)) {
      const htmlFiles = fs.readdirSync(htmlDir).filter(f => f.endsWith(".html"));
      evidence.push({
        item: "html/",
        status: "✅ EXISTS",
        value: `${htmlFiles.length} HTML files`
      });
    } else {
      evidence.push({
        item: "html/",
        status: "❌ MISSING",
        value: "-"
      });
    }

    // Generate proof
    let output = `## Completion Proof\n\n`;
    output += `**Source:** ${sourceDir}\n`;
    if (storyId) output += `**Story:** ${storyId}\n`;
    output += `**Generated:** ${new Date().toISOString()}\n\n`;

    output += `### Evidence\n\n`;
    output += `| Item | Status | Value |\n`;
    output += `|------|--------|-------|\n`;
    for (const e of evidence) {
      output += `| ${e.item} | ${e.status} | ${e.value} |\n`;
    }

    // Summary
    const existsCount = evidence.filter(e => e.status.includes("EXISTS")).length;
    const complete = existsCount >= 3; // At minimum: urls.json, html/, builds.json

    output += `\n---\n`;
    output += `**Completion Status:** ${complete ? "✅ SUFFICIENT EVIDENCE" : "❌ INSUFFICIENT EVIDENCE"}\n`;
    output += `**Evidence Score:** ${existsCount}/${evidence.length}\n`;

    return {
      content: [{
        type: "text",
        text: output
      }]
    };
  }
);

// ============== SELF-DIAGNOSIS ==============

// Diagnose Failure
server.tool(
  "diagnose_failure",
  "Analyze a failed operation and suggest fixes",
  {
    sourceDir: z.string().describe("Path to source data directory"),
    stage: z.enum(["url_discovery", "html_scrape", "build_extraction", "mod_extraction"])
      .describe("Pipeline stage that failed"),
    errorLog: z.string().optional().describe("Error message or log content")
  },
  async ({ sourceDir, stage, errorLog }) => {
    const baseDir = path.isAbsolute(sourceDir) ? sourceDir : path.join(RALPH_DIR, sourceDir);
    const issues: Array<{ issue: string; severity: string; suggestion: string }> = [];

    // Stage-specific diagnostics
    switch (stage) {
      case "url_discovery": {
        const urlsFile = path.join(baseDir, "urls.json");
        if (!fs.existsSync(urlsFile)) {
          issues.push({
            issue: "urls.json not created",
            severity: "HIGH",
            suggestion: "Check if target URL is accessible. Verify pagination logic. Try running with debug mode."
          });
        } else {
          try {
            const data = JSON.parse(fs.readFileSync(urlsFile, "utf-8"));
            if (!data.urls || data.urls.length === 0) {
              issues.push({
                issue: "No URLs found",
                severity: "HIGH",
                suggestion: "Check CSS selectors. Verify page loads JavaScript content. Try browser automation."
              });
            }
          } catch {
            issues.push({
              issue: "Invalid JSON in urls.json",
              severity: "HIGH",
              suggestion: "Check for encoding issues. Ensure proper JSON formatting in script."
            });
          }
        }
        break;
      }

      case "html_scrape": {
        const htmlDir = path.join(baseDir, "html");
        const urlsFile = path.join(baseDir, "urls.json");

        if (!fs.existsSync(htmlDir)) {
          issues.push({
            issue: "html/ directory not created",
            severity: "HIGH",
            suggestion: "Ensure directory creation runs before scraping. Check write permissions."
          });
        } else {
          const htmlFiles = fs.readdirSync(htmlDir).filter(f => f.endsWith(".html"));
          if (htmlFiles.length === 0) {
            issues.push({
              issue: "No HTML files scraped",
              severity: "HIGH",
              suggestion: "Check for rate limiting (429 errors). Verify URLs are accessible. Add delays between requests."
            });
          }

          // Check for empty files
          const emptyFiles = htmlFiles.filter(f =>
            fs.statSync(path.join(htmlDir, f)).size < 100
          );
          if (emptyFiles.length > htmlFiles.length * 0.1) {
            issues.push({
              issue: `${emptyFiles.length} empty/small HTML files`,
              severity: "MEDIUM",
              suggestion: "Site may be blocking requests. Try rotating user agents. Add Cloudflare bypass."
            });
          }

          // Check completion rate
          if (fs.existsSync(urlsFile)) {
            try {
              const urls = JSON.parse(fs.readFileSync(urlsFile, "utf-8")).urls || [];
              const completionRate = urls.length > 0 ? htmlFiles.length / urls.length : 0;
              if (completionRate < 0.8) {
                issues.push({
                  issue: `Low completion rate: ${(completionRate * 100).toFixed(1)}%`,
                  severity: "MEDIUM",
                  suggestion: "Check for failed requests in logs. Implement retry logic. Resume from checkpoint."
                });
              }
            } catch { /* ignore */ }
          }
        }
        break;
      }

      case "build_extraction": {
        const buildsFile = path.join(baseDir, "builds.json");
        const htmlDir = path.join(baseDir, "html");

        if (!fs.existsSync(buildsFile)) {
          issues.push({
            issue: "builds.json not created",
            severity: "HIGH",
            suggestion: "Check extraction script for errors. Verify HTML content structure."
          });
        } else {
          try {
            const data = JSON.parse(fs.readFileSync(buildsFile, "utf-8"));
            const builds = Array.isArray(data) ? data : data.builds || [];

            if (builds.length === 0) {
              issues.push({
                issue: "No builds extracted",
                severity: "HIGH",
                suggestion: "Review HTML structure. Check CSS selectors. Verify extraction schema matches content."
              });
            }

            // Check field completeness
            const incompleteBuilds = builds.filter((b: Record<string, unknown>) =>
              !b.year || !b.make || !b.model
            );
            if (incompleteBuilds.length > builds.length * 0.2) {
              issues.push({
                issue: `${incompleteBuilds.length} builds missing year/make/model`,
                severity: "MEDIUM",
                suggestion: "Improve field extraction logic. Add fallback patterns. Check for alternative data locations."
              });
            }
          } catch {
            issues.push({
              issue: "Invalid JSON in builds.json",
              severity: "HIGH",
              suggestion: "Check extraction script output. Verify JSON encoding."
            });
          }
        }
        break;
      }

      case "mod_extraction": {
        const buildsFile = path.join(baseDir, "builds.json");

        if (fs.existsSync(buildsFile)) {
          try {
            const data = JSON.parse(fs.readFileSync(buildsFile, "utf-8"));
            const builds = Array.isArray(data) ? data : data.builds || [];
            const withMods = builds.filter((b: Record<string, unknown>) =>
              b.modifications && (b.modifications as unknown[]).length > 0
            );

            if (withMods.length === 0) {
              issues.push({
                issue: "No modifications extracted",
                severity: "MEDIUM",
                suggestion: "Check if source has modification data. Review extraction patterns for mod lists."
              });
            }
          } catch { /* ignore */ }
        }
        break;
      }
    }

    // Analyze error log if provided
    if (errorLog) {
      if (errorLog.includes("403") || errorLog.includes("Forbidden")) {
        issues.push({
          issue: "403 Forbidden errors",
          severity: "HIGH",
          suggestion: "Site is blocking requests. Try: 1) Rotate user agents, 2) Add delays, 3) Use stealth scraper, 4) Check robots.txt"
        });
      }
      if (errorLog.includes("429") || errorLog.includes("rate limit")) {
        issues.push({
          issue: "Rate limiting detected",
          severity: "HIGH",
          suggestion: "Add longer delays between requests (2-5 seconds). Implement exponential backoff."
        });
      }
      if (errorLog.includes("timeout") || errorLog.includes("ETIMEDOUT")) {
        issues.push({
          issue: "Request timeouts",
          severity: "MEDIUM",
          suggestion: "Increase timeout values. Check network connectivity. Site may be slow or overloaded."
        });
      }
      if (errorLog.includes("Cloudflare") || errorLog.includes("challenge")) {
        issues.push({
          issue: "Cloudflare protection detected",
          severity: "HIGH",
          suggestion: "Use stealth_scraper.py with browser automation. Consider cloudscraper library."
        });
      }
    }

    // Format output
    let output = `## Diagnosis Report: ${stage}\n\n`;
    output += `**Source:** ${sourceDir}\n`;
    output += `**Analyzed:** ${new Date().toISOString()}\n\n`;

    if (issues.length === 0) {
      output += `✅ No obvious issues detected. Check logs for more details.\n`;
    } else {
      output += `### Issues Found (${issues.length})\n\n`;

      for (const issue of issues) {
        const icon = issue.severity === "HIGH" ? "🔴" : issue.severity === "MEDIUM" ? "🟡" : "🟢";
        output += `#### ${icon} ${issue.issue}\n`;
        output += `**Severity:** ${issue.severity}\n`;
        output += `**Suggestion:** ${issue.suggestion}\n\n`;
      }
    }

    // Record diagnosis
    const diagEntity: Entity = {
      id: generateId("pattern"),
      type: "pattern",
      name: `Diagnosis: ${sourceDir} - ${stage}`,
      observations: issues.map(i => `[${i.severity}] ${i.issue}`),
      properties: {
        sourceDir,
        stage,
        issues,
        diagnosedAt: new Date().toISOString()
      },
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };
    graph.entities.set(diagEntity.id, diagEntity);
    saveGraph();

    return {
      content: [{
        type: "text",
        text: output
      }]
    };
  }
);

// Record Success Pattern
server.tool(
  "record_success_pattern",
  "Record a successful approach for future reference",
  {
    sourceId: z.string().describe("Source identifier"),
    stage: z.string().describe("Pipeline stage"),
    pattern: z.string().describe("Description of the successful pattern"),
    details: z.record(z.unknown()).optional().describe("Additional details about the pattern")
  },
  async ({ sourceId, stage, pattern, details }) => {
    const entity: Entity = {
      id: generateId("pattern"),
      type: "pattern",
      name: `Success: ${sourceId} - ${stage}`,
      observations: [
        `Pattern: ${pattern}`,
        `Stage: ${stage}`,
        `Recorded: ${new Date().toISOString()}`
      ],
      properties: {
        sourceId,
        stage,
        pattern,
        details: details || {},
        recordedAt: new Date().toISOString()
      },
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };

    graph.entities.set(entity.id, entity);
    saveGraph();

    return {
      content: [{
        type: "text",
        text: `✅ Recorded success pattern for ${sourceId} (${stage}):\n\n"${pattern}"\n\nThis pattern will be available for future reference when working on similar sources.`
      }]
    };
  }
);

// Get Success Patterns
server.tool(
  "get_success_patterns",
  "Retrieve recorded success patterns for reference",
  {
    stage: z.string().optional().describe("Filter by pipeline stage"),
    limit: z.number().optional().describe("Maximum patterns to return")
  },
  async ({ stage, limit }) => {
    let patterns = Array.from(graph.entities.values())
      .filter(e => e.type === "pattern" && e.name.startsWith("Success:"));

    if (stage) {
      patterns = patterns.filter(p => p.properties.stage === stage);
    }

    patterns = patterns
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      .slice(0, limit || 20);

    let output = `## Success Patterns${stage ? ` (${stage})` : ""}\n\n`;

    if (patterns.length === 0) {
      output += "No success patterns recorded yet.\n";
    } else {
      for (const p of patterns) {
        output += `### ${p.properties.sourceId} - ${p.properties.stage}\n`;
        output += `**Pattern:** ${p.properties.pattern}\n`;
        output += `**Recorded:** ${p.properties.recordedAt}\n`;
        if (p.properties.details && Object.keys(p.properties.details as object).length > 0) {
          output += `**Details:** ${JSON.stringify(p.properties.details)}\n`;
        }
        output += "\n";
      }
    }

    return {
      content: [{
        type: "text",
        text: output
      }]
    };
  }
);

// ============== RESOURCES ==============

// Expose knowledge graph as a resource
server.resource(
  "knowledge-graph",
  "knowledge-graph://graph",
  async () => {
    return {
      contents: [{
        uri: "knowledge-graph://graph",
        mimeType: "application/json",
        text: JSON.stringify({
          entities: Array.from(graph.entities.values()),
          relations: graph.relations,
          metadata: graph.metadata
        }, null, 2)
      }]
    };
  }
);

// Expose pipeline status as a resource
server.resource(
  "pipeline-status",
  "pipeline://status",
  async () => {
    const sources = Array.from(graph.entities.values())
      .filter(e => e.type === "source")
      .map(s => ({
        name: s.name,
        status: s.properties.status,
        pipeline: s.properties.pipeline
      }));

    return {
      contents: [{
        uri: "pipeline://status",
        mimeType: "application/json",
        text: JSON.stringify(sources, null, 2)
      }]
    };
  }
);

// ============== PROMPTS ==============

// Analysis prompt
server.prompt(
  "analyze-pipeline",
  "Analyze the current state of the Ralph scraping pipeline",
  async () => {
    const sources = Array.from(graph.entities.values())
      .filter(e => e.type === "source");

    const status = sources.map(s =>
      `${s.name}: ${s.properties.status} (URLs: ${(s.properties.pipeline as Record<string, number>)?.urlsFound || 0})`
    ).join("\n");

    return {
      messages: [{
        role: "user",
        content: {
          type: "text",
          text: `Please analyze the current state of the Ralph scraping pipeline and provide recommendations.\n\nCurrent Sources:\n${status}\n\nConsider:\n1. Which sources are blocked and why?\n2. What patterns have been successful?\n3. What should be prioritized next?`
        }
      }]
    };
  }
);

// Build extraction prompt
server.prompt(
  "extract-patterns",
  "Extract patterns from successful scrapes",
  async () => {
    const completedSources = Array.from(graph.entities.values())
      .filter(e => e.type === "source" && e.properties.status === "completed");

    const observations = completedSources
      .flatMap(s => s.observations)
      .join("\n- ");

    return {
      messages: [{
        role: "user",
        content: {
          type: "text",
          text: `Based on successful scraping operations, extract reusable patterns.\n\nCompleted Sources:\n${completedSources.map(s => s.name).join(", ")}\n\nObservations:\n- ${observations}\n\nIdentify:\n1. Common URL patterns\n2. Successful pagination strategies\n3. Anti-bot bypass techniques that worked\n4. Data extraction patterns`
        }
      }]
    };
  }
);

// ============== MAIN ==============

async function main(): Promise<void> {
  // Load existing graph
  loadGraph();

  // Start file watchers for auto-sync
  startFileWatchers();

  // Connect to stdio transport
  const transport = new StdioServerTransport();
  await server.connect(transport);

  // Log to stderr (not stdout which is used for JSON-RPC)
  console.error("Fylo-Core-MCP server running on stdio");
  console.error(`Graph loaded: ${graph.entities.size} entities, ${graph.relations.length} relations`);

  // Handle graceful shutdown
  process.on("SIGINT", () => {
    console.error("Received SIGINT, shutting down...");
    stopFileWatchers();
    saveGraph();
    process.exit(0);
  });

  process.on("SIGTERM", () => {
    console.error("Received SIGTERM, shutting down...");
    stopFileWatchers();
    saveGraph();
    process.exit(0);
  });
}

main().catch((error) => {
  console.error("Fatal error:", error);
  stopFileWatchers();
  process.exit(1);
});
