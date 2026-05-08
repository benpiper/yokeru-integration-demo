import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { StatCard } from './StatCard';

describe('StatCard', () => {
  it('renders the label and value', () => {
    render(<StatCard label="Total Calls" value={10} />);
    expect(screen.getByText('Total Calls')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
  });

  it('renders the sub text if provided', () => {
    render(<StatCard label="Delivered" value={5} sub="Acknowledged" />);
    expect(screen.getByText('Acknowledged')).toBeInTheDocument();
  });
});
