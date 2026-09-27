export default function safariCacheBustPlugin() {
  return {
    name: "vite-plugin-safari-cachebust",
    transformIndexHtml(html) {
      return html.replace(
        /(<link[^>]*rel="stylesheet"[^>]*>)/g,
        (match) => {
          const url = new URL(match.match(/href="([^"]+)"/)?.[1] || "", "file:");
          url.searchParams.set("v", Date.now().toString());
          return match.replace(/href="([^"]+)"/, `href="${url.href}"`);
        }
      );
    },
  };
}