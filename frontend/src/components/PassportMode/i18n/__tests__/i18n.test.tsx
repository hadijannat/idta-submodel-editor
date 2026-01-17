/**
 * Tests for PassportMode i18n infrastructure.
 */

import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, act, cleanup } from '@testing-library/react';
import { renderHook } from '@testing-library/react';
import {
  usePassportI18n,
  PassportI18nProvider,
  detectLocale,
  DEFAULT_LOCALE,
} from '../index';
import { en } from '../en';
import { de } from '../de';
import type { PassportLocale } from '../index';

describe('i18n infrastructure', () => {
  describe('detectLocale', () => {
    const originalNavigator = globalThis.navigator;

    afterEach(() => {
      // Restore original navigator
      Object.defineProperty(globalThis, 'navigator', {
        value: originalNavigator,
        writable: true,
      });
    });

    it('returns "en" for English browser language', () => {
      Object.defineProperty(globalThis, 'navigator', {
        value: { language: 'en-US' },
        writable: true,
      });
      expect(detectLocale()).toBe('en');
    });

    it('returns "de" for German browser language', () => {
      Object.defineProperty(globalThis, 'navigator', {
        value: { language: 'de-DE' },
        writable: true,
      });
      expect(detectLocale()).toBe('de');
    });

    it('returns "de" for simple German language code', () => {
      Object.defineProperty(globalThis, 'navigator', {
        value: { language: 'de' },
        writable: true,
      });
      expect(detectLocale()).toBe('de');
    });

    it('returns default locale for unsupported languages', () => {
      Object.defineProperty(globalThis, 'navigator', {
        value: { language: 'fr-FR' },
        writable: true,
      });
      expect(detectLocale()).toBe(DEFAULT_LOCALE);
    });

    it('returns default locale when navigator is undefined', () => {
      Object.defineProperty(globalThis, 'navigator', {
        value: undefined,
        writable: true,
      });
      expect(detectLocale()).toBe(DEFAULT_LOCALE);
    });
  });

  describe('usePassportI18n hook (standalone)', () => {
    it('provides translation function', () => {
      const { result } = renderHook(() => usePassportI18n());

      expect(result.current.t('toggle.editor')).toBe('Editor');
      expect(result.current.t('toggle.passportView')).toBe('Passport View');
    });

    it('provides locale state', () => {
      const { result } = renderHook(() => usePassportI18n());

      expect(result.current.locale).toBeDefined();
      expect(['en', 'de']).toContain(result.current.locale);
    });

    it('provides available locales', () => {
      const { result } = renderHook(() => usePassportI18n());

      expect(result.current.availableLocales).toContain('en');
      expect(result.current.availableLocales).toContain('de');
    });

    it('allows changing locale', () => {
      const { result } = renderHook(() => usePassportI18n());

      act(() => {
        result.current.setLocale('de');
      });

      expect(result.current.locale).toBe('de');
      expect(result.current.t('toggle.editor')).toBe('Editor');
      expect(result.current.t('toggle.passportView')).toBe('Passport-Ansicht');
    });

    it('falls back to default for invalid locale', () => {
      const { result } = renderHook(() => usePassportI18n());

      act(() => {
        result.current.setLocale('invalid' as PassportLocale);
      });

      expect(result.current.locale).toBe(DEFAULT_LOCALE);
    });
  });

  describe('PassportI18nProvider', () => {
    afterEach(() => {
      cleanup();
    });

    function TestComponent() {
      const { locale, t, setLocale } = usePassportI18n();
      return (
        <div>
          <span data-testid="locale">{locale}</span>
          <span data-testid="translation">{t('toggle.editor')}</span>
          <button onClick={() => setLocale('de')}>Switch to German</button>
        </div>
      );
    }

    it('provides context to child components', () => {
      render(
        <PassportI18nProvider initialLocale="en">
          <TestComponent />
        </PassportI18nProvider>
      );

      expect(screen.getByTestId('locale').textContent).toBe('en');
      expect(screen.getByTestId('translation').textContent).toBe('Editor');
    });

    it('respects initial locale', () => {
      render(
        <PassportI18nProvider initialLocale="de">
          <TestComponent />
        </PassportI18nProvider>
      );

      expect(screen.getByTestId('locale').textContent).toBe('de');
      expect(screen.getByTestId('translation').textContent).toBe('Editor');
    });

    it('shares locale across multiple consumers', () => {
      function SecondConsumer() {
        const { locale } = usePassportI18n();
        return <span data-testid="second-locale">{locale}</span>;
      }

      render(
        <PassportI18nProvider initialLocale="en">
          <TestComponent />
          <SecondConsumer />
        </PassportI18nProvider>
      );

      act(() => {
        screen.getByRole('button').click();
      });

      expect(screen.getByTestId('locale').textContent).toBe('de');
      expect(screen.getByTestId('second-locale').textContent).toBe('de');
    });
  });

  describe('translation interpolation', () => {
    it('interpolates parameters', () => {
      const { result } = renderHook(() => usePassportI18n());

      const translated = result.current.t('pcf.perUnit', { unit: 'kg' });
      expect(translated).toBe('per kg');
    });

    it('interpolates numeric parameters', () => {
      const { result } = renderHook(() => usePassportI18n());

      const translated = result.current.t('generic.itemsCount', { count: 5 });
      expect(translated).toBe('5 items');
    });

    it('preserves unmatched parameters', () => {
      const { result } = renderHook(() => usePassportI18n());

      const translated = result.current.t('pcf.perUnit', {});
      expect(translated).toBe('per {{unit}}');
    });
  });

  describe('translation keys', () => {
    it('returns key for missing translation', () => {
      const { result } = renderHook(() => usePassportI18n());

      // Force an unknown key
      // @ts-expect-error - testing missing key behavior
      const translated = result.current.t('nonexistent.key');
      expect(translated).toBe('nonexistent.key');
    });
  });

  describe('English translations completeness', () => {
    it('has all toggle translations', () => {
      expect(en.toggle.editor).toBeDefined();
      expect(en.toggle.passportView).toBeDefined();
      expect(en.toggle.viewModeLabel).toBeDefined();
    });

    it('has all loading translations', () => {
      expect(en.loading.ariaLabel).toBeDefined();
      expect(en.loading.loading).toBeDefined();
    });

    it('has all error translations', () => {
      expect(en.error.title).toBeDefined();
      expect(en.error.description).toBeDefined();
      expect(en.error.retry).toBeDefined();
      expect(en.error.editorHint).toBeDefined();
    });

    it('has all nameplate translations', () => {
      expect(en.nameplate.emptyMessage).toBeDefined();
      expect(en.nameplate.emptyHint).toBeDefined();
      expect(en.nameplate.identifierMarker).toBeDefined();
      expect(en.nameplate.fields.serialNumber).toBeDefined();
      expect(en.nameplate.fields.manufacturerProductType).toBeDefined();
    });

    it('has all PCF translations', () => {
      expect(en.pcf.title).toBeDefined();
      expect(en.pcf.emptyMessage).toBeDefined();
      expect(en.pcf.totalCo2e).toBeDefined();
      expect(en.pcf.phases.A1).toBeDefined();
      expect(en.pcf.phases.D).toBeDefined();
    });

    it('has all generic translations', () => {
      expect(en.generic.emptyMessage).toBeDefined();
      expect(en.generic.emptyHint).toBeDefined();
      expect(en.generic.templateLabel).toBeDefined();
      expect(en.generic.itemsCount).toBeDefined();
      expect(en.generic.itemLabel).toBeDefined();
    });
  });

  describe('German translations completeness', () => {
    it('has all toggle translations', () => {
      expect(de.toggle.editor).toBeDefined();
      expect(de.toggle.passportView).toBeDefined();
      expect(de.toggle.viewModeLabel).toBeDefined();
    });

    it('has all loading translations', () => {
      expect(de.loading.ariaLabel).toBeDefined();
      expect(de.loading.loading).toBeDefined();
    });

    it('has all error translations', () => {
      expect(de.error.title).toBeDefined();
      expect(de.error.description).toBeDefined();
      expect(de.error.retry).toBeDefined();
      expect(de.error.editorHint).toBeDefined();
    });

    it('has all nameplate translations', () => {
      expect(de.nameplate.emptyMessage).toBeDefined();
      expect(de.nameplate.emptyHint).toBeDefined();
      expect(de.nameplate.identifierMarker).toBeDefined();
      expect(de.nameplate.fields.serialNumber).toBeDefined();
      expect(de.nameplate.fields.manufacturerProductType).toBeDefined();
    });

    it('has all PCF translations', () => {
      expect(de.pcf.title).toBeDefined();
      expect(de.pcf.emptyMessage).toBeDefined();
      expect(de.pcf.totalCo2e).toBeDefined();
      expect(de.pcf.phases.A1).toBeDefined();
      expect(de.pcf.phases.D).toBeDefined();
    });

    it('has all generic translations', () => {
      expect(de.generic.emptyMessage).toBeDefined();
      expect(de.generic.emptyHint).toBeDefined();
      expect(de.generic.templateLabel).toBeDefined();
      expect(de.generic.itemsCount).toBeDefined();
      expect(de.generic.itemLabel).toBeDefined();
    });
  });

  describe('German translations are different from English', () => {
    it('toggle translations differ', () => {
      expect(de.toggle.passportView).not.toBe(en.toggle.passportView);
      expect(de.toggle.viewModeLabel).not.toBe(en.toggle.viewModeLabel);
    });

    it('nameplate translations differ', () => {
      expect(de.nameplate.emptyMessage).not.toBe(en.nameplate.emptyMessage);
      expect(de.nameplate.fields.serialNumber).not.toBe(en.nameplate.fields.serialNumber);
    });

    it('PCF phase translations differ', () => {
      expect(de.pcf.phases.A1).not.toBe(en.pcf.phases.A1);
      expect(de.pcf.phases.A3).not.toBe(en.pcf.phases.A3);
    });
  });
});
