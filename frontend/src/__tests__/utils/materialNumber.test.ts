import { describe, it, expect } from 'vitest';
import { splitMaterialNumbers } from '../../utils/materialNumber';

// Same vectors as backend/tests/unit/services/test_material_number_match.py:
// a stored text is a list of numbers separated by a comma or a semicolon.
describe('splitMaterialNumbers', () => {
  it('keeps a single number whole', () => {
    expect(splitMaterialNumbers('9319236810491')).toEqual(['9319236810491']);
  });

  it('splits at commas and semicolons and trims each entry', () => {
    expect(splitMaterialNumbers('15,9319236810491')).toEqual(['15', '9319236810491']);
    expect(splitMaterialNumbers('15;9319236810491')).toEqual(['15', '9319236810491']);
    expect(splitMaterialNumbers('15,9319236810491;77')).toEqual(['15', '9319236810491', '77']);
    expect(splitMaterialNumbers('  15 ,  9319236810491  ')).toEqual(['15', '9319236810491']);
  });

  it('keeps the case and does not split at a space', () => {
    expect(splitMaterialNumbers('AB-1')).toEqual(['AB-1']);
    expect(splitMaterialNumbers('PM 70820')).toEqual(['PM 70820']);
  });

  it('gives no entry for an empty text or empty parts', () => {
    expect(splitMaterialNumbers(null)).toEqual([]);
    expect(splitMaterialNumbers(undefined)).toEqual([]);
    expect(splitMaterialNumbers('')).toEqual([]);
    expect(splitMaterialNumbers(',,')).toEqual([]);
    expect(splitMaterialNumbers(' ; ')).toEqual([]);
  });
});
