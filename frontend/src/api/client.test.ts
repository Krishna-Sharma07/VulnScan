import { describe, expect, it } from "vitest";
import { extractErrorMessage } from "./client";

describe("extractErrorMessage", () => {
  it("passes through a plain string detail (HTTPException shape)", () => {
    const err = { response: { data: { detail: "Email already registered" } } };
    expect(extractErrorMessage(err, "fallback")).toBe("Email already registered");
  });

  it("joins an array detail (Pydantic 422 shape) into one message", () => {
    const err = {
      response: {
        data: {
          detail: [{ msg: "String should have at least 8 characters" }, { msg: "Invalid email" }],
        },
      },
    };
    expect(extractErrorMessage(err, "fallback")).toBe(
      "String should have at least 8 characters, Invalid email"
    );
  });

  it("falls back to the raw item when an array entry has no msg", () => {
    const err = { response: { data: { detail: ["oops"] } } };
    expect(extractErrorMessage(err, "fallback")).toBe("oops");
  });

  it("uses the fallback when there is no detail at all", () => {
    expect(extractErrorMessage({}, "Signup failed")).toBe("Signup failed");
    expect(extractErrorMessage(null, "Signup failed")).toBe("Signup failed");
  });
});
