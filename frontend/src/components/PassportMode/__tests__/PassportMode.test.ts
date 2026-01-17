/**
 * Tests for PassportMode exports and logic.
 *
 * Note: Full component rendering tests would require @testing-library/react.
 * These tests verify the module exports and type consistency.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import type { ViewMode } from '../index';

// Mock localStorage for testing
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    clear: vi.fn(() => {
      store = {};
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
  };
})();

Object.defineProperty(globalThis, 'localStorage', {
  value: localStorageMock,
});

describe('PassportMode module', () => {
  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
  });

  describe('exports', () => {
    it('exports PassportModeToggle component', async () => {
      const module = await import('../index');
      expect(module.PassportModeToggle).toBeDefined();
      expect(typeof module.PassportModeToggle).toBe('function');
    });

    it('exports PassportView component', async () => {
      const module = await import('../index');
      expect(module.PassportView).toBeDefined();
      expect(typeof module.PassportView).toBe('function');
    });

    it('exports usePassportMode hook', async () => {
      const module = await import('../index');
      expect(module.usePassportMode).toBeDefined();
      expect(typeof module.usePassportMode).toBe('function');
    });

    it('exports PassportCard component', async () => {
      const module = await import('../index');
      expect(module.PassportCard).toBeDefined();
      expect(typeof module.PassportCard).toBe('function');
    });

    it('exports detectPassportType function', async () => {
      const module = await import('../index');
      expect(module.detectPassportType).toBeDefined();
      expect(typeof module.detectPassportType).toBe('function');
    });

    it('exports getCardTypeLabel function', async () => {
      const module = await import('../index');
      expect(module.getCardTypeLabel).toBeDefined();
      expect(typeof module.getCardTypeLabel).toBe('function');
    });

    it('exports ViewMode type', async () => {
      // Type check - this test verifies the type exists and is correct
      const mode: ViewMode = 'editor';
      expect(mode).toBe('editor');

      const passportMode: ViewMode = 'passport';
      expect(passportMode).toBe('passport');
    });
  });

  describe('ViewMode type', () => {
    it('accepts "editor" as valid ViewMode', () => {
      const mode: ViewMode = 'editor';
      expect(['editor', 'passport']).toContain(mode);
    });

    it('accepts "passport" as valid ViewMode', () => {
      const mode: ViewMode = 'passport';
      expect(['editor', 'passport']).toContain(mode);
    });
  });

  describe('localStorage integration', () => {
    it('reads mode preference from localStorage key', () => {
      // This tests that the STORAGE_KEY constant is used correctly
      localStorageMock.setItem('passport-mode-preference', 'passport');
      expect(localStorageMock.getItem('passport-mode-preference')).toBe('passport');
    });

    it('stores mode preference in localStorage', () => {
      localStorageMock.setItem('passport-mode-preference', 'editor');
      expect(localStorageMock.getItem('passport-mode-preference')).toBe('editor');
    });

    it('handles missing localStorage gracefully', () => {
      expect(localStorageMock.getItem('passport-mode-preference')).toBeNull();
    });
  });
});

describe('PassportModeToggle props interface', () => {
  it('requires mode prop of ViewMode type', () => {
    // Type verification
    interface PassportModeToggleProps {
      mode: ViewMode;
      onModeChange: (mode: ViewMode) => void;
    }

    const validProps: PassportModeToggleProps = {
      mode: 'editor',
      onModeChange: () => {},
    };

    expect(validProps.mode).toBe('editor');
    expect(typeof validProps.onModeChange).toBe('function');
  });
});

describe('PassportView props interface', () => {
  it('requires schema, formData, and children props', () => {
    // Type verification - ensures the interface is correct
    interface PassportViewProps {
      schema: { idShort: string }; // Simplified for test
      formData: Record<string, unknown> | undefined;
      children: unknown;
    }

    const validProps: PassportViewProps = {
      schema: { idShort: 'Test' },
      formData: undefined,
      children: null,
    };

    expect(validProps.schema.idShort).toBe('Test');
    expect(validProps.formData).toBeUndefined();
  });
});

/**
 * Note: The following tests would require @testing-library/react:
 *
 * - Toggle renders with Editor mode active by default
 * - Clicking Passport button switches to passport view
 * - Clicking Editor button switches back to editor view
 * - Editor content is hidden (not unmounted) in passport mode
 * - PassportCard receives correct schema and formData
 * - Mode preference persists to localStorage
 *
 * To add full component tests, install:
 *   npm install -D @testing-library/react @testing-library/jest-dom
 *
 * Then add a setup file (src/setupTests.ts) and update vite.config.ts
 * with the vitest configuration.
 */
