import type { DocumentKind } from '@/api/client';

/** Client-side pre-check for fast feedback. The server remains the authority. */
export const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
export const ACCEPT = '.docx,.pdf,.pptx';

export function precheck(file: File): { ok: true; kind: DocumentKind } | { ok: false; reason: string } {
  const ext = file.name.toLowerCase().split('.').pop() ?? '';
  if (ext === 'docm' || ext === 'pptm') return { ok: false, reason: 'Macro-enabled files are not accepted.' };
  if (ext === 'doc' || ext === 'ppt') return { ok: false, reason: 'Save legacy Office files as .docx or .pptx first.' };
  if (ext !== 'docx' && ext !== 'pdf' && ext !== 'pptx') return { ok: false, reason: 'Only .docx, .pdf and .pptx are supported.' };
  if (file.size === 0) return { ok: false, reason: 'The file is empty.' };
  if (file.size > MAX_UPLOAD_BYTES) return { ok: false, reason: 'The file is larger than 50 MB.' };
  return { ok: true, kind: ext };
}
