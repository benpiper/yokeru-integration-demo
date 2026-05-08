import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { CallTable } from './CallTable';
import { CallRow } from '../../types/api';

const mockCalls: CallRow[] = [
  {
    correlation_id: 'a1b2c3d4',
    patient_id: '123',
    status: 'PENDING',
    synced: 0,
    attempts: 0,
    reason: null,
    outcome: null,
    completed_at: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    correlation_id: 'e5f6g7h8',
    patient_id: '456',
    status: 'DELIVERED',
    synced: 1,
    attempts: 1,
    reason: null,
    outcome: 'completed',
    completed_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }
];

describe('CallTable', () => {
  it('renders all calls initially', () => {
    render(<CallTable calls={mockCalls} />);
    expect(screen.getByText('a1b2c3d4…')).toBeInTheDocument();
    expect(screen.getByText('e5f6g7h8…')).toBeInTheDocument();
  });

  it('filters calls by status when a filter button is clicked', () => {
    render(<CallTable calls={mockCalls} />);
    
    // Click PENDING filter
    fireEvent.click(screen.getByTestId('filter-pending'));
    
    expect(screen.getByText('a1b2c3d4…')).toBeInTheDocument();
    expect(screen.queryByText('e5f6g7h8…')).not.toBeInTheDocument();
  });

  it('shows empty state when no calls match the filter', () => {
    render(<CallTable calls={mockCalls} />);
    
    // Click FAILED_PERMANENT filter
    fireEvent.click(screen.getByTestId('filter-failed_permanent'));
    
    expect(screen.getByText('No calls match this filter')).toBeInTheDocument();
  });
});
