import * as fs from "fs";
import * as path from "path";
import type {
  AgentVersion,
  VersionDiff,
  DocContent,
  VersionIndex,
  ChapterImage,
} from "../src/types/agent-data";
import { VERSION_META, VERSION_ORDER, LEARNING_PATH } from "../src/lib/constants";

const WEB_DIR = path.resolve(__dirname, "..");
const REPO_ROOT = path.resolve(WEB_DIR, "..");
// 新版课程只从 agents/ 下的章节目录读取，不再回退到旧版 12 章。
const COURSE_DIR = path.join(REPO_ROOT, "agents");
const OUT_DIR = path.join(WEB_DIR, "src", "data", "generated");
const PUBLIC_DIR = path.join(WEB_DIR, "public");
const COURSE_ASSETS_DIR = path.join(PUBLIC_DIR, "course-assets");

type Locale = "en" | "zh" | "ja";

interface ChapterSource {
  id: string;
  dirName: string;
  dirPath: string;
  codePath: string;
}

function dirToVersionId(dirName: string): string | null {
  const match = dirName.match(/^(s\d{2})_/);
  return match ? match[1] : null;
}

function listCourseChapters(): ChapterSource[] {
  return fs
    .readdirSync(COURSE_DIR, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .filter((name) => /^s\d{2}_/.test(name))
    .sort()
    .map((dirName) => {
      const id = dirToVersionId(dirName);
      if (!id) return null;
      const dirPath = path.join(COURSE_DIR, dirName);
      const codePath = path.join(dirPath, "code.py");
      if (!fs.existsSync(codePath)) return null;
      return { id, dirName, dirPath, codePath };
    })
    .filter((chapter): chapter is ChapterSource => chapter !== null);
}

function extractClasses(
  lines: string[]
): { name: string; startLine: number; endLine: number }[] {
  const classes: { name: string; startLine: number; endLine: number }[] = [];
  const classPattern = /^class\s+(\w+)/;

  for (let i = 0; i < lines.length; i++) {
    const match = lines[i].match(classPattern);
    if (!match) continue;

    const name = match[1];
    const startLine = i + 1;
    let endLine = lines.length;
    for (let j = i + 1; j < lines.length; j++) {
      if (
        lines[j].match(/^class\s/) ||
        lines[j].match(/^def\s/) ||
        (lines[j].match(/^\S/) &&
          lines[j].trim() !== "" &&
          !lines[j].startsWith("#") &&
          !lines[j].startsWith("@"))
      ) {
        endLine = j;
        break;
      }
    }
    classes.push({ name, startLine, endLine });
  }

  return classes;
}

function extractFunctions(
  lines: string[]
): { name: string; signature: string; startLine: number }[] {
  const functions: { name: string; signature: string; startLine: number }[] = [];
  const funcPattern = /^def\s+(\w+)\((.*?)\)/;

  for (let i = 0; i < lines.length; i++) {
    const match = lines[i].match(funcPattern);
    if (!match) continue;
    functions.push({
      name: match[1],
      signature: `def ${match[1]}(${match[2]})`,
      startLine: i + 1,
    });
  }

  return functions;
}

function extractTools(source: string): string[] {
  const toolPattern = /"name"\s*:\s*"([\w-]+)"/g;
  const tools = new Set<string>();
  let match;
  while ((match = toolPattern.exec(source)) !== null) {
    tools.add(match[1]);
  }
  return Array.from(tools);
}

function countLoc(lines: string[]): number {
  return lines.filter((line) => {
    const trimmed = line.trim();
    return trimmed !== "" && !trimmed.startsWith("#");
  }).length;
}

function titleFromMarkdown(content: string, fallback: string): string {
  const titleMatch = content.match(/^#\s+(.+)$/m);
  return titleMatch ? titleMatch[1] : fallback;
}

function cleanCourseAssets() {
  fs.rmSync(COURSE_ASSETS_DIR, { recursive: true, force: true });
  fs.mkdirSync(COURSE_ASSETS_DIR, { recursive: true });
}

function copyChapterAssets(chapter: ChapterSource): ChapterImage[] {
  const imagesDir = path.join(chapter.dirPath, "images");
  if (!fs.existsSync(imagesDir)) return [];

  const outDir = path.join(COURSE_ASSETS_DIR, chapter.dirName);
  fs.mkdirSync(outDir, { recursive: true });
  fs.cpSync(imagesDir, outDir, { recursive: true });

  return fs
    .readdirSync(imagesDir)
    .filter((filename) => filename.endsWith(".svg"))
    .filter((filename) => !filename.includes(".en.") && !filename.includes(".ja."))
    .sort()
    .map((filename) => ({
      src: `/course-assets/${chapter.dirName}/${filename}`,
      alt: filename.replace(/\.svg$/, "").replace(/-/g, " "),
    }));
}

function localeReadmeName(locale: Locale): string {
  if (locale === "zh") return "README.md";
  return `README.${locale}.md`;
}

function rewriteChapterMarkdown(
  content: string,
  chapter: ChapterSource,
  locale: Locale
): string {
  let next = content;

  next = next.replace(
    /^\[中文\]\(README\.md\)\s*.\s*\[English\]\(README\.en\.md\)\s*.\s*\[日本語\]\(README\.ja\.md\)\n\n?/m,
    ""
  );

  next = next.replace(
    /(!\[[^\]]*\]\()images\/([^)]+)(\))/g,
    `$1/course-assets/${chapter.dirName}/$2$3`
  );

  next = next.replace(
    /\]\(\.\.\/(s\d{2}_[^)\/]+)\/?\)/g,
    (_match, dirName) => {
      const id = dirToVersionId(dirName);
      return id ? `](/${locale}/${id})` : `](../${dirName}/)`;
    }
  );

  next = next.replace(
    /\]\(\.\/(s\d{2}_[^)\/]+)\/?\)/g,
    (_match, dirName) => {
      const id = dirToVersionId(dirName);
      return id ? `](/${locale}/${id})` : `](./${dirName}/)`;
    }
  );

  return next;
}

