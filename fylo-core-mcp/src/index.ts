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

  // Connect to stdio transport
  const transport = new StdioServerTransport();
  await server.connect(transport);

  // Log to stderr (not stdout which is used for JSON-RPC)
  console.error("Fylo-Core-MCP server running on stdio");
  console.error(`Graph loaded: ${graph.entities.size} entities, ${graph.relations.length} relations`);
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
