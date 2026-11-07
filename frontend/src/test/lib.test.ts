import { describe, expect, it } from 'vitest';

import { describeWarning, formatBytes } from '@/lib/format';
import { precheck } from '@/lib/upload';

const file = (name: string, size = 10) => new File([new Uint8Array(size)], name);

describe('upload precheck', () => {
  it.each([
    ['report.docx', true],
    ['Paper.PDF', true],
    ['deck.pptx', true],
    ['macro.docm', false],
    ['old.doc', false],
    ['notes.txt', false],
  ])('%s → %s', (name, ok) => {
    expect(precheck(file(name)).ok).toBe(ok);
  });

  it('rejects empty and oversized files', () => {
    expect(precheck(file('a.pdf', 0))).toEqual({ ok: false, reason: 'The file is empty.' });
    const big = file('a.pdf');
    Object.defineProperty(big, 'size', { value: 51 * 1024 * 1024 });
    expect(precheck(big).ok).toBe(false);
  });
});

describe('formatting', () => {
  it('formats bytes', () => {
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(2048)).toBe('2.0 KB');
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MB');
  });
  it('explains security warnings in plain language', () => {
    expect(describeWarning('pdf_active_content:javascript')).toMatch(/never executed/);
  });
});
