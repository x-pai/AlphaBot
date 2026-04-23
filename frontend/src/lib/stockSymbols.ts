const PURE_CODE_PATTERN = /^\d{6}$/;

export const MAX_BATCH_SYMBOLS = 10;

export type SymbolValidationResult = {
  rawTokens: string[];
  validCodes: string[];
  normalizedPreview: string[];
  invalidSymbols: string[];
  duplicateSymbols: string[];
};

export function inferExchangeFromCode(code: string): 'SH' | 'SZ' | 'BJ' {
  if (/^[569]/.test(code)) {
    return 'SH';
  }
  if (/^[48]/.test(code)) {
    return 'BJ';
  }
  return 'SZ';
}

export function normalizeStockSymbol(symbol: string): string | null {
  const raw = symbol.trim().toUpperCase();
  if (!raw) {
    return null;
  }

  if (PURE_CODE_PATTERN.test(raw)) {
    return `${raw}.${inferExchangeFromCode(raw)}`;
  }

  return null;
}

export function validateBatchSymbols(input: string): SymbolValidationResult {
  const rawTokens = input
    .split(/[,，\s]+/)
    .map((token) => token.trim())
    .filter(Boolean);

  const validCodes: string[] = [];
  const normalizedPreview: string[] = [];
  const invalidSymbols: string[] = [];
  const duplicateSymbols: string[] = [];
  const seen = new Set<string>();

  for (const token of rawTokens) {
    const normalized = normalizeStockSymbol(token);
    if (!normalized) {
      invalidSymbols.push(token);
      continue;
    }

    const rawCode = token.trim();
    if (seen.has(rawCode)) {
      duplicateSymbols.push(token);
      continue;
    }

    seen.add(rawCode);
    validCodes.push(rawCode);
    normalizedPreview.push(normalized);
  }

  return {
    rawTokens,
    validCodes,
    normalizedPreview,
    invalidSymbols,
    duplicateSymbols,
  };
}
