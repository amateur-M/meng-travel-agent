/**
 * Minimal Node global typing for the E2E project.
 *
 * Playwright's config runs in Node, but this project deliberately keeps its
 * dependency set lean (and the frontend verification tooling is zero-dependency
 * by choice), so it does not pull in `@types/node` for the sake of one file.
 * Only the API actually used is declared.
 *
 * If the E2E suite starts using more Node APIs (fs, path, __dirname, …),
 * replace this file with a devDependency on `@types/node` instead of growing
 * hand-written declarations.
 */
declare const process: {
  env: Record<string, string | undefined>;
};
