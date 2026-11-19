/**
 * Editing the material number of a Spoolman spool writes the filament's
 * article number: one filament PATCH after the spool save, with the filament
 * id from the save response, and none when the number is unchanged.
 */

import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { render } from '../utils';
import { SpoolFormModal } from '../../components/SpoolFormModal';
import type { InventorySpool } from '../../api/client';

vi.mock('../../api/client', () => ({
  api: {
    getSettings: vi.fn().mockResolvedValue({}),
    getAuthStatus: vi.fn().mockResolvedValue({ auth_enabled: false }),
    getCloudStatus: vi.fn().mockResolvedValue({ is_authenticated: false }),
    getFilamentPresets: vi.fn().mockResolvedValue([]),
    getSpoolCatalog: vi.fn().mockResolvedValue([]),
    getLocations: vi.fn().mockResolvedValue([]),
    getColorCatalog: vi.fn().mockResolvedValue([]),
    getLocalPresets: vi.fn().mockResolvedValue({ filament: [] }),
    getBuiltinFilaments: vi.fn().mockResolvedValue([]),
    getPrinters: vi.fn().mockResolvedValue([]),
    getSpoolUsageHistory: vi.fn().mockResolvedValue([]),
    getSpoolmanSpoolUsageHistory: vi.fn().mockResolvedValue([]),
    createSpool: vi.fn().mockResolvedValue({ id: 99 }),
    createSpoolmanInventorySpool: vi.fn().mockResolvedValue({ id: 88 }),
    updateSpool: vi.fn().mockResolvedValue({ id: 1 }),
    saveSpoolKProfiles: vi.fn().mockResolvedValue([]),
    getSpoolFilamentPresets: vi.fn().mockResolvedValue([]),
    saveSpoolFilamentPresets: vi.fn().mockResolvedValue([]),
    getSpoolmanFilamentPresets: vi.fn().mockResolvedValue([]),
    saveSpoolmanFilamentPresets: vi.fn().mockResolvedValue([]),
    saveSpoolmanKProfiles: vi.fn().mockResolvedValue([]),
    updateSpoolmanInventorySpool: vi.fn().mockResolvedValue({ id: 42, spoolman_filament_id: 7 }),
    updateSpoolmanInventoryFilament: vi.fn().mockResolvedValue({ id: 7 }),
    bulkCreateSpoolmanInventorySpools: vi.fn().mockResolvedValue({
      created: [{ id: 1, material: 'PLA' }],
      requested_count: 1,
      failed_count: 0,
    }),
    getSpoolmanInventoryFilaments: vi.fn().mockResolvedValue([]),
    getAssignments: vi.fn().mockResolvedValue([]),
    getSpoolmanSlotAssignments: vi.fn().mockResolvedValue([]),
    unassignSpool: vi.fn().mockResolvedValue({}),
    unassignSpoolmanSlot: vi.fn().mockResolvedValue({}),
    // Suppliers (#2988) — the SupplierSection inside the form loads these.
    getSuppliers: vi.fn().mockResolvedValue([]),
    createSupplier: vi.fn().mockResolvedValue({ id: 1, name: 'S' }),
    setSpoolSuppliers: vi.fn().mockResolvedValue([]),
    setSpoolmanSpoolSuppliers: vi.fn().mockResolvedValue([]),
  },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
}));


const mockShowToast = vi.fn();
vi.mock('../../contexts/ToastContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../contexts/ToastContext')>();
  return {
    ...actual,
    useToast: () => ({ showToast: mockShowToast }),
  };
});

import { api } from '../../api/client';

const spoolmanSpool = {
  id: 42,
  material: 'PLA',
  subtype: 'Basic',
  brand: 'BrandX',
  color_name: 'Black',
  rgba: '000000FF',
  extra_colors: null,
  effect_type: null,
  label_weight: 1000,
  core_weight: 250,
  core_weight_catalog_id: null,
  weight_used: 200,
  slicer_filament: 'GFL99',
  slicer_filament_name: 'Generic PLA',
  note: null,
  material_number: '15,9319236810491',
  spoolman_filament_id: 7,
  k_profiles: [],
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
} as unknown as InventorySpool;

function renderEdit() {
  render(
    <SpoolFormModal
      isOpen={true}
      onClose={vi.fn()}
      spool={spoolmanSpool}
      mode="edit"
      currencySymbol="$"
      spoolmanMode={true}
    />,
  );
}

async function openColorAndCost() {
  await waitFor(() => expect(screen.getByText('Edit Spool')).toBeInTheDocument());
  fireEvent.click(screen.getByText('Color & Cost'));
}

describe('SpoolFormModal material number in Spoolman mode', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('patches the filament once, with the id from the save response, when the number changed', async () => {
    // The response names filament 9, not the 7 the spool came with: the id of
    // the response wins (a changed identity can move the spool to another filament).
    vi.mocked(api.updateSpoolmanInventorySpool).mockResolvedValueOnce({ id: 42, spoolman_filament_id: 9 } as InventorySpool);
    renderEdit();
    await openColorAndCost();

    fireEvent.change(screen.getByLabelText('Material No.'), { target: { value: '15,77' } });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => expect(api.updateSpoolmanInventoryFilament).toHaveBeenCalledTimes(1));
    expect(api.updateSpoolmanInventoryFilament).toHaveBeenCalledWith(9, { material_number: '15,77' });
  });

  it('clears the filament number with null when the field is emptied', async () => {
    renderEdit();
    await openColorAndCost();

    fireEvent.change(screen.getByLabelText('Material No.'), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => expect(api.updateSpoolmanInventoryFilament).toHaveBeenCalledWith(7, { material_number: null }));
  });

  it('does not patch the filament when the number is unchanged', async () => {
    renderEdit();
    await openColorAndCost();

    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => expect(api.updateSpoolmanInventorySpool).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(mockShowToast).toHaveBeenCalledWith('Spool updated', 'success'));
    expect(api.updateSpoolmanInventoryFilament).not.toHaveBeenCalled();
  });

  it('shows the error toast when the save response has no filament id', async () => {
    vi.mocked(api.updateSpoolmanInventorySpool).mockResolvedValueOnce({ id: 42, spoolman_filament_id: null } as InventorySpool);
    renderEdit();
    await openColorAndCost();

    fireEvent.change(screen.getByLabelText('Material No.'), { target: { value: '99' } });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => expect(mockShowToast).toHaveBeenCalledWith(expect.any(String), 'error'));
    expect(api.updateSpoolmanInventoryFilament).not.toHaveBeenCalled();
  });
});