function buildCourseVersions(chapters: ChapterSource[]): AgentVersion[] {
  return chapters.map((chapter) => {
    const source = fs.readFileSync(chapter.codePath, "utf-8");
    const lines = source.split("\n");
    const meta = VERSION_META[chapter.id];

    return {
      id: chapter.id,
      filename: `agents/${chapter.dirName}/code.py`,
      title: meta?.title ?? chapter.id,
      subtitle: meta?.subtitle ?? "",
      loc: countLoc(lines),
      tools: extractTools(source),
      newTools: [] as string[],
      coreAddition: meta?.coreAddition ?? "",
      keyInsight: meta?.keyInsight ?? "",
      classes: extractClasses(lines),
      functions: extractFunctions(lines),
      layer: meta?.layer ?? "tools",
      source,
      images: copyChapterAssets(chapter),
    };
  });
}

function buildCourseDocs(chapters: ChapterSource[]): DocContent[] {
  const docs: DocContent[] = [];
  const locales: Locale[] = ["en", "zh", "ja"];

  for (const chapter of chapters) {
    for (const locale of locales) {
      const filename = localeReadmeName(locale);
      const filePath = path.join(chapter.dirPath, filename);
      if (!fs.existsSync(filePath)) continue;

      const raw = fs.readFileSync(filePath, "utf-8");
      const content = rewriteChapterMarkdown(raw, chapter, locale);
      docs.push({
        version: chapter.id,
        locale,
        title: titleFromMarkdown(content, filename),
        content,
      });
    }
  }

  return docs;
}

function computeNewTools(versions: AgentVersion[]) {
  for (let i = 0; i < versions.length; i++) {
    const prev = i > 0 ? new Set(versions[i - 1].tools) : new Set<string>();
    versions[i].newTools = versions[i].tools.filter((tool) => !prev.has(tool));
  }
}

function buildDiffs(versions: AgentVersion[]): VersionDiff[] {
  const diffs: VersionDiff[] = [];
  const versionMap = new Map(versions.map((version) => [version.id, version]));

  for (let i = 1; i < LEARNING_PATH.length; i++) {
    const fromId = LEARNING_PATH[i - 1];
    const toId = LEARNING_PATH[i];
    const fromVer = versionMap.get(fromId);
    const toVer = versionMap.get(toId);
    if (!fromVer || !toVer) continue;

    const fromClassNames = new Set(fromVer.classes.map((cls) => cls.name));
    const fromFuncNames = new Set(fromVer.functions.map((fn) => fn.name));
    const fromToolNames = new Set(fromVer.tools);

    diffs.push({
      from: fromId,
      to: toId,
      newClasses: toVer.classes
        .map((cls) => cls.name)
        .filter((name) => !fromClassNames.has(name)),
      newFunctions: toVer.functions
        .map((fn) => fn.name)
        .filter((name) => !fromFuncNames.has(name)),
      newTools: toVer.tools.filter((tool) => !fromToolNames.has(tool)),
      locDelta: toVer.loc - fromVer.loc,
    });
  }

  return diffs;
}

function sortVersions(versions: AgentVersion[]) {
  const orderMap = new Map(VERSION_ORDER.map((id, index) => [id, index]));
  versions.sort(
    (a, b) => (orderMap.get(a.id as any) ?? 99) - (orderMap.get(b.id as any) ?? 99)
  );
}

function main() {
  console.log("Extracting course content...");
  console.log(`  Repo root: ${REPO_ROOT}`);

  // 先确认课程完整，再清理生成图片，避免错误路径把现有数据覆盖成空课程。
  const chapters = listCourseChapters();
  const expectedIds = Array.from({ length: 20 }, (_, index) =>
    `s${String(index + 1).padStart(2, "0")}`
  );
  if (chapters.length !== 20 || chapters.some((chapter, index) => chapter.id !== expectedIds[index])) {
    throw new Error("Expected exactly s01-s20 chapter folders with code.py under agents/");
  }
  cleanCourseAssets();
  console.log(`  Source: agents/ chapter folders (${chapters.length})`);
  const versions = buildCourseVersions(chapters);
  const docs = buildCourseDocs(chapters);

  sortVersions(versions);
  computeNewTools(versions);
  const diffs = buildDiffs(versions);

  fs.mkdirSync(OUT_DIR, { recursive: true });

  const index: VersionIndex = { versions, diffs };
  fs.writeFileSync(path.join(OUT_DIR, "versions.json"), JSON.stringify(index, null, 2));
  fs.writeFileSync(path.join(OUT_DIR, "docs.json"), JSON.stringify(docs, null, 2));

  console.log("\nExtraction complete:");
  console.log(`  ${versions.length} versions`);
  console.log(`  ${diffs.length} diffs`);
  console.log(`  ${docs.length} docs`);
  for (const version of versions) {
    console.log(
      `    ${version.id}: ${version.loc} LOC, ${version.tools.length} tools, ${version.classes.length} classes, ${version.functions.length} functions`
    );
  }
}

main();
