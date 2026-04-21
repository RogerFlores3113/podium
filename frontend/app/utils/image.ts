const IMAGE_EXTENSIONS = /\.(png|jpg|jpeg|gif|webp|svg)(\?.*)?$/i;
// DALL-E CDN URLs look like: https://oaidalleapiprodscus.blob.core.windows.net/...
const DALLE_CDN = /oaidalleapiprodscus\.blob\.core\.windows\.net/i;

export function tryParseImageUrl(result: string): string | null {
  const trimmed = result.trim();
  if (!trimmed.startsWith("https://") && !trimmed.startsWith("http://")) return null;
  if (IMAGE_EXTENSIONS.test(trimmed) || DALLE_CDN.test(trimmed)) return trimmed;
  return null;
}
