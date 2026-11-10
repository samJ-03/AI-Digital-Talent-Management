/** Generate types from actual JSON content; support Windows non-ASCII project paths. */
import { readFile,writeFile,mkdir } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const root=fileURLToPath(new URL('../',import.meta.url));
const require=createRequire(new URL('../frontend/package.json',import.meta.url));
const { default:openapiTS,astToString,COMMENT_HEADER }=require('openapi-typescript');
const schema=JSON.parse(await readFile(join(root,'artifacts/openapi.json'),'utf8'));
const ast=await openapiTS(schema);
await mkdir(join(root,'frontend/src/generated'),{recursive:true});
await writeFile(join(root,'frontend/src/generated/api-types.ts'),COMMENT_HEADER+astToString(ast),'utf8');
console.log('Generated frontend API types from reviewed OpenAPI');
