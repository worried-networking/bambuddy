/**
 * The entries of a stored material number.
 *
 * A product sold under more than one article number keeps them in the one
 * text, separated by a comma or a semicolon. Each entry is trimmed and empty
 * ones are dropped; a space is not a separator ("PM 70820" is one number).
 * The server splits the same way when it searches by material number.
 */
export function splitMaterialNumbers(stored: string | null | undefined): string[] {
  if (!stored) return [];
  return stored
    .replace(/;/g, ',')
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);
}
