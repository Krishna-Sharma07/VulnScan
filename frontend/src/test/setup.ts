import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Not using Vitest's `globals: true` mode, so @testing-library/react's own
// auto-cleanup (which relies on a global `afterEach`) never registers -
// without this, every test after the first in a file sees the previous
// test's still-mounted DOM and "multiple elements found" errors follow.
afterEach(() => {
  cleanup();
});
