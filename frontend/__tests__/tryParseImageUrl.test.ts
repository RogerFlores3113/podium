import { describe, it, expect } from "vitest";
import { tryParseImageUrl } from "@/app/utils/image";

describe("tryParseImageUrl", () => {
  it("returns null for plain text", () => {
    expect(tryParseImageUrl("Found 5 results for your query")).toBeNull();
  });

  it("returns null for non-image URLs", () => {
    expect(tryParseImageUrl("https://example.com/page")).toBeNull();
  });

  it("returns the URL for .png", () => {
    const url = "https://example.com/photo.png";
    expect(tryParseImageUrl(url)).toBe(url);
  });

  it("returns the URL for .jpg", () => {
    const url = "https://example.com/photo.jpg";
    expect(tryParseImageUrl(url)).toBe(url);
  });

  it("returns the URL for .webp with query params", () => {
    const url = "https://cdn.example.com/img.webp?v=2";
    expect(tryParseImageUrl(url)).toBe(url);
  });

  it("returns the URL for DALL-E CDN URLs", () => {
    const url =
      "https://oaidalleapiprodscus.blob.core.windows.net/private/abc123/img-xyz.png";
    expect(tryParseImageUrl(url)).toBe(url);
  });

  it("returns null for http:// non-image URLs", () => {
    expect(tryParseImageUrl("http://example.com/data")).toBeNull();
  });

  it("trims surrounding whitespace before checking", () => {
    const url = "  https://example.com/img.jpg  ";
    expect(tryParseImageUrl(url)).toBe(url.trim());
  });
});
