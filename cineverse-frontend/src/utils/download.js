/**
 * Triggers a browser "Save As" download for an in-memory blob (e.g. a
 * PDF fetched via axios with `responseType: 'blob'`). No server-side
 * file is involved -- this only exists to turn an already-fetched
 * blob into a download, via a temporary, invisible anchor element.
 */
export function downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

/**
 * Opens an in-memory blob (e.g. a PDF) in a new browser tab, for a
 * "Print" action (Phase 6C). No dedicated print backend logic exists
 * or is needed -- browsers already render PDFs with a native viewer
 * that has its own print button/shortcut, so this is the simplest,
 * most reliable way to support "print this invoice" without building
 * a custom print layout.
 */
export function printBlob(blob) {
  const url = window.URL.createObjectURL(blob);
  const opened = window.open(url, '_blank');
  if (!opened) {
    // Popup blocked -- fall back to a plain download so the person
    // can still open and print it themselves, rather than silently
    // doing nothing.
    const link = document.createElement('a');
    link.href = url;
    link.target = '_blank';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
  // Revoked after a delay rather than immediately -- the new tab needs
  // time to actually load the blob URL before it's invalidated.
  setTimeout(() => window.URL.revokeObjectURL(url), 30000);
}
